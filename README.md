# LakeQuest Starter Kit

This repository contains the participant-facing materials for the LakeQuest Codabench tracks.

## Contents

- `starter_kit/`: submission template, prediction schema, and README for prediction and code submissions.
- `scoring_program/`: the public Codabench scoring program used by the open tracks.
- `public_data/public_lake_data.zip`: shared public lake files used by all LakeQuest tracks.

Hidden answers, held-out inputs, organizer worker scripts, queue credentials, and bundle-build tooling are not included here.

## Tracks

LakeQuest is split into three Codabench tracks:

- `LakeQuest Open Dev`: public development questions and answers. Submit `predictions.jsonl` in a zip.
- `LakeQuest Open Test`: public partial-test questions with hidden answers. Submit `predictions.jsonl` in a zip.
- `LakeQuest Closed Test (Code Evaluation)`: official held-out project submission. Submit a runnable project zip with `run.sh` or `run.py`.

See `starter_kit/README.md` for the required submission format.

## Project Website

The LakeQuest project homepage lives in [`docs/`](docs/) and is configured for
publication at <https://michael0402.github.io/LakeQuest/> through the GitHub
Pages workflow. In the repository's **Settings → Pages** screen, select
**GitHub Actions** as the source once; subsequent changes under `docs/` deploy
automatically from `main`.

The benchmark tracks are:

- [LakeQuest Open Dev](https://www.codabench.org/competitions/17066/)
- [LakeQuest Open Test](https://www.codabench.org/competitions/17065/)
- [LakeQuest Closed Test (Code Evaluation)](https://www.codabench.org/competitions/17064/)

## Prediction Row Format

Each prediction line is a JSON object:

```json
{"qa_id": "example-id", "answer": "answer text"}
```

- `qa_id` identifies the question.
- `answer` is the natural-language answer and is the main leaderboard target.
- `object_ids` are optional supporting public lake object IDs from `lakes/<lake>/corpus_objects.parquet`.
- `provenance_ids` are optional finer-grained gold evidence IDs attached to benchmark references.

The scorer reports answer F1, object ID F1, provenance ID F1, and coverage. The main `overall_score` is answer-only; object/provenance scores are diagnostic attribution metrics.

The public data zip contains a frozen `raw_lake_snapshot/`. For example, bank
`policy_document` IDs map to text in
`raw_lake_snapshot/lakes/bank/policy_documents.jsonl`.

## Local Public Scoring

For Open Dev, download the Codabench input/reference files and run:

```bash
python scoring_program/score.py
```

The Codabench worker sets the required input/output paths automatically. For local runs, set:

```bash
export LAKEQUEST_REFERENCE_DIR=/path/to/reference_data
export LAKEQUEST_RESULT_DIR=/path/to/submission_output
export LAKEQUEST_SCORE_OUTPUT_DIR=/path/to/score_output
python scoring_program/score.py
```
