import os

import pytest
import responses
from requests.exceptions import HTTPError

import src.core.map_processors as mp
from tests.fixtures.utils.util_mocks import MockBar


@pytest.fixture
def patch_subprocess(monkeypatch):
    calls = {}

    def mock_run(cmd, shell, check):
        calls["cmd"] = cmd
        calls["shell"] = shell
        calls["check"] = check

    monkeypatch.setattr(mp.subprocess, "run", mock_run, raising=True)
    return calls


@pytest.fixture
def patch_boto3(monkeypatch):
    uploaded = {}

    class MockS3:
        def upload_file(self, source, bucket, key):
            uploaded["source"] = source
            uploaded["bucket"] = bucket
            uploaded["key"] = key

    monkeypatch.setattr(mp.boto3, "client", lambda name: MockS3(), raising=True)
    return uploaded


def test_mbtile_generation_happy_path(monkeypatch, patch_subprocess, capsys):
    monkeypatch.setattr(mp, "tqdm", MockBar, raising=True)
    mp.generate_mbtiles("in.geojson", "out.mbtiles", verbose=True)
    calls = patch_subprocess
    assert "tippecanoe" in calls["cmd"]
    assert "in.geojson" in calls["cmd"]
    assert "out.mbtiles" in calls["cmd"]
    assert calls["shell"] is True and calls["check"] is True

    out = capsys.readouterr().out
    assert "Creating mbtiles file" in out
    assert "mbtiles file created" in out


# ----------------------------
# generate_mbtiles
# ----------------------------
def test_mbtile_generation_errors(monkeypatch):
    monkeypatch.setattr(
        mp.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad")), raising=True
    )

    captured = {}
    monkeypatch.setattr(mp.logger, "error", lambda m: captured.setdefault("msg", m), raising=True)

    with pytest.raises(ValueError, match="bad"):
        mp.generate_mbtiles("input", "output")
    assert "Error generating mbtiles file from input" in captured["msg"]


# ----------------------------
# getS3Credentials / setS3Credentials (responses)
# ----------------------------
@responses.activate
def test_get_s3_credentials_happy_path():
    url = f"{mp.MAPBOX_BASE_URL}user/credentials?access_token=token123"
    responses.add(
        responses.GET,
        url,
        json={"accessKeyId": "AK", "secretAccessKey": "SK", "sessionToken": "ST"},
        status=200,
    )
    creds = mp.getS3Credentials("user", "token123")
    assert creds["accessKeyId"] == "AK"
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == url


def test_set_s3_credentials_sets_env(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)

    mp.setS3Credentials({"accessKeyId": "AK", "secretAccessKey": "SK", "sessionToken": "ST"})
    assert os.environ["AWS_ACCESS_KEY_ID"] == "AK"
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "SK"
    assert os.environ["AWS_SESSION_TOKEN"] == "ST"


# ----------------------------
# uploadToS3 (boto3)
# ----------------------------
def test_upload_to_s3(patch_boto3, capsys):
    mp.uploadToS3("local.mbtiles", {"bucket": "b", "key": "k"}, verbose=True)
    assert patch_boto3 == {"source": "local.mbtiles", "bucket": "b", "key": "k"}
    assert "Upload to S3 complete." in capsys.readouterr().out


# ----------------------------
# link_to_mapbox (responses)
# ----------------------------
@responses.activate
def test_link_to_mapbox_happy_path(monkeypatch):
    # Mock to speed up test by avoiding sleep
    monkeypatch.setattr(mp, "sleep", lambda s: None, raising=True)

    post_url = f"{mp.MAPBOX_BASE_URL}user?access_token=tok"
    responses.add(
        responses.POST,
        post_url,
        json={"id": "upload_123"},
        status=200,
    )

    status_url = f"{mp.MAPBOX_BASE_URL}user/upload_123?access_token=tok"

    # Initially not complete
    responses.add(
        responses.GET,
        status_url,
        json={"error": None, "complete": False, "progress": 0.25},
        status=200,
    )

    # Complete on second check
    responses.add(
        responses.GET,
        status_url,
        json={"error": None, "complete": True, "progress": 1.0},
        status=200,
    )

    ok = mp.link_to_mapbox(
        username="user",
        token="tok",
        credentials={"bucket": "mb", "key": "abc/tiles.mbtiles"},
        tileset_name="tileset",
        display_name="MyTiles",
    )
    assert ok is True
    # Verify body posted to Mapbox includes s3 url and tileset
    sent = responses.calls[0].request.body
    assert b"tileset" in sent and b"user.tileset" in sent
    assert b"https://mb.s3.amazonaws.com/abc/tiles.mbtiles" in sent
    assert len(responses.calls) == 3  # POST + 2 GETs


@responses.activate
def test_link_to_mapbox_raises_on_status_error(monkeypatch):
    monkeypatch.setattr(mp, "sleep", lambda s: None, raising=True)

    post_url = f"{mp.MAPBOX_BASE_URL}user?access_token=token"
    responses.add(responses.POST, post_url, json={"id": "ID"}, status=200)

    status_url = f"{mp.MAPBOX_BASE_URL}user/ID?access_token=token"
    responses.add(
        responses.GET,
        status_url,
        json={"error": "broken", "complete": False, "progress": 0.0},
        status=500,
    )

    with pytest.raises(HTTPError):
        mp.link_to_mapbox("user", "token", {"bucket": "b", "key": "k"}, "tileset", "display")


@responses.activate
def test_link_to_mapbox_bad_credentials_error(monkeypatch):
    monkeypatch.setattr(mp, "sleep", lambda s: None, raising=True)

    with pytest.raises(ValueError, match="Missing bucket or key in credentials"):
        mp.link_to_mapbox("user", "token", {"empty": "bad"}, "tileset", "display")


# ----------------------------
# upload_to_mapbox (orchestration)
# ----------------------------
@responses.activate
def test_upload_to_mapbox_calls_all_steps(monkeypatch, capsys, patch_boto3):
    # 1) Mapbox credentials GET
    cred_url = f"{mp.MAPBOX_BASE_URL}user/credentials?access_token=tok"
    responses.add(
        responses.GET,
        cred_url,
        json={
            "accessKeyId": "AK",
            "secretAccessKey": "SK",
            "sessionToken": "ST",
            "bucket": "b",
            "key": "k",
        },
        status=200,
    )

    # 2) POST create upload
    post_url = f"{mp.MAPBOX_BASE_URL}user?access_token=tok"
    responses.add(responses.POST, post_url, json={"id": "up1"}, status=200)

    # 3) GET status (complete immediately)
    status_url = f"{mp.MAPBOX_BASE_URL}user/up1?access_token=tok"
    responses.add(
        responses.GET,
        status_url,
        json={"error": None, "complete": True, "progress": 1.0},
        status=200,
    )

    # avoid sleeping
    monkeypatch.setattr(mp, "sleep", lambda s: None, raising=True)

    mp.upload_to_mapbox(
        source="out.mbtiles",
        tileset_id="tid",
        display_name="Display",
        username="user",
        token="tok",
        verbose=True,
    )

    # Verified: credentials GET called
    assert responses.calls[0].request.url == cred_url
    # Upload to S3 happened with our boto3 fake
    assert patch_boto3 == {"source": "out.mbtiles", "bucket": "b", "key": "k"}
    # Mapbox POST & GET called
    assert responses.calls[1].request.url == post_url
    assert responses.calls[2].request.url == status_url

    assert "Uploading to Mapbox..." in capsys.readouterr().out
