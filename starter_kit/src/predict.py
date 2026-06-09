#!/usr/bin/env python3
"""Minimal LakeQuest predictor that writes placeholder answers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Directory containing questions.parquet")
    parser.add_argument("--output", required=True, help="Directory where predictions.jsonl is written")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    questions = pd.read_parquet(input_dir / "questions.parquet")
    output_path = output_dir / "predictions.jsonl"
    with output_path.open("w", encoding="utf-8") as handle:
        for _, row in questions.iterrows():
            prediction = {
                "qa_id": row["qa_id"],
                "answer": "I do not know.",
                "object_ids": [],
                "provenance_ids": [],
            }
            handle.write(json.dumps(prediction) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
