from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class SavedQuery:
    name: str
    prompt: str
    sql: str


def load_queries(path: str) -> List[SavedQuery]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text())
        return [SavedQuery(**item) for item in raw]
    except Exception:
        return []


def save_queries(path: str, queries: List[SavedQuery]) -> None:
    p = Path(path)
    p.write_text(json.dumps([asdict(q) for q in queries], indent=2))


def upsert_query(path: str, q: SavedQuery) -> List[SavedQuery]:
    items = load_queries(path)
    by_name: Dict[str, SavedQuery] = {i.name: i for i in items}
    by_name[q.name] = q
    out = list(by_name.values())
    save_queries(path, out)
    return out
