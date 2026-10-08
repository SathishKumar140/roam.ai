"""Load a profile from a LinkedIn data export (folder of CSVs) or a hand-written JSON file.

LinkedIn offers no public API for reading your own full profile, and scraping breaks its terms.
The supported route is Settings > Data privacy > Get a copy of your data, which yields the CSVs read here.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Position, Profile


def load_profile(path: str | Path) -> Profile:
    path = Path(path)
    if path.is_dir():
        return _from_export(path)
    if path.suffix.lower() == ".json":
        return _from_json(json.loads(path.read_text(encoding="utf-8")))
    raise ValueError(f"{path}: expected a LinkedIn export folder or a .json file")


def _rows(folder: Path, name: str) -> list[dict[str, str]]:
    match = next((p for p in folder.iterdir() if p.name.lower() == name.lower()), None)
    if match is None:
        return []
    with match.open(newline="", encoding="utf-8-sig") as fh:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def _from_export(folder: Path) -> Profile:
    prof = (_rows(folder, "Profile.csv") or [{}])[0]
    return Profile(
        name=f"{prof.get('First Name', '')} {prof.get('Last Name', '')}".strip(),
        headline=prof.get("Headline", ""),
        summary=prof.get("Summary", ""),
        industry=prof.get("Industry", ""),
        location=prof.get("Geo Location", "") or prof.get("Address", ""),
        websites=[w for w in prof.get("Websites", "").replace("[", "").replace("]", "").split(",") if w.strip()],
        positions=[
            Position(
                company=r.get("Company Name", ""),
                title=r.get("Title", ""),
                description=r.get("Description", ""),
                location=r.get("Location", ""),
                started=r.get("Started On", ""),
                finished=r.get("Finished On", ""),
            )
            for r in _rows(folder, "Positions.csv")
        ],
        education=[r.get("School Name", "") for r in _rows(folder, "Education.csv") if r.get("School Name")],
        skills=[r["Name"] for r in _rows(folder, "Skills.csv") if r.get("Name")],
        certifications=[r["Name"] for r in _rows(folder, "Certifications.csv") if r.get("Name")],
        recommendations_received=len(_rows(folder, "Recommendations_Received.csv")),
    )


def _from_json(data: dict) -> Profile:
    positions = [
        Position(
            company=p.get("company", ""),
            title=p.get("title", ""),
            description=p.get("description", ""),
            location=p.get("location", ""),
            started=p.get("started", ""),
            finished=p.get("finished", ""),
        )
        for p in data.get("positions", [])
    ]
    return Profile(
        name=data.get("name", ""),
        headline=data.get("headline", ""),
        summary=data.get("summary", ""),
        industry=data.get("industry", ""),
        location=data.get("location", ""),
        websites=list(data.get("websites", [])),
        positions=positions,
        education=list(data.get("education", [])),
        skills=list(data.get("skills", [])),
        certifications=list(data.get("certifications", [])),
        recommendations_received=int(data.get("recommendations_received", 0)),
    )
