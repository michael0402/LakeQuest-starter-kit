# Scoring Program

This is the public LakeQuest Codabench scoring program.

The deterministic metrics are:

- `answer_f1`: token F1 against the reference answer.
- `object_f1`: set F1 against gold supporting object IDs.
- `provenance_f1`: set F1 against gold provenance IDs.
- `coverage`: fraction of questions with a submitted answer.
- `overall_score`: `0.70 * answer_f1 + 0.15 * object_f1 + 0.15 * provenance_f1`.

Codabench provides hidden `reference_data` to this program during scoring. For local runs, set:

```bash
export LAKEQUEST_REFERENCE_DIR=/path/to/reference_data
export LAKEQUEST_RESULT_DIR=/path/to/submission_output
export LAKEQUEST_SCORE_OUTPUT_DIR=/path/to/score_output
python score.py
```
