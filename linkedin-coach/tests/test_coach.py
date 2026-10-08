import json
from datetime import datetime, timezone

from linkedin_coach.cli import main
from linkedin_coach.loader import load_profile
from linkedin_coach.models import Position, Profile, parse_month
from linkedin_coach.rules import audit
from linkedin_coach.suggest import suggest
from linkedin_coach.tracker import Tracker


def strong() -> Profile:
    return Profile(
        name="A", headline="Backend engineer | Python, distributed systems | helping fintechs scale payments reliably",
        summary="I build payment systems. " * 20 + " Reach me at a@example.com.",
        industry="Software", location="Chennai", websites=["https://a.dev"], education=["IIT"],
        skills=[f"s{i}" for i in range(12)], recommendations_received=2,
        positions=[Position("Acme", "Eng", "Cut p99 latency by 40% across 12 services. " * 5, started="Jan 2022")],
    )  # fmt: skip


def ids(report):
    return {i.id for i in report.issues}


def test_strong_profile_scores_100():
    r = audit(strong())
    assert r.score == 100 and not r.issues


def test_empty_profile_flags_core_sections():
    r = audit(Profile())
    assert {"headline.missing", "summary.missing", "experience.none", "skills.missing"} <= ids(r)
    assert r.issues[0].severity == "high"


def test_position_rules_use_stable_ids():
    p = strong()
    p.positions[0].description = "Built backend services."
    assert {"experience.thin:Acme|Eng", "experience.no_metrics:Acme|Eng"} <= ids(audit(p))


def test_buzzwords_and_gap():
    p = strong()
    p.headline = "Passionate ninja engineer with a long enough headline to pass"
    p.positions = [
        Position("New", "Eng", "Did 5 things. " * 20, started="Jan 2022"),
        Position("Old", "Eng", "Did 5 things. " * 20, started="Jan 2018", finished="Jan 2019"),
    ]
    got = ids(audit(p))
    assert "headline.buzzwords" in got
    assert "experience.gap:Old|Eng>New|Eng" in got


def test_parse_month_formats():
    assert parse_month("Jan 2020").month == 1
    assert parse_month("2020-03").month == 3
    assert parse_month("2020").year == 2020
    assert parse_month("garbage") is None


def test_tracker_reports_new_fixed_and_ignored(tmp_path):
    t = Tracker(tmp_path / "s.json")
    p = Profile()
    d1 = t.record(audit(p), datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert "headline.missing" in d1.new

    p.headline = "Backend engineer | Python, distributed systems | helping fintechs scale"
    t2 = Tracker(tmp_path / "s.json")
    d2 = t2.record(audit(p))
    assert "headline.missing" in d2.fixed and d2.previous_score is not None

    assert t2.ignore("skills.missing")
    r = audit(p)
    Tracker(tmp_path / "s.json").record(r)
    assert "skills.missing" not in ids(r)


def test_fixed_issue_that_returns_counts_as_new(tmp_path):
    t = Tracker(tmp_path / "s.json")
    t.record(audit(Profile()))
    t.record(audit(strong()))
    assert "headline.missing" in Tracker(tmp_path / "s.json").record(audit(Profile())).new


def test_loader_reads_linkedin_export(tmp_path):
    (tmp_path / "Profile.csv").write_text(
        'First Name,Last Name,Headline,Summary,Geo Location\nA,B,Dev,Hi,"Chennai"\n', encoding="utf-8-sig"
    )
    (tmp_path / "positions.csv").write_text("Company Name,Title,Description,Location,Started On,Finished On\nAcme,Eng,Did x,,Jan 2022,\n")
    (tmp_path / "Skills.csv").write_text("Name\nPython\nSQL\n")
    p = load_profile(tmp_path)
    assert (p.name, p.headline, p.skills) == ("A B", "Dev", ["Python", "SQL"])
    assert p.positions[0].is_current


def test_suggest_uses_injected_client_and_prompts_with_issues():
    seen = {}

    class Block:
        type, text = "text", "better headline"

    class Client:
        class messages:
            @staticmethod
            def create(**kw):
                seen.update(kw)
                return type("M", (), {"content": [Block()]})()

    p = Profile(headline="Dev")
    assert suggest(p, audit(p), client=Client()) == "better headline"
    assert "Headline is only" in seen["messages"][0]["content"]
    assert "Never invent" in seen["system"]


def test_cli_audit_roundtrip(tmp_path, capsys):
    prof = tmp_path / "p.json"
    prof.write_text(json.dumps({"headline": "Dev"}))
    state = str(tmp_path / "state.json")
    assert main(["--state", state, "audit", str(prof), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["score"] < 100
    assert main(["--state", state, "history"]) == 0
    assert main(["--state", state, "ignore", "nope"]) == 1
