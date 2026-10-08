"""Deterministic audit rules. Each finding gets an id that stays the same between runs, so the
tracker can tell which issues are new, still open, or fixed."""

from __future__ import annotations

import re

from .models import Issue, Profile, Report

PENALTY = {"high": 12, "medium": 6, "low": 2}
BUZZWORDS = [
    "results-driven", "passionate", "team player", "hard-working", "hardworking", "motivated", "detail-oriented",
    "dynamic", "synergy", "go-getter", "self-starter", "thought leader", "guru", "ninja", "rockstar", "think outside the box",
]  # fmt: skip
CONTACT_HINT = re.compile(r"@|open to|reach (me|out)|contact|get in touch|let'?s (talk|connect|chat)|dm me", re.I)
METRIC = re.compile(r"\d")
RECENT_POSITIONS = 3  # only nag about the most recent roles; old ones matter less
GAP_MONTHS = 12


def audit(profile: Profile) -> Report:
    issues: list[Issue] = []

    def add(rule: str, severity: str, section: str, message: str, fix: str, subject: str = "") -> None:
        issues.append(Issue(f"{rule}:{subject}" if subject else rule, rule, severity, section, message, fix))

    _headline(profile, add)
    _summary(profile, add)
    _experience(profile, add)
    _other(profile, add)

    score = max(0, 100 - sum(PENALTY[i.severity] for i in issues))
    order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: (order[i.severity], i.id))
    return Report(score, issues)


def _buzz(text: str) -> list[str]:
    low = text.lower()
    return [b for b in BUZZWORDS if b in low]


def _headline(p: Profile, add) -> None:
    h = p.headline.strip()
    if not h:
        add("headline.missing", "high", "headline", "No headline.", "Write a headline: role, specialty, and the value you deliver.")
    elif len(h) < 40:
        add(
            "headline.short", "medium", "headline", f"Headline is only {len(h)} characters; it looks like a bare job title.",
            "Use the 220-character limit: add your specialty, key skills, and who you help.",
        )  # fmt: skip
    if found := _buzz(h):
        add(
            "headline.buzzwords",
            "low",
            "headline",
            f"Headline uses filler words: {', '.join(found)}.",
            "Replace them with concrete skills or outcomes.",
        )


def _summary(p: Profile, add) -> None:
    s = p.summary.strip()
    if not s:
        add(
            "summary.missing",
            "high",
            "about",
            "The About section is empty.",
            "Write 3-5 short paragraphs: who you are, what you do best, proof, and how to reach you.",
        )
        return
    if len(s) < 300:
        add(
            "summary.short",
            "medium",
            "about",
            f"About section is only {len(s)} characters.",
            "Aim for 800-1,500 characters with a clear story and concrete results.",
        )
    elif len(s) > 2600:
        add(
            "summary.long",
            "low",
            "about",
            f"About section is {len(s)} characters; most readers stop early.",
            "Tighten it and put the strongest points in the first 3 lines.",
        )
    if not CONTACT_HINT.search(s):
        add(
            "summary.no_cta",
            "low",
            "about",
            "About section has no call to action or contact route.",
            "End with what you're open to and how to reach you.",
        )
    if found := _buzz(s):
        add(
            "summary.buzzwords",
            "low",
            "about",
            f"About section uses filler words: {', '.join(found)}.",
            "Show these qualities through specific examples instead.",
        )


def _months_between(a, b) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def _experience(p: Profile, add) -> None:
    if not p.positions:
        add(
            "experience.none",
            "high",
            "experience",
            "No work experience listed.",
            "Add your roles, including internships and notable projects.",
        )
        return
    for pos in p.positions[:RECENT_POSITIONS]:
        label = f"{pos.title or 'Role'} at {pos.company or 'company'}"
        desc = pos.description.strip()
        if not desc:
            add(
                "experience.no_description",
                "high",
                "experience",
                f"{label} has no description.",
                "Add 3-5 bullets on scope and outcomes.",
                pos.key,
            )
            continue
        if len(desc) < 150:
            add(
                "experience.thin",
                "medium",
                "experience",
                f"{label} has a very short description ({len(desc)} chars).",
                "Describe scope, actions, and results.",
                pos.key,
            )
        if not METRIC.search(desc):
            add(
                "experience.no_metrics",
                "medium",
                "experience",
                f"{label} has no numbers.",
                "Quantify impact: revenue, users, time saved, team size, percentages.",
                pos.key,
            )
        if found := _buzz(desc):
            add(
                "experience.buzzwords",
                "low",
                "experience",
                f"{label} uses filler words: {', '.join(found)}.",
                "Replace with specific achievements.",
                pos.key,
            )

    dated = sorted((x for x in p.positions if x.start_date), key=lambda x: x.start_date)
    for prev, nxt in zip(dated, dated[1:]):
        end = prev.end_date
        if end and (gap := _months_between(end, nxt.start_date)) > GAP_MONTHS:
            add(
                "experience.gap", "low", "experience", f"{gap}-month gap between {prev.company} and {nxt.company}.",
                "If intentional, add a line about study, freelance, caregiving, or projects from that period.", f"{prev.key}>{nxt.key}",
            )  # fmt: skip


def _other(p: Profile, add) -> None:
    if not p.skills:
        add("skills.missing", "high", "skills", "No skills listed.", "Add 10+ skills that match the roles you want, and pin the top 3.")
    elif len(p.skills) < 5:
        add(
            "skills.few",
            "medium",
            "skills",
            f"Only {len(p.skills)} skills listed.",
            "Add at least 10 relevant skills; recruiters search on them.",
        )
    if not p.education:
        add("education.missing", "medium", "education", "No education listed.", "Add your education or relevant training.")
    if not p.location:
        add("location.missing", "medium", "basics", "No location set.", "Set a location; recruiters filter by it.")
    if not p.industry:
        add("industry.missing", "low", "basics", "No industry set.", "Choose the industry you want to be found in.")
    if not p.websites:
        add("websites.missing", "low", "basics", "No website or portfolio link.", "Link a portfolio, GitHub, or personal site.")
    if p.recommendations_received == 0:
        add(
            "recommendations.none",
            "low",
            "social proof",
            "No recommendations received.",
            "Ask 2-3 former managers or colleagues for a recommendation.",
        )
