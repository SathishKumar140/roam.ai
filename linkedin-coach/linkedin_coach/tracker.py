"""Persist issue history between runs so each audit reports what changed."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .models import Report

DEFAULT_STATE = Path(".linkedin-coach/state.json")


@dataclass
class Diff:
    new: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    still_open: list[str] = field(default_factory=list)
    previous_score: int | None = None


class Tracker:
    def __init__(self, path: Path = DEFAULT_STATE):
        self.path = Path(path)
        self.data = {"runs": [], "issues": {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def ignored(self) -> set[str]:
        return {i for i, v in self.data["issues"].items() if v["status"] == "ignored"}

    def record(self, report: Report, now: datetime | None = None) -> Diff:
        """Store this run. Issues the user has chosen to ignore are dropped from the report in place."""
        now_s = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        ignored = self.ignored()
        report.issues = [i for i in report.issues if i.id not in ignored]
        issues = self.data["issues"]
        current = {i.id for i in report.issues}
        prev_open = {k for k, v in issues.items() if v["status"] == "open"}
        diff = Diff(previous_score=self.data["runs"][-1]["score"] if self.data["runs"] else None)

        for issue in report.issues:
            entry = issues.get(issue.id)
            if entry is None or entry["status"] == "fixed":
                issues[issue.id] = {"status": "open", "first_seen": now_s, "message": issue.message, "severity": issue.severity}
                diff.new.append(issue.id)
            else:
                entry["message"] = issue.message
                diff.still_open.append(issue.id)
        for key in sorted(prev_open - current):
            issues[key].update(status="fixed", fixed_at=now_s)
            diff.fixed.append(key)

        self.data["runs"].append({"at": now_s, "score": report.score, "open": len(current)})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        return diff

    def ignore(self, issue_id: str) -> bool:
        if issue_id not in self.data["issues"]:
            return False
        self.data["issues"][issue_id]["status"] = "ignored"
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        return True
