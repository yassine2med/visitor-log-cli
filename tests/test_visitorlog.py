import json
from datetime import datetime
from pathlib import Path

import pytest

from visitorlog import log
from visitorlog.cli import main

EX = Path(__file__).resolve().parent.parent / "examples"


def t(text):
    return datetime.strptime(text, log.FMT)


def test_badges_increment():
    visits = []
    a = log.check_in(visits, "Ana Cruz", "Acme", "Lee", "Meeting", t("2026-11-20 09:00"))
    b = log.check_in(visits, "Bo Diaz", "", "Lee", "", t("2026-11-20 09:05"))
    assert (a.badge, b.badge) == ("V0001", "V0002")


def test_name_and_host_required():
    with pytest.raises(log.LogError):
        log.check_in([], " ", "", "Lee", "", t("2026-11-20 09:00"))
    with pytest.raises(log.LogError):
        log.check_in([], "Ana", "", "", "", t("2026-11-20 09:00"))


def test_double_check_in_blocked():
    visits = []
    log.check_in(visits, "Ana Cruz", "", "Lee", "", t("2026-11-20 09:00"))
    with pytest.raises(log.LogError, match="already on site"):
        log.check_in(visits, "ana cruz", "", "Lee", "", t("2026-11-20 09:10"))


def test_return_visit_after_checkout_allowed():
    visits = []
    log.check_in(visits, "Ana Cruz", "", "Lee", "", t("2026-11-20 09:00"))
    log.check_out(visits, "V0001", t("2026-11-20 10:00"))
    again = log.check_in(visits, "Ana Cruz", "", "Lee", "", t("2026-11-21 09:00"))
    assert again.badge == "V0002"


def test_checkout_by_badge_and_minutes():
    visits = []
    log.check_in(visits, "Ana Cruz", "", "Lee", "", t("2026-11-20 09:00"))
    v = log.check_out(visits, "v0001", t("2026-11-20 10:30"))
    assert v.minutes() == 90 and not v.on_site


def test_checkout_by_partial_name():
    visits = []
    log.check_in(visits, "Ana Cruz", "", "Lee", "", t("2026-11-20 09:00"))
    assert log.check_out(visits, "cruz", t("2026-11-20 09:30")).badge == "V0001"


def test_ambiguous_name_needs_badge():
    visits = []
    log.check_in(visits, "Ana Cruz", "", "Lee", "", t("2026-11-20 09:00"))
    log.check_in(visits, "Ana Diaz", "", "Lee", "", t("2026-11-20 09:00"))
    with pytest.raises(log.LogError, match="matches 2"):
        log.check_out(visits, "Ana", t("2026-11-20 10:00"))


def test_checkout_errors():
    visits = []
    log.check_in(visits, "Ana Cruz", "", "Lee", "", t("2026-11-20 09:00"))
    with pytest.raises(log.LogError, match="before check in"):
        log.check_out(visits, "V0001", t("2026-11-20 08:00"))
    log.check_out(visits, "V0001", t("2026-11-20 10:00"))
    with pytest.raises(log.LogError, match="already checked out"):
        log.check_out(visits, "V0001", t("2026-11-20 11:00"))
    with pytest.raises(log.LogError, match="no visitor"):
        log.check_out(visits, "Zed", t("2026-11-20 11:00"))


def test_bad_time_rejected():
    with pytest.raises(log.LogError):
        log.parse_time("tomorrow")


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "v.csv"
    visits = []
    log.check_in(visits, "Ana, Jr.", "Acme \"Co\"", "Lee", "Tour", t("2026-11-20 09:00"))
    log.save(p, visits)
    assert log.load(p) == visits


def test_load_rejects_foreign_csv(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(log.LogError):
        log.load(p)


def test_select_filters():
    visits = log.load(EX / "visitors.csv")
    assert len(visits) == 5
    assert len(log.select(visits, on_site=True)) == 2
    assert len(log.select(visits, day=datetime(2026, 11, 19).date())) == 2


def test_export_formats():
    visits = log.load(EX / "visitors.csv")
    rows = log.export_csv(visits).splitlines()
    assert rows[0].endswith(",minutes") and len(rows) == 6
    data = json.loads(log.export_json(visits))
    assert data[0]["minutes"] == 75 and data[-1]["minutes"] is None


def test_cli_flow(tmp_path, capsys):
    f = str(tmp_path / "v.csv")
    assert main(["--file", f, "checkin", "Ana Cruz", "--host", "Lee", "--at", "2026-11-20 09:00"]) == 0
    assert "badge V0001" in capsys.readouterr().out
    assert main(["--file", f, "list", "--on-site"]) == 0
    assert "Ana Cruz" in capsys.readouterr().out
    assert main(["--file", f, "checkout", "V0001", "--at", "2026-11-20 09:45"]) == 0
    assert "45 minute(s)" in capsys.readouterr().out
    out = tmp_path / "o.json"
    assert main(["--file", f, "export", "--format", "json", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))[0]["minutes"] == 45


def test_cli_error_exit_codes(tmp_path, capsys):
    f = str(tmp_path / "v.csv")
    assert main(["--file", f, "checkout", "V0009"]) == 1
    bad = tmp_path / "bad.csv"
    bad.write_text("x\n", encoding="utf-8")
    assert main(["--file", str(bad), "list"]) == 2
    assert main(["--file", f, "list", "--date", "soon"]) == 1
