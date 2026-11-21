"""Visitor log stored in one CSV file."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from pathlib import Path

FMT = "%Y-%m-%d %H:%M"
FIELDS = ["badge", "name", "company", "host", "purpose", "checked_in", "checked_out"]


class LogError(Exception):
    """A problem the user can fix: bad input, unknown badge, double checkout."""


@dataclass
class Visit:
    badge: str
    name: str
    company: str
    host: str
    purpose: str
    checked_in: str
    checked_out: str = ""

    @property
    def on_site(self) -> bool:
        return not self.checked_out

    def minutes(self) -> int | None:
        if not self.checked_out:
            return None
        delta = datetime.strptime(self.checked_out, FMT) - datetime.strptime(self.checked_in, FMT)
        return int(delta.total_seconds() // 60)


def parse_time(text: str) -> datetime:
    try:
        return datetime.strptime(text, FMT)
    except ValueError:
        raise LogError(f"bad time '{text}', use YYYY-MM-DD HH:MM") from None


def load(path: Path) -> list[Visit]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != FIELDS:
            raise LogError(f"{path} is not a visitor log (unexpected columns)")
        return [Visit(**{k: row[k] for k in FIELDS}) for row in reader]


def save(path: Path, visits: list[Visit]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for v in visits:
            writer.writerow(asdict(v))


def next_badge(visits: list[Visit]) -> str:
    numbers = [int(v.badge[1:]) for v in visits if v.badge[1:].isdigit()]
    return f"V{(max(numbers) + 1) if numbers else 1:04d}"


def check_in(visits: list[Visit], name: str, company: str, host: str, purpose: str, when: datetime) -> Visit:
    name = name.strip()
    if not name:
        raise LogError("visitor name is required")
    if not host.strip():
        raise LogError("host is required")
    for v in visits:
        if v.on_site and v.name.lower() == name.lower():
            raise LogError(f"{name} is already on site with badge {v.badge}")
    visit = Visit(next_badge(visits), name, company.strip(), host.strip(), purpose.strip(), when.strftime(FMT))
    visits.append(visit)
    return visit


def find_on_site(visits: list[Visit], key: str) -> Visit:
    key_l = key.strip().lower()
    for v in visits:
        if v.badge.lower() == key_l and v.on_site:
            return v
    matches = [v for v in visits if v.on_site and key_l in v.name.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise LogError(f"'{key}' matches {len(matches)} visitors on site, use the badge number")
    for v in visits:
        if v.badge.lower() == key_l:
            raise LogError(f"{v.name} ({v.badge}) already checked out")
    raise LogError(f"no visitor on site matches '{key}'")


def check_out(visits: list[Visit], key: str, when: datetime) -> Visit:
    visit = find_on_site(visits, key)
    if when < datetime.strptime(visit.checked_in, FMT):
        raise LogError("checkout time is before check in")
    visit.checked_out = when.strftime(FMT)
    return visit


def select(visits: list[Visit], on_site: bool = False, day: date | None = None,
           start: date | None = None, end: date | None = None) -> list[Visit]:
    out = []
    for v in visits:
        d = datetime.strptime(v.checked_in, FMT).date()
        if on_site and not v.on_site:
            continue
        if day and d != day:
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue
        out.append(v)
    return out


def export_csv(visits: list[Visit]) -> str:
    import io
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(FIELDS + ["minutes"])
    for v in visits:
        m = v.minutes()
        writer.writerow([getattr(v, f) for f in FIELDS] + ["" if m is None else m])
    return buf.getvalue()


def export_json(visits: list[Visit]) -> str:
    rows = []
    for v in visits:
        row = asdict(v)
        row["minutes"] = v.minutes()
        rows.append(row)
    return json.dumps(rows, indent=2) + "\n"


assert [f.name for f in fields(Visit)] == FIELDS
