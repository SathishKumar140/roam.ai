from __future__ import annotations

import argparse
import json
from pathlib import Path

from .loader import load_profile
from .rules import audit
from .suggest import suggest
from .tracker import DEFAULT_STATE, Tracker

ICON = {"high": "HIGH", "medium": "MED ", "low": "LOW "}


def _print_report(report, diff) -> None:
    trend = ""
    if diff.previous_score is not None:
        delta = report.score - diff.previous_score
        trend = f" ({'+' if delta >= 0 else ''}{delta} since last run)"
    print(f"Profile score: {report.score}/100{trend}")
    if diff.fixed:
        print(f"\nFixed since last run ({len(diff.fixed)}):")
        for key in diff.fixed:
            print(f"  ✓ {key}")
    if not report.issues:
        print("\nNo open issues. Nice work.")
        return
    print(f"\nOpen issues ({len(report.issues)}), most important first:")
    for i in report.issues:
        tag = "NEW " if i.id in diff.new else "    "
        print(f"  [{ICON[i.severity]}] {tag}{i.message}\n           -> {i.fix}\n           id: {i.id}")
    print("\nStart with the first three, update your profile, export again, and re-run.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="linkedin_coach", description=__doc__)
    ap.add_argument("--state", type=Path, default=DEFAULT_STATE, help="where issue history is stored")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="audit a LinkedIn export folder or profile.json and track changes")
    a.add_argument("path")
    a.add_argument("--json", action="store_true")
    s = sub.add_parser("suggest", help="audit, then ask Claude for rewrites (needs ANTHROPIC_API_KEY)")
    s.add_argument("path")
    sub.add_parser("history", help="show score over time")
    ig = sub.add_parser("ignore", help="stop reporting an issue you disagree with")
    ig.add_argument("issue_id")
    args = ap.parse_args(argv)

    tracker = Tracker(args.state)
    if args.cmd == "history":
        for run in tracker.data["runs"]:
            print(f"{run['at']}  score {run['score']:>3}  open {run['open']}")
        return 0
    if args.cmd == "ignore":
        if not tracker.ignore(args.issue_id):
            print(f"Unknown issue id: {args.issue_id}")
            return 1
        print(f"Ignoring {args.issue_id}")
        return 0

    profile = load_profile(args.path)
    report = audit(profile)
    diff = tracker.record(report)
    if args.cmd == "audit" and args.json:
        print(json.dumps({"score": report.score, "issues": [vars(i) for i in report.issues], "fixed": diff.fixed}, indent=2))
    else:
        _print_report(report, diff)
    if args.cmd == "suggest":
        print("\n" + "=" * 60 + "\n" + suggest(profile, report))
    return 0
