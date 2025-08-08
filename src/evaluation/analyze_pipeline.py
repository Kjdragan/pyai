#!/usr/bin/env python3
"""
Research Pipeline Evaluation: API coverage, efficiency, redundancy, and quote retention

- Scans state snapshots in `src/logs/state/`
- Scans log files in `src/logs/`
- Correlates items across snapshots by URL (if available) to estimate quote retention pre/post cleaning
- Generates a Markdown report in `evaluation_reports/`

Usage:
  python3 src/evaluation/analyze_pipeline.py [--logs_dir src/logs] [--state_dir src/logs/state] [--out_dir evaluation_reports]

Notes:
- Designed to be robust to missing fields (e.g., when cleaning has not run yet).
- Quote detection counts double quotes and curly double quotes to estimate presence and retention.
- No external API calls are made.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -------------- Constants --------------
DEFAULT_LOGS_DIR = Path("src/logs")
DEFAULT_STATE_DIR = Path("src/logs/state")
DEFAULT_OUT_DIR = Path("evaluation_reports")

DOUBLE_QUOTE_CHARS = ['"', '“', '”']  # basic set to catch common quotes

# -------------- Utilities --------------

def read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_files(directory: Path, pattern: str) -> List[Path]:
    return sorted(directory.glob(pattern)) if directory.exists() else []


def parse_timestamp_from_state_filename(name: str) -> Optional[dt.datetime]:
    # Expect pattern: master_state_<uuid>_YYYYMMDD_HHMMSS.json
    m = re.search(r"_(\d{8})_(\d{6})\.json$", name)
    if not m:
        return None
    datestr, timestr = m.group(1), m.group(2)
    try:
        return dt.datetime.strptime(f"{datestr}_{timestr}", "%Y%m%d_%H%M%S")
    except Exception:
        return None


def count_quotes(text: Optional[str]) -> int:
    if not text:
        return 0
    return sum(text.count(ch) for ch in DOUBLE_QUOTE_CHARS)


def extract_url_like(item: Dict[str, Any]) -> Optional[str]:
    # Try common fields
    for key in ("url", "source_url", "link", "href", "page_url"):
        if key in item and isinstance(item[key], str) and item[key].startswith("http"):
            return item[key]
    # Fallback: search inside metadata
    meta = item.get("metadata")
    if isinstance(meta, dict):
        for key in ("url", "source_url", "link", "href", "page_url"):
            val = meta.get(key)
            if isinstance(val, str) and val.startswith("http"):
                return val
    return None


# -------------- State analysis --------------

def analyze_states(state_dir: Path) -> Dict[str, Any]:
    state_files = list_files(state_dir, "*.json")
    snapshots: List[Tuple[Path, Optional[dt.datetime], Dict[str, Any]]] = []

    for f in state_files:
        data = read_json_file(f)
        if not isinstance(data, dict):
            continue
        ts = parse_timestamp_from_state_filename(f.name)
        snapshots.append((f, ts, data))

    # Sort by timestamp ascending (oldest first)
    snapshots.sort(key=lambda t: (t[1] or dt.datetime.min))

    # Metrics
    total_items = 0
    cleaned_items = 0
    items_with_quotes_after = 0
    quote_retention_records: List[Dict[str, Any]] = []
    total_reduction_chars = 0
    reduction_count = 0

    # Correlate by URL across earliest and latest snapshots to estimate quote retention
    earliest_by_url: Dict[str, Dict[str, Any]] = {}
    latest_by_url: Dict[str, Dict[str, Any]] = {}

    for _, _, snap in snapshots:
        # Try to locate research items list
        research_items = None
        # Supported structures:
        # 1) { "research_data": [ ...items... ] }
        # 2) { "research_data": { "results": [ ...items... ] } }
        # 3) { "master_state": { "research_data": [ ...items... ] } }
        # 4) { "master_state": { "research_data": { "results": [ ...items... ] } } }
        if isinstance(snap.get("research_data"), list):
            research_items = snap["research_data"]
        elif isinstance(snap.get("research_data"), dict):
            rd = snap["research_data"]
            if isinstance(rd.get("results"), list):
                research_items = rd["results"]
        elif isinstance(snap.get("master_state"), dict):
            ms = snap["master_state"]
            if isinstance(ms.get("research_data"), list):
                research_items = ms["research_data"]
            elif isinstance(ms.get("research_data"), dict):
                rd = ms["research_data"]
                if isinstance(rd.get("results"), list):
                    research_items = rd["results"]

        if not isinstance(research_items, list):
            continue

        for item in research_items:
            if not isinstance(item, dict):
                continue
            url = extract_url_like(item) or f"item-{id(item)}"
            content = item.get("scraped_content")
            content_cleaned = item.get("content_cleaned")
            orig_len = item.get("original_content_length")
            clean_len = item.get("cleaned_content_length")

            # Track earliest and latest snapshots for each URL
            earliest_by_url.setdefault(url, item)
            latest_by_url[url] = item

    # Aggregate totals from latest snapshot view
    for url, item in latest_by_url.items():
        total_items += 1
        content = item.get("scraped_content")
        if item.get("content_cleaned") is True:
            cleaned_items += 1
        if count_quotes(content) > 0:
            items_with_quotes_after += 1
        # Reduction where lengths provided
        orig_len = item.get("original_content_length")
        clean_len = item.get("cleaned_content_length")
        if isinstance(orig_len, int) and isinstance(clean_len, int) and orig_len >= 0 and clean_len >= 0:
            total_reduction_chars += max(0, orig_len - clean_len)
            reduction_count += 1

    # Quote retention across earliest vs latest
    for url, earliest in earliest_by_url.items():
        latest = latest_by_url.get(url)
        if not latest:
            continue
        early_text = earliest.get("scraped_content")
        late_text = latest.get("scraped_content")
        early_quotes = count_quotes(early_text)
        late_quotes = count_quotes(late_text)
        # Only meaningful if we see a transition to cleaned or content changes
        was_cleaned = bool(latest.get("content_cleaned"))
        if early_text != late_text or was_cleaned:
            denom = early_quotes if early_quotes > 0 else None
            retention_pct = (100.0 * late_quotes / denom) if denom else None
            quote_retention_records.append({
                "url": url,
                "early_quotes": early_quotes,
                "late_quotes": late_quotes,
                "retention_pct": retention_pct,
                "was_cleaned": was_cleaned,
            })

    avg_reduction = (total_reduction_chars / reduction_count) if reduction_count else None

    return {
        "state_files_count": len(state_files),
        "total_items_latest": total_items,
        "cleaned_items_latest": cleaned_items,
        "items_with_quotes_after": items_with_quotes_after,
        "avg_char_reduction": avg_reduction,
        "quote_retention_records": quote_retention_records,
    }


# -------------- Log analysis --------------

def analyze_logs(logs_dir: Path) -> Dict[str, Any]:
    log_files = list_files(logs_dir, "*.log")

    tavily_posts = 0
    serper_posts = 0
    openai_posts = 0
    dedup_skips = 0
    dedup_urls = set()

    # Efficiency from Start -> Returning dict
    run_durations: List[float] = []

    # Cleaning metrics from logs
    cleaning_batches: List[int] = []  # number of results mentioned in "Starting content cleaning for X Tavily results"

    # Patterns
    tavily_pat = re.compile(r"https://api\.tavily\.com/search")
    serper_pat = re.compile(r"serper|google\.serper", re.IGNORECASE)
    openai_pat = re.compile(r"https://api\.openai\.com/v1/chat/completions")
    dedup_pat = re.compile(r"DEDUPLICATION: Skipping duplicate URL from .*?:\s*(\S+)")
    start_research_pat = re.compile(r"Starting research for query:")
    return_dict_pat = re.compile(r"Returning dict with .* raw results")
    cleaning_start_pat = re.compile(r"Starting content cleaning for (\d+) Tavily results")

    for lf in log_files:
        try:
            text = lf.read_text(encoding="utf-8")
        except Exception:
            continue

        # API posts
        tavily_posts += len(tavily_pat.findall(text))
        serper_posts += len(serper_pat.findall(text))
        openai_posts += len(openai_pat.findall(text))

        # Dedup URLs
        for m in dedup_pat.finditer(text):
            url = m.group(1)
            dedup_urls.add(url)
            dedup_skips += 1

        # Durations per file (approx by first start -> last return)
        # Use timestamps inside JSON lines if present ("timestamp": "2025-..."), else relative.
        starts = []
        returns = []
        for line in text.splitlines():
            if start_research_pat.search(line):
                ts = extract_timestamp_from_json_line(line)
                starts.append(ts)
            if return_dict_pat.search(line):
                ts = extract_timestamp_from_json_line(line)
                returns.append(ts)
            ms = cleaning_start_pat.search(line)
            if ms:
                try:
                    cleaning_batches.append(int(ms.group(1)))
                except Exception:
                    pass
        if starts and returns:
            # Use earliest start and latest return per file
            s = min([t for t in starts if t is not None] or [None])
            e = max([t for t in returns if t is not None] or [None])
            if s and e:
                run_durations.append((e - s).total_seconds())

    avg_duration = sum(run_durations) / len(run_durations) if run_durations else None
    avg_cleaning_batch = sum(cleaning_batches) / len(cleaning_batches) if cleaning_batches else None

    return {
        "log_files_count": len(log_files),
        "api_usage": {
            "tavily_posts": tavily_posts,
            "serper_posts": serper_posts,
            "openai_posts": openai_posts,
        },
        "dedup": {
            "skips": dedup_skips,
            "unique_urls": len(dedup_urls),
        },
        "efficiency": {
            "avg_run_duration_seconds": avg_duration,
            "avg_cleaning_batch_size": avg_cleaning_batch,
        },
    }


def extract_timestamp_from_json_line(line: str) -> Optional[dt.datetime]:
    # Try to parse a JSON object and read its "timestamp"; else None
    try:
        obj = json.loads(line.strip())
        ts = obj.get("timestamp")
        if isinstance(ts, str):
            # 2025-08-07T23:35:12.770529
            try:
                return dt.datetime.fromisoformat(ts)
            except Exception:
                pass
    except Exception:
        pass
    return None


# -------------- Report generation --------------

def generate_report(state_stats: Dict[str, Any], log_stats: Dict[str, Any], analyzed_at: dt.datetime) -> str:
    def fmt(v: Any) -> str:
        if v is None:
            return "N/A"
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    # Quote retention summary
    qrecs = state_stats.get("quote_retention_records", [])
    with_denominator = [r for r in qrecs if r.get("retention_pct") is not None]
    avg_retention = (
        sum(r["retention_pct"] for r in with_denominator) / len(with_denominator)
        if with_denominator else None
    )

    lines = []
    lines.append(f"# Research Pipeline Evaluation Report\n")
    lines.append(f"Generated: {analyzed_at.isoformat()}\n")

    lines.append("## Summary\n")
    lines.append(f"- State snapshots analyzed: {state_stats.get('state_files_count', 0)}")
    lines.append(f"- Log files analyzed: {log_stats.get('log_files_count', 0)}")
    lines.append(f"- Items in latest snapshot: {state_stats.get('total_items_latest', 0)}")
    lines.append(f"- Cleaned items (latest): {state_stats.get('cleaned_items_latest', 0)}")
    lines.append(f"- Items with quotes after cleaning (latest): {state_stats.get('items_with_quotes_after', 0)}")
    lines.append(f"- Avg character reduction (where available): {fmt(state_stats.get('avg_char_reduction'))}")
    lines.append(f"- Avg quote retention across matched items: {fmt(avg_retention)}%\n")

    lines.append("## API Coverage\n")
    api = log_stats.get("api_usage", {})
    lines.append(f"- Tavily POSTs: {api.get('tavily_posts', 0)}")
    lines.append(f"- Serper indicators: {api.get('serper_posts', 0)}")
    lines.append(f"- OpenAI chat completions: {api.get('openai_posts', 0)}\n")

    lines.append("## Efficiency\n")
    eff = log_stats.get("efficiency", {})
    lines.append(f"- Avg run duration (s): {fmt(eff.get('avg_run_duration_seconds'))}")
    lines.append(f"- Avg cleaning batch size: {fmt(eff.get('avg_cleaning_batch_size'))}\n")

    lines.append("## Redundancy\n")
    dd = log_stats.get("dedup", {})
    lines.append(f"- Deduplication skips: {dd.get('skips', 0)}")
    lines.append(f"- Unique duplicate URLs: {dd.get('unique_urls', 0)}\n")

    lines.append("## Quote Retention Details\n")
    if not qrecs:
        lines.append("No matched items across snapshots to estimate quote retention.\n")
    else:
        # Show up to 20 records for brevity
        for r in qrecs[:20]:
            url = r.get("url", "(unknown)")
            lines.append(f"- URL: {url}")
            lines.append(
                f"  - Early quotes: {r.get('early_quotes', 0)}, Late quotes: {r.get('late_quotes', 0)}, "
                f"Retention%: {fmt(r.get('retention_pct'))}, Cleaned: {r.get('was_cleaned')}"
            )
        if len(qrecs) > 20:
            lines.append(f"...and {len(qrecs) - 20} more\n")

    lines.append("## Recommendations\n")
    lines.append("- Ensure cleaning prompts explicitly preserve quoted statements and figures.")
    lines.append("- Consider storing raw scraped content separately (e.g., `raw_content`) to avoid overwriting.")
    lines.append("- Add explicit unit tests that assert presence of quotes before and after cleaning for sample items.")
    lines.append("- Track per-item cleaning outcomes in logs (e.g., quotes before/after) to improve diagnostics.")
    lines.append("- Continue deduplication logging; consider surfacing duplicate ratios per source (Tavily/Serper).\n")

    return "\n".join(lines) + "\n"


# -------------- Main --------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs_dir", type=Path, default=DEFAULT_LOGS_DIR)
    parser.add_argument("--state_dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--out_dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    analyzed_at = dt.datetime.now()

    state_stats = analyze_states(args.state_dir)
    log_stats = analyze_logs(args.logs_dir)

    report = generate_report(state_stats, log_stats, analyzed_at)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"evaluation_report_{analyzed_at.strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(report, encoding="utf-8")

    print(f"Wrote evaluation report to: {out_path}")


if __name__ == "__main__":
    main()
