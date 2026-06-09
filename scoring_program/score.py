#!/usr/bin/env python3
"""LakeQuest scorer for Codabench.

The deterministic metrics always run. Optional LLM judging can be enabled by
setting LAKEQUEST_ENABLE_LLM_JUDGE=1 and providing OPENROUTER_API_KEY.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


APP_ROOT = Path(os.getenv("LAKEQUEST_APP_ROOT", "/app"))
INPUT_ROOT = Path(os.getenv("LAKEQUEST_SCORING_INPUT_ROOT", APP_ROOT / "input"))
REFERENCE_DIR = Path(os.getenv("LAKEQUEST_REFERENCE_DIR", INPUT_ROOT / "ref"))
RESULT_DIR = Path(os.getenv("LAKEQUEST_RESULT_DIR", INPUT_ROOT / "res"))
OUTPUT_DIR = Path(os.getenv("LAKEQUEST_SCORE_OUTPUT_DIR", APP_ROOT / "output"))

ANSWER_WEIGHT = 0.70
OBJECT_WEIGHT = 0.15
PROVENANCE_WEIGHT = 0.15
TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
LLM_ALLOWED_SCORES = (0.0, 0.5, 1.0)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if hasattr(value, "tolist"):
        return _as_list(value.tolist())

    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            decoded = json.loads(text)
            return _as_list(decoded)
        except json.JSONDecodeError:
            pass
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return [text]


def _normalize_id(value: str) -> str:
    return str(value).strip().lower()


def _tokenize(text: Any) -> list[str]:
    return TOKEN_RE.findall(str(text or "").lower())


def _token_f1(reference: str, prediction: str) -> float:
    ref_tokens = _tokenize(reference)
    pred_tokens = _tokenize(prediction)
    if not ref_tokens and not pred_tokens:
        return 1.0
    if not ref_tokens or not pred_tokens:
        return 0.0

    ref_counts: dict[str, int] = defaultdict(int)
    pred_counts: dict[str, int] = defaultdict(int)
    for token in ref_tokens:
        ref_counts[token] += 1
    for token in pred_tokens:
        pred_counts[token] += 1

    overlap = sum(min(ref_counts[token], pred_counts[token]) for token in ref_counts)
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def _coerce_llm_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return math.nan
    return min(LLM_ALLOWED_SCORES, key=lambda allowed: abs(allowed - score))


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _parse_llm_score(text: str) -> float:
    parsed = _extract_json_object(text)
    if "score" in parsed:
        return _coerce_llm_score(parsed["score"])
    match = re.search(r"\b(?:0(?:\.0)?|0\.5|1(?:\.0)?)\b", text)
    return _coerce_llm_score(match.group(0)) if match else math.nan


def _set_f1(reference: Iterable[str], prediction: Iterable[str]) -> float:
    ref = {_normalize_id(item) for item in reference if str(item).strip()}
    pred = {_normalize_id(item) for item in prediction if str(item).strip()}
    if not ref and not pred:
        return 1.0
    if not ref or not pred:
        return 0.0
    overlap = len(ref.intersection(pred))
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(ref)
    return 2 * precision * recall / (precision + recall)


def _llm_enabled() -> bool:
    return _env_flag("LAKEQUEST_ENABLE_LLM_JUDGE") and (
        bool(os.getenv("OPENROUTER_API_KEY")) or _env_flag("LAKEQUEST_LLM_JUDGE_MOCK")
    )


def _openrouter_headers() -> dict[str, str]:
    headers = {}
    headers["Authorization"] = f"Bearer {os.environ['OPENROUTER_API_KEY']}"
    headers["Content-Type"] = "application/json"
    if os.getenv("OPENROUTER_SITE_URL"):
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "")
    if os.getenv("OPENROUTER_SITE_NAME"):
        headers["X-Title"] = os.getenv("OPENROUTER_SITE_NAME", "")
    return headers


def _openrouter_chat_completion(model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers=_openrouter_headers(),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_env_float("LAKEQUEST_LLM_JUDGE_TIMEOUT", 60.0)) as response:
        return json.loads(response.read().decode("utf-8"))


def _reference_answer(reference: pd.Series) -> str:
    answer_short = str(reference.get("answer_short", "") or "").strip()
    answer_long = str(reference.get("answer_long", "") or "").strip()
    if answer_short and answer_long and answer_short != answer_long:
        return f"Short answer: {answer_short}\nFull reference: {answer_long}"
    return answer_short or answer_long


def _llm_judge_prompt(reference: pd.Series, prediction: dict[str, Any]) -> list[dict[str, str]]:
    question = str(reference.get("question", "") or "").strip()
    reference_answer = _reference_answer(reference)
    candidate_answer = str(prediction.get("answer", "") or "").strip()
    return [
        {
            "role": "system",
            "content": (
                "You are grading a LakeQuest benchmark answer. Compare the candidate answer "
                "to the reference answer for factual correctness and completeness. Award 1 "
                "when it is correct, 0.5 when it is partially correct or misses important "
                "details, and 0 when it is incorrect, unsupported, or empty. Do not require "
                "identical wording. Return only JSON with keys score and reason."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{question}\n\n"
                f"Reference answer:\n{reference_answer}\n\n"
                f"Candidate answer:\n{candidate_answer}\n\n"
                'Return JSON exactly like {"score": 0, "reason": "brief reason"} '
                "where score is one of 0, 0.5, or 1."
            ),
        },
    ]


def _usage_counts(response: dict[str, Any]) -> tuple[int, int, int]:
    usage = response.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or 0)
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    return prompt_tokens, completion_tokens, total_tokens


def _compute_cost(prompt_tokens: int, completion_tokens: int) -> float:
    prompt_price = _env_float("OPENROUTER_PROMPT_PRICE_PER_1K", 0.0)
    completion_price = _env_float("OPENROUTER_COMPLETION_PRICE_PER_1K", 0.0)
    return (prompt_tokens / 1000.0 * prompt_price) + (
        completion_tokens / 1000.0 * completion_price
    )


def _score_with_llm(
    reference: pd.Series,
    prediction: dict[str, Any] | None,
    answer_f1: float,
) -> dict[str, Any]:
    if prediction is None or not str(prediction.get("answer", "") or "").strip():
        return {
            "llm_answer_score": math.nan,
            "llm_judge_available": False,
            "llm_prompt_tokens": 0,
            "llm_completion_tokens": 0,
            "llm_total_tokens": 0,
            "llm_processing_time": 0.0,
            "llm_inference_cost": 0.0,
        }

    if _env_flag("LAKEQUEST_LLM_JUDGE_MOCK"):
        mock_score = 1.0 if answer_f1 >= 0.75 else 0.5 if answer_f1 >= 0.25 else 0.0
        return {
            "llm_answer_score": mock_score,
            "llm_judge_available": True,
            "llm_prompt_tokens": 0,
            "llm_completion_tokens": 0,
            "llm_total_tokens": 0,
            "llm_processing_time": 0.0,
            "llm_inference_cost": 0.0,
        }

    model = os.getenv("LAKEQUEST_LLM_JUDGE_MODEL", "openai/gpt-5-mini")
    max_retries = max(1, _env_int("LAKEQUEST_LLM_JUDGE_RETRIES", 3))
    start = time.time()
    last_error = ""
    for attempt in range(max_retries):
        try:
            response = _openrouter_chat_completion(model, _llm_judge_prompt(reference, prediction))
            content = response["choices"][0]["message"].get("content") or ""
            score = _parse_llm_score(content)
            if math.isnan(score):
                raise ValueError(f"Could not parse LLM score from response: {content[:200]}")
            prompt_tokens, completion_tokens, total_tokens = _usage_counts(response)
            return {
                "llm_answer_score": score,
                "llm_judge_available": True,
                "llm_prompt_tokens": prompt_tokens,
                "llm_completion_tokens": completion_tokens,
                "llm_total_tokens": total_tokens,
                "llm_processing_time": time.time() - start,
                "llm_inference_cost": _compute_cost(prompt_tokens, completion_tokens),
            }
        except (Exception, urllib.error.URLError) as exc:  # Keep scoring resilient for benchmark operations.
            last_error = type(exc).__name__
            if attempt + 1 < max_retries:
                time.sleep(min(8.0, 2.0**attempt))

    if _env_flag("LAKEQUEST_LLM_JUDGE_FAIL_CLOSED"):
        raise RuntimeError(f"LLM judge failed after {max_retries} attempts: {last_error}")
    return {
        "llm_answer_score": math.nan,
        "llm_judge_available": False,
        "llm_prompt_tokens": 0,
        "llm_completion_tokens": 0,
        "llm_total_tokens": 0,
        "llm_processing_time": time.time() - start,
        "llm_inference_cost": 0.0,
    }


def _load_references(reference_dir: Path) -> pd.DataFrame:
    parquet_path = reference_dir / "references.parquet"
    jsonl_path = reference_dir / "references.jsonl"
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    if jsonl_path.exists():
        rows = [
            json.loads(line)
            for line in jsonl_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return pd.DataFrame(rows)
    raise FileNotFoundError(
        f"No references found. Expected {parquet_path} or {jsonl_path}."
    )


def _load_predictions(result_dir: Path) -> dict[str, dict[str, Any]]:
    jsonl_path = result_dir / "predictions.jsonl"
    csv_path = result_dir / "predictions.csv"
    if not jsonl_path.exists() and not csv_path.exists():
        return {}

    predictions: dict[str, dict[str, Any]] = {}
    if jsonl_path.exists():
        with jsonl_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON on predictions.jsonl line {line_number}: {exc}"
                    ) from exc
                qa_id = str(row.get("qa_id", "")).strip()
                if qa_id:
                    predictions[qa_id] = row
        return predictions

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            qa_id = str(row.get("qa_id", "")).strip()
            if qa_id:
                predictions[qa_id] = row
    return predictions


def _score_row(reference: pd.Series, prediction: dict[str, Any] | None) -> dict[str, Any]:
    answer = "" if prediction is None else str(prediction.get("answer", "")).strip()
    answer_short = str(reference.get("answer_short", "") or "")
    answer_long = str(reference.get("answer_long", "") or "")
    answer_f1 = max(_token_f1(answer_short, answer), _token_f1(answer_long, answer))

    object_f1 = _set_f1(
        _as_list(reference.get("gold_object_ids")),
        [] if prediction is None else _as_list(prediction.get("object_ids")),
    )
    provenance_f1 = _set_f1(
        _as_list(reference.get("gold_provenance_ids")),
        [] if prediction is None else _as_list(prediction.get("provenance_ids")),
    )
    answered = bool(answer)
    overall = (
        ANSWER_WEIGHT * answer_f1
        + OBJECT_WEIGHT * object_f1
        + PROVENANCE_WEIGHT * provenance_f1
    )
    return {
        "qa_id": reference["qa_id"],
        "domain": reference["domain"],
        "answered": answered,
        "answer_f1": answer_f1,
        "object_f1": object_f1,
        "provenance_f1": provenance_f1,
        "overall_score": overall,
        "llm_answer_score": math.nan,
        "llm_overall_score": math.nan,
        "llm_judge_available": False,
        "llm_prompt_tokens": 0,
        "llm_completion_tokens": 0,
        "llm_total_tokens": 0,
        "llm_processing_time": 0.0,
        "llm_inference_cost": 0.0,
    }


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if not math.isnan(float(row[key]))]
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _apply_llm_judging(
    references: pd.DataFrame,
    predictions: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    if not _llm_enabled():
        return

    max_rows = _env_int("LAKEQUEST_LLM_JUDGE_MAX_ROWS", 0)
    workers = max(1, _env_int("LAKEQUEST_LLM_JUDGE_WORKERS", 4))
    jobs: list[tuple[int, pd.Series, dict[str, Any] | None]] = []
    for index, (_, reference) in enumerate(references.iterrows()):
        if max_rows > 0 and len(jobs) >= max_rows:
            break
        prediction = predictions.get(str(reference["qa_id"]))
        if prediction is not None and str(prediction.get("answer", "") or "").strip():
            jobs.append((index, reference, prediction))

    def run_job(job: tuple[int, pd.Series, dict[str, Any] | None]) -> tuple[int, dict[str, Any]]:
        index, reference, prediction = job
        result = _score_with_llm(reference, prediction, rows[index]["answer_f1"])
        return index, result

    if workers == 1:
        for job in jobs:
            index, result = run_job(job)
            rows[index].update(result)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_index = {executor.submit(run_job, job): job[0] for job in jobs}
            for future in as_completed(future_to_index):
                index, result = future.result()
                rows[index].update(result)

    for row in rows:
        if row["llm_judge_available"] and not math.isnan(float(row["llm_answer_score"])):
            row["llm_overall_score"] = (
                ANSWER_WEIGHT * float(row["llm_answer_score"])
                + OBJECT_WEIGHT * float(row["object_f1"])
                + PROVENANCE_WEIGHT * float(row["provenance_f1"])
            )


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    references = _load_references(REFERENCE_DIR)
    predictions = _load_predictions(RESULT_DIR)

    required_columns = {
        "qa_id",
        "domain",
        "answer_short",
        "answer_long",
        "gold_object_ids",
        "gold_provenance_ids",
    }
    missing = sorted(required_columns.difference(references.columns))
    if missing:
        raise ValueError(f"Reference data missing required columns: {missing}")

    rows = [
        _score_row(reference, predictions.get(str(reference["qa_id"])))
        for _, reference in references.iterrows()
    ]
    _apply_llm_judging(references, predictions, rows)

    per_item_path = OUTPUT_DIR / "per_item_scores.csv"
    pd.DataFrame(rows).to_csv(per_item_path, index=False)

    score_keys = [
        "overall_score",
        "answer_f1",
        "object_f1",
        "provenance_f1",
        "llm_answer_score",
        "llm_overall_score",
    ]
    scores = {key: _mean(rows, key) for key in score_keys}
    scores["coverage"] = sum(1 for row in rows if row["answered"]) / len(rows) if rows else 0.0
    llm_rows = [row for row in rows if row["llm_judge_available"]]
    scores["llm_judge_enabled"] = 1.0 if _llm_enabled() else 0.0
    scores["llm_judge_coverage"] = len(llm_rows) / len(rows) if rows else 0.0
    scores["llm_judge_rows"] = len(llm_rows)
    scores["llm_prompt_tokens"] = int(sum(int(row["llm_prompt_tokens"]) for row in rows))
    scores["llm_completion_tokens"] = int(
        sum(int(row["llm_completion_tokens"]) for row in rows)
    )
    scores["llm_total_tokens"] = int(sum(int(row["llm_total_tokens"]) for row in rows))
    scores["llm_inference_cost"] = float(
        sum(float(row["llm_inference_cost"]) for row in rows)
    )
    scores["n_questions"] = len(rows)
    scores["n_predictions"] = len(predictions)

    for domain in sorted({str(row["domain"]) for row in rows}):
        domain_rows = [row for row in rows if row["domain"] == domain]
        scores[f"{domain}_score"] = _mean(domain_rows, "overall_score")
        scores[f"{domain}_llm_answer_score"] = _mean(domain_rows, "llm_answer_score")
        scores[f"{domain}_llm_overall_score"] = _mean(domain_rows, "llm_overall_score")
        scores[f"{domain}_coverage"] = (
            sum(1 for row in domain_rows if row["answered"]) / len(domain_rows)
            if domain_rows
            else 0.0
        )
        domain_llm_rows = [row for row in domain_rows if row["llm_judge_available"]]
        scores[f"{domain}_llm_judge_coverage"] = (
            len(domain_llm_rows) / len(domain_rows) if domain_rows else 0.0
        )

    (OUTPUT_DIR / "scores.json").write_text(
        json.dumps(scores, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
