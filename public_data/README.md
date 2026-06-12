# Public Lake Data

`public_lake_data.zip` is the shared public lake package used by all LakeQuest tracks.

It contains lake-level public files such as:

```text
manifest.json
lakes/<lake>/manifest.json
lakes/<lake>/corpus_objects.parquet
lakes/<lake>/split_entities.parquet
raw_lake_snapshot/
```

`raw_lake_snapshot/` is the frozen participant-facing lake content. Use it instead of crawling live upstream sources, because live sources can change over time.

It does not contain hidden answers or held-out references.
