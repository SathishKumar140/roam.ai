"""Ask Claude for rewrites that address the open issues. Optional: needs `pip install anthropic`
and ANTHROPIC_API_KEY. Only the profile text you point the tool at is sent."""

from __future__ import annotations

import os

from .models import Profile, Report

SYSTEM = (
    "You are a LinkedIn profile coach. Rewrite only what the listed issues call for. "
    "Never invent employers, titles, dates, or numbers. Where a metric is needed, use a placeholder such as [X%] "
    "and tell the user to fill it with the real figure. Keep the person's voice; avoid buzzwords."
)
MAX_ISSUES = 6


def build_prompt(profile: Profile, report: Report) -> str:
    lines = [f"Name: {profile.name}", f"Headline: {profile.headline}", f"About: {profile.summary}", "Positions:"]
    for p in profile.positions[:3]:
        lines.append(f"- {p.title} at {p.company} ({p.started} - {p.finished or 'present'}): {p.description}")
    lines.append(f"Skills: {', '.join(profile.skills)}")
    lines.append("\nOpen issues, most important first:")
    for i in report.issues[:MAX_ISSUES]:
        lines.append(f"- [{i.severity}] {i.message} Fix: {i.fix}")
    lines.append("\nFor each issue, give a ready-to-paste rewrite and one sentence on why it helps.")
    return "\n".join(lines)


def suggest(profile: Profile, report: Report, client=None) -> str:
    if not report.issues:
        return "No open issues, nothing to rewrite."
    if client is None:
        import anthropic  # lazy: the rest of the tool works without it

        client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.environ.get("LINKEDIN_COACH_MODEL", "claude-sonnet-5-5"),
        max_tokens=2000,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(profile, report)}],
    )
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
