# LinkedIn Coach

Audits your LinkedIn profile, remembers what it found, and on each re-run tells you which issues are new, which you fixed, and how your score moved. Optionally asks Claude for ready-to-paste rewrites.

## How it connects to LinkedIn

LinkedIn has no public API for reading your own full profile, and scraping breaks its terms. This tool uses the official route instead:

1. LinkedIn > Settings > Data privacy > **Get a copy of your data**. Pick Profile, Positions, Education, Skills (and optionally Certifications and Recommendations).
2. Unzip the download. That folder is the input.

Or write a `profile.json` by hand (see `examples/profile.json`).

## Use

```bash
python -m linkedin_coach audit  ~/Downloads/linkedin-export     # score + issues, diffed against last run
python -m linkedin_coach suggest ~/Downloads/linkedin-export    # same, plus Claude rewrites
python -m linkedin_coach history                                # score over time
python -m linkedin_coach ignore headline.short                  # stop reporting something you disagree with
```

The loop: audit, fix the top three issues on LinkedIn, export again, audit again. State lives in `.linkedin-coach/state.json`.

`suggest` needs `pip install anthropic` and `ANTHROPIC_API_KEY`; set `LINKEDIN_COACH_MODEL` to change the model. It sends your profile text to the Anthropic API and tells the model not to invent facts (metrics come back as `[X%]` placeholders for you to fill in). Everything else runs locally with no dependencies.

## What it checks

Headline (missing, bare job title, filler words), About (missing, short, long, no call to action), the three most recent roles (no description, thin, no numbers, filler words), employment gaps over 12 months, skills, education, location, industry, website, recommendations. Rules live in `linkedin_coach/rules.py`.

## Test

```bash
pip install pytest && python -m pytest
```
