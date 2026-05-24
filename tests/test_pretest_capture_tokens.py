"""Tests for scripts/pretest_capture_tokens.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pretest_capture_tokens import sum_tokens_by_model


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_sum_tokens_by_model_aggregates_opus_and_haiku(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_jsonl(transcript, [
        {"type": "assistant", "message": {
            "model": "claude-opus-4-7-20260101",
            "usage": {"input_tokens": 1000, "output_tokens": 200,
                       "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        }},
        {"type": "assistant", "message": {
            "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 5000, "output_tokens": 300,
                       "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0},
        }},
        {"type": "assistant", "message": {
            "model": "claude-opus-4-7-20260101",
            "usage": {"input_tokens": 500, "output_tokens": 50,
                       "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        }},
        {"type": "user", "message": {"content": "irrelevant"}},
    ])

    result = sum_tokens_by_model(transcript)

    assert result["opus"]["input_tokens"] == 1500
    assert result["opus"]["output_tokens"] == 250
    assert result["haiku"]["input_tokens"] == 5000
    assert result["haiku"]["output_tokens"] == 300
    assert result["haiku"]["cache_read_input_tokens"] == 100


def test_sum_tokens_by_model_empty_transcript(tmp_path: Path) -> None:
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("", encoding="utf-8")
    result = sum_tokens_by_model(transcript)
    assert result == {
        "opus": {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        "haiku": {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        "sonnet": {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        "other": {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    }


def test_sum_tokens_by_model_unknown_model_goes_to_other(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_jsonl(transcript, [
        {"type": "assistant", "message": {
            "model": "some-other-model-xyz",
            "usage": {"input_tokens": 10, "output_tokens": 5,
                       "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        }},
    ])
    result = sum_tokens_by_model(transcript)
    assert result["other"]["input_tokens"] == 10
    assert result["other"]["output_tokens"] == 5
