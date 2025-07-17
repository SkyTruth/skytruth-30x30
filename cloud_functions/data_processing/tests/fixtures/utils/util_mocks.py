class MockBar:
    """A mock tqdm bar that just records calls to update() and close()."""

    def __init__(self, itterable=None):
        self.updates = []
        self.closed = False

    def update(self, n):
        self.updates.append(n)

    def close(self):
        self.closed = True


class IterableMockBar(MockBar):
    """
    Wraps an existing iterable, yields its items,
    and records update(len(item)) on each __next__.
    """

    def __init__(self, iterable, **kwargs):
        super().__init__()
        self._iter = iter(iterable)

    def __iter__(self):
        return self

    def __next__(self):
        chunk = next(self._iter)
        super().update(len(chunk) if hasattr(chunk, "__len__") else 1)
        return chunk


class MockBlob:
    """Mock class for gcs blob"""

    def __init__(self):
        self.uploaded_data = None
        self.kwargs = None

    def upload_from_file(self, file_obj, **kwargs):
        file_obj.seek(0)
        self.uploaded_data = file_obj.read()
        self.kwargs = kwargs


class MockBucket:
    """Mokc class for GCS Bucket"""

    def __init__(self, name, blob):
        self.name = name
        self._blob = blob

    def blob(self, blob_name):
        self.blob_name = blob_name
        return self._blob


class MockClient:
    """Mokc class for GCS client"""

    def __init__(self, bucket):
        self._bucket = bucket

    def bucket(self, name):
        self.bucket_name = name
        return self._bucket


class MockRequest:
    """Mock flask.Request.get_json(silent=True) behavior."""

    def __init__(self, payload):
        self._payload = payload

    def get_json(self, silent=True):
        return self._payload
