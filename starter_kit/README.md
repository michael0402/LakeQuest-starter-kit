# LakeQuest Submission Starting Kit

LakeQuest has two submission formats:

- `Development` and `Partial Test`: submit a zip containing `predictions.jsonl` at the archive root.
- `Held-out Code Evaluation`: submit a runnable project zip with `run.sh` or `run.py`.

## Prediction Submission Format

For `Development` and `Partial Test`, create:

```text
submission.zip
  predictions.jsonl
```

Each line must be:

```json
{"qa_id": "example-id", "answer": "answer text"}
```

You may optionally include:

```json
{"qa_id": "example-id", "answer": "answer text", "object_ids": ["object-id"], "provenance_ids": ["evidence-id"]}
```

Field meanings:

- `qa_id`: the unique question identifier from `questions.jsonl` or `questions.parquet`. The scorer matches predictions to questions using this field.
- `answer`: your natural-language answer. This is required and is the main leaderboard score. Deterministic scoring computes token F1 against the reference answer; optional organizer LLM judging compares this text to the reference answer for factual correctness.
- `object_ids`: optional list of supporting lake object IDs. These IDs come from `lakes/<lake>/corpus_objects.parquet`. They identify the lake artifacts your system used, such as Hugging Face cards, bank tables, policy documents, DrugBank tables, or drug passages. The scorer reports diagnostic set F1 against gold supporting object IDs, but this is not part of the main leaderboard score.
- `provenance_ids`: optional list of finer-grained gold evidence IDs. These are internal evidence records attached to the benchmark references. They are useful for attribution diagnostics when released, but they are not required for Open Test or Closed Test predictions and are not part of the main leaderboard score.

Example:

```json
{"qa_id": "aiml_000123", "answer": "The model was trained with a batch size of 64.", "object_ids": ["model_card:example-model"], "provenance_ids": []}
```

If your system cannot reliably identify evidence, omit `object_ids` and
`provenance_ids` or submit empty lists. Your answer will still receive the main
leaderboard score.

## Code Submission Format

Submit a zip whose root contains either `run.sh` or `run.py`.

Codabench will run your project as:

```bash
bash run.sh --input /app/input_data --output /app/output
```

Your code must write:

```text
/app/output/predictions.jsonl
```

Each line must be a JSON object:

```json
{"qa_id": "example-id", "answer": "answer text"}
```

`answer` is required. `object_ids` and `provenance_ids` are optional diagnostics.

The input directory contains:

```text
questions.parquet
questions.jsonl
manifest.json
lakes/<lake>/manifest.json
lakes/<lake>/corpus_objects.parquet
lakes/<lake>/split_entities.parquet
```

The downloadable shared public lake package also contains `raw_lake_snapshot/`,
which is the frozen lake content participants should use instead of crawling
live sources.

For example, bank `policy_document` object IDs in
`lakes/bank/corpus_objects.parquet` map to policy text in
`raw_lake_snapshot/lakes/bank/policy_documents.jsonl`.

## Python Requirements

Held-out submissions run inside the organizer Docker image:

```text
michaelsolodko/lakequest-codabench-gpu-eval:2026-05
```

The image includes Python, pandas, pyarrow, numpy, scipy, scikit-learn, and PyTorch with CUDA.

If your project only uses those packages, do not include anything extra.

If your project needs additional Python packages, include:

```text
submission.zip
  run.sh
  requirements.txt
  wheels/
    package_a-...whl
    package_b-...whl
  src/...
```

Official held-out evaluation is run without internet access. The runner installs `requirements.txt` from the top-level `wheels/` directory into an isolated temporary dependency directory and adds it to `PYTHONPATH`. Do not rely on downloading packages, models, or data during evaluation.

Build the wheelhouse before zipping:

```bash
python -m pip download -r requirements.txt -d wheels
```

For GPU packages, make sure the wheel versions are compatible with CUDA 12.4 and the official image.
