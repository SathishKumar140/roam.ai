from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_month(text: str) -> date | None:
    """Parse the date shapes LinkedIn emits: 'Jan 2020', 'January 2020', '2020-01', '2020'."""
    text = (text or "").strip().lower()
    if not text:
        return None
    if m := re.fullmatch(r"([a-z]{3})[a-z]*\.?\s+(\d{4})", text):
        month = _MONTHS.get(m.group(1))
        return date(int(m.group(2)), month, 1) if month else None
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})(?:-\d{1,2})?", text):
        month = int(m.group(2))
        return date(int(m.group(1)), month, 1) if 1 <= month <= 12 else None
    if m := re.fullmatch(r"(\d{4})", text):
        return date(int(m.group(1)), 1, 1)
    return None


@dataclass
class Position:
    company: str = ""
    title: str = ""
    description: str = ""
    location: str = ""
    started: str = ""
    finished: str = ""  # empty means current

    @property
    def key(self) -> str:
        return f"{self.company}|{self.title}"

    @property
    def start_date(self) -> date | None:
        return parse_month(self.started)

    @property
    def end_date(self) -> date | None:
        return parse_month(self.finished)

    @property
    def is_current(self) -> bool:
        return not self.finished.strip()


@dataclass
class Profile:
    name: str = ""
    headline: str = ""
    summary: str = ""
    industry: str = ""
    location: str = ""
    websites: list[str] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    recommendations_received: int = 0


@dataclass
class Issue:
    id: str  # stable across runs, e.g. "experience.no_metrics:Acme|Engineer"
    rule: str
    severity: str  # high | medium | low
    section: str
    message: str
    fix: str


@dataclass
class Report:
    score: int
    issues: list[Issue]
