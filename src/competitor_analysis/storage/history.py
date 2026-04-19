from __future__ import annotations

import json
from pathlib import Path

from competitor_analysis.models import AnalysisRecord, AnalysisRecordMeta

_HISTORY_DIR = Path(__file__).resolve().parents[3] / ".cache" / "history"


def _ensure_dir() -> Path:
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return _HISTORY_DIR


def _path(record_id: str) -> Path:
    return _ensure_dir() / f"{record_id}.json"


def save_analysis(record: AnalysisRecord) -> str:
    _path(record.id).write_text(record.model_dump_json(), encoding="utf-8")
    return record.id


def load_analysis(record_id: str) -> AnalysisRecord:
    return AnalysisRecord.model_validate_json(_path(record_id).read_text(encoding="utf-8"))


def list_analyses() -> list[AnalysisRecordMeta]:
    d = _ensure_dir()
    metas: list[AnalysisRecordMeta] = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            metas.append(AnalysisRecordMeta(
                id=data["id"],
                created_at=data["created_at"],
                input_url=data["input_url"],
                profile_name=data["profile"]["name"],
                competitor_count=len(data["rows"]),
            ))
        except Exception:
            continue
    return metas


def delete_analysis(record_id: str) -> None:
    _path(record_id).unlink(missing_ok=True)
