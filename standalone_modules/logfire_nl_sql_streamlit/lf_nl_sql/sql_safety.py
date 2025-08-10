from __future__ import annotations

import re
import logging

_SINGLE_LINE_COMMENT = re.compile(r"--.*?(\n|$)")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RISKY = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|call|execute|merge)\b", re.IGNORECASE)


def _strip_comments(sql: str) -> str:
    sql = _BLOCK_COMMENT.sub(" ", sql)
    sql = _SINGLE_LINE_COMMENT.sub(" ", sql)
    return sql


def _strip_wrapping(sql: str) -> str:
    # Trim whitespace and redundant trailing semicolons
    s = sql.strip()
    while s.endswith(";"):
        s = s[:-1].rstrip()
    return s


def ensure_safe_select(sql: str) -> str:
    """Ensure the SQL is a single, read-only SELECT statement.

    - Removes comments and trailing semicolons.
    - Validates it starts with SELECT.
    - Rejects queries containing risky keywords.
    - Rejects multiple statements separated by semicolons.
    Returns the sanitized SQL string, or raises ValueError.
    """
    if not sql or not sql.strip():
        raise ValueError("SQL is empty")

    cleaned = _strip_wrapping(_strip_comments(sql))

    # No internal semicolons allowed after cleanup
    if ";" in cleaned:
        raise ValueError("Multiple statements are not allowed")

    # Must start with SELECT (allow leading parenthesis/CTEs are allowed only if start with 'with' or 'select')
    start = cleaned.lstrip().lower()
    if not (start.startswith("select") or start.startswith("with ")):
        raise ValueError("Only SELECT queries are allowed")

    # Disallow risky keywords anywhere
    if _RISKY.search(cleaned):
        raise ValueError("Disallowed SQL keyword detected")

    return cleaned


def autopatch_sql(sql: str) -> tuple[str, list[str]]:
    """Apply non-destructive patches to improve SQL compatibility.

    Current patches:
    - Replace unsupported approx_percentile(... with approx_percentile_cont(...)

    Returns (patched_sql, notes)
    """
    notes: list[str] = []
    out = sql

    # Replace approx_percentile( with approx_percentile_cont(
    if re.search(r"\bapprox_percentile\s*\(", out, flags=re.IGNORECASE):
        out = re.sub(r"\bapprox_percentile\s*\(", "approx_percentile_cont(", out, flags=re.IGNORECASE)
        notes.append("Replaced approx_percentile with approx_percentile_cont")

    # Convert two-arg form to ordered-set syntax:
    #   approx_percentile_cont(expr, 0.95)  -> approx_percentile_cont(0.95) WITHIN GROUP (ORDER BY expr)
    # Also handles when the function name was approx_percentile originally.
    def _to_ordered_set(m: re.Match[str]) -> str:
        expr = m.group("expr").strip()
        pct = m.group("pct").strip()
        return f"approx_percentile_cont({pct}) WITHIN GROUP (ORDER BY {expr})"

    pattern_two_args = re.compile(
        r"\b(?:approx_percentile_cont|approx_percentile)\s*\(\s*(?P<expr>[^,]+?)\s*,\s*(?P<pct>[0-9]*\.?[0-9]+)\s*\)",
        flags=re.IGNORECASE,
    )
    if pattern_two_args.search(out):
        out_new = pattern_two_args.sub(_to_ordered_set, out)
        if out_new != out:
            out = out_new
            notes.append("Rewrote approx_percentile_cont(expr, pct) to ordered-set WITHIN GROUP syntax (regex)")

    # Robust pass: parse and rewrite any remaining two-arg calls with nested parentheses/newlines
    func_pat = re.compile(r"\b(?:approx_percentile_cont|approx_percentile)\s*\(", flags=re.IGNORECASE)

    def _is_number(s: str) -> bool:
        return bool(re.fullmatch(r"[0-9]*\.?[0-9]+", s.strip()))

    s = out
    i = 0
    changed = False
    while True:
        m = func_pat.search(s, i)
        if not m:
            break
        # find matching closing parenthesis
        # locate the '(' character
        paren_idx = s.find("(", m.start())
        if paren_idx == -1:
            i = m.end()
            continue
        depth = 0
        j = paren_idx
        end_idx = -1
        while j < len(s):
            ch = s[j]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    end_idx = j
                    break
            j += 1
        if end_idx == -1:
            i = m.end()
            continue
        args_str = s[paren_idx + 1 : end_idx]
        # split by top-level comma
        parts = []
        buf = []
        depth2 = 0
        for ch in args_str:
            if ch == '(':
                depth2 += 1
            elif ch == ')':
                depth2 -= 1
            if ch == ',' and depth2 == 0:
                parts.append(''.join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        parts.append(''.join(buf).strip())

        if len(parts) == 2 and _is_number(parts[1]):
            expr = parts[0]
            pct = parts[1]
            replacement = f"approx_percentile_cont({pct}) WITHIN GROUP (ORDER BY {expr})"
            s = s[: m.start()] + replacement + s[end_idx + 1 :]
            i = m.start() + len(replacement)
            changed = True
        else:
            i = end_idx + 1

    if changed:
        out = s
        notes.append("Rewrote approx_percentile*_two-arg into ordered-set syntax (parser)")

    if notes:
        logging.getLogger(__name__).info("autopatch_sql applied: %s", "; ".join(notes))
    return out, notes
