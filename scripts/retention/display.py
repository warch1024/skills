"""Human-readable listing and safe selection parsing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .model import SessionRecord


class SelectionError(ValueError):
    """Raised when a numbered selection is malformed or out of range."""


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def format_local_time(timestamp_ms: int) -> str:
    if timestamp_ms <= 0:
        return "unknown"
    local = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).astimezone()
    return local.isoformat(timespec="seconds")


def _path_status(record: SessionRecord) -> str:
    paths = "; ".join(str(path) for path in record.paths) or "missing"
    if record.ambiguous:
        return f"AMBIGUOUS: {paths}"
    return paths


def format_session_table(
    records: list[SessionRecord], *, cutoff_ms: int, days: int
) -> str:
    recent = [record for record in records if not record.is_stale(cutoff_ms)]
    stale = [record for record in records if record.is_stale(cutoff_ms)]
    lines = [
        f"cutoff: {format_local_time(cutoff_ms)}",
        f"最近 {days} 天，共 {len(recent)} 个",
        "编号  ID                                    最后活动时间                 来源             标题  路径/状态  文件数  记录数  空间",
    ]
    for number, record in enumerate(records, start=1):
        if record.is_stale(cutoff_ms):
            break
        lines.append(_format_row(number, record))
    lines.extend(
        [
            "",
            f"-------------------- 大于 {days} 天，共 {len(stale)} 个 --------------------",
            "编号  ID                                    最后活动时间                 来源             标题  路径/状态  文件数  记录数  空间",
        ]
    )
    for number, record in enumerate(records, start=1):
        if record.is_stale(cutoff_ms):
            lines.append(_format_row(number, record))
    return "\n".join(lines)


def _format_row(number: int, record: SessionRecord) -> str:
    return (
        f"{number:>4}  {record.session_id:<36}  {format_local_time(record.last_activity_ms):<28} "
        f"{record.activity_source:<16} {record.title!r:<24} {_path_status(record):<60} "
        f"{record.file_count:>5}  {record.record_count:>6}  {format_bytes(record.size_bytes):>10}"
    )


def parse_selection(text: str, maximum: int) -> tuple[int, ...]:
    if not text.strip():
        raise SelectionError("selection is empty")
    selected: list[int] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            raise SelectionError("empty selection token")
        if "-" in token:
            pieces = token.split("-")
            if len(pieces) != 2 or not all(piece.strip().isdigit() for piece in pieces):
                raise SelectionError(f"invalid range: {token}")
            start, end = (int(piece.strip()) for piece in pieces)
            if start > end:
                raise SelectionError(f"reversed range: {token}")
            values = list(range(start, end + 1))
        elif token.isdigit():
            values = [int(token)]
        else:
            raise SelectionError(f"invalid number: {token}")
        for value in values:
            if value < 1 or value > maximum:
                raise SelectionError(f"number out of range: {value}")
            if value in selected:
                raise SelectionError(f"duplicate number: {value}")
            selected.append(value)
    return tuple(selected)


__all__ = [
    "SelectionError",
    "format_bytes",
    "format_local_time",
    "format_session_table",
    "parse_selection",
]
