# Data Processing

The purpose of this Cloud Function is to download, store, process, and update the database with current data related to protected areas. The function is called via a series of Cloud Schedulers.

## Architecture

For architecture, data sources and teh high-level data update plan, please see the [internal documentation][documentation].

## Use and Testing

Each method can be run in CLI via a statement like

```shell
gcloud functions call x30-dev-data --data '{"METHOD": "download_habitats"}' --region us-east1
```

There are scheduled monthly jobs to download MPATLAS, Protected Seas, and Protected Planet data. The habitat data and Marine Region data is more or less static and can be run with the above statement.

- #TODO: The Marine Region and habitat filenames are currently hardcoded in params.py and we should update this.

[documentation]: https://drive.google.com/drive/folders/1EkZvHqNViCg__OaCxpPrYIQoTj_YLJIo