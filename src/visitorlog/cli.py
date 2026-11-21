"""Command line entry for the visitor log."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from . import log

DEFAULT_LOG = "visitors.csv"


def _day(text: str) -> date:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise log.LogError(f"bad date '{text}', use YYYY-MM-DD") from None


def _when(text: str | None) -> datetime:
    return log.parse_time(text) if text else datetime.now().replace(second=0, microsecond=0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="visitorlog", description="Front desk visitor log kept in one CSV file.")
    p.add_argument("--file", default=DEFAULT_LOG, help=f"log file (default {DEFAULT_LOG})")
    sub = p.add_subparsers(dest="command", required=True)
    cin = sub.add_parser("checkin", help="sign a visitor in and print the badge number")
    cin.add_argument("name")
    cin.add_argument("--company", default="")
    cin.add_argument("--host", required=True, help="person being visited")
    cin.add_argument("--purpose", default="")
    cin.add_argument("--at", help='time, for example "2026-11-20 09:15" (default now)')
    cout = sub.add_parser("checkout", help="sign a visitor out by badge number or name")
    cout.add_argument("who")
    cout.add_argument("--at", help="time (default now)")
    ls = sub.add_parser("list", help="show visits")
    ls.add_argument("--on-site", action="store_true", help="only visitors still on site")
    ls.add_argument("--date", help="only visits that started on YYYY-MM-DD")
    ex = sub.add_parser("export", help="write visits as csv or json, with minutes on site")
    ex.add_argument("--format", choices=["csv", "json"], default="csv")
    ex.add_argument("--from", dest="start", help="first day, YYYY-MM-DD")
    ex.add_argument("--to", dest="end", help="last day, YYYY-MM-DD")
    ex.add_argument("--out", help="output file (default: print)")
    return p


def _table(visits: list[log.Visit]) -> str:
    rows = [f"{'badge':<7}{'name':<18}{'host':<14}{'in':<17}{'out':<17}"]
    for v in visits:
        rows.append(f"{v.badge:<7}{v.name:<18}{v.host:<14}{v.checked_in:<17}{v.checked_out or 'on site':<17}")
    rows.append(f"{len(visits)} visit(s)")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    """Return 0 on success, 1 when the request cannot be done, 2 for a bad log file."""
    args = build_parser().parse_args(argv)
    path = Path(args.file)
    try:
        visits = log.load(path)
    except (log.LogError, OSError, UnicodeDecodeError) as exc:
        print(f"Cannot read log: {exc}", file=sys.stderr)
        return 2
    try:
        if args.command == "checkin":
            v = log.check_in(visits, args.name, args.company, args.host, args.purpose, _when(args.at))
            log.save(path, visits)
            print(f"Checked in {v.name}: badge {v.badge} at {v.checked_in}")
        elif args.command == "checkout":
            v = log.check_out(visits, args.who, _when(args.at))
            log.save(path, visits)
            print(f"Checked out {v.name}: badge {v.badge} after {v.minutes()} minute(s)")
        elif args.command == "list":
            day = _day(args.date) if args.date else None
            print(_table(log.select(visits, on_site=args.on_site, day=day)))
        else:
            start = _day(args.start) if args.start else None
            end = _day(args.end) if args.end else None
            chosen = log.select(visits, start=start, end=end)
            text = log.export_csv(chosen) if args.format == "csv" else log.export_json(chosen)
            if args.out:
                Path(args.out).write_text(text, encoding="utf-8", newline="")
                print(f"Wrote {len(chosen)} visit(s) to {args.out}")
            else:
                print(text, end="")
    except log.LogError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
