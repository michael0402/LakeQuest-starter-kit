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
{"qa_id": "example-id", "answer": "answer text", "object_ids": ["object-id"], "provenance_ids": ["provenance-id"]}
```

Field meanings:

- `qa_id`: the unique question identifier from `questions.jsonl` or `questions.parquet`. The scorer matches predictions to questions using this field.
- `answer`: your natural-language answer. This is required. Deterministic scoring computes token F1 against the reference answer; optional organizer LLM judging compares this text to the reference answer for factual correctness.
- `object_ids`: optional list of supporting lake object IDs. These IDs come from the public lake files, especially `lakes/<lake>/corpus_objects.parquet`. They identify the objects, tables, documents, records, or other lake artifacts your system used to answer the question. The scorer computes set F1 against the gold supporting object IDs.
- `provenance_ids`: optional list of finer-grained evidence/provenance IDs. These identify specific supporting provenance records or evidence units for the answer. The scorer computes set F1 against the gold provenance IDs.

Example:

```json
{"qa_id": "aiml_000123", "answer": "The model was trained with a batch size of 64.", "object_ids": ["paper_17"], "provenance_ids": ["paper_17::table_2::row_4"]}
```

If your system cannot reliably identify evidence, submit empty lists for `object_ids` and `provenance_ids`. Your answer will still be scored, but the object/provenance components will be zero for those questions.

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
{"qa_id": "example-id", "answer": "answer text", "object_ids": ["object-id"], "provenance_ids": ["provenance-id"]}
```

`answer` is required. `object_ids` and `provenance_ids` are optional but scored.

The input directory contains:

```text
questions.parquet
questions.jsonl
manifest.json
lakes/<lake>/manifest.json
lakes/<lake>/corpus_objects.parquet
lakes/<lake>/split_entities.parquet
```

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
