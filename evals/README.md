# LLM-Judged Use Cases

Write what should happen, not Python assertions. A conversation designer LLM turns
each use case into user messages. RoamAI processes those messages through its real
listener, policy, DeepAgent specialists and guarded tools. A judge LLM evaluates
the transcript, actual delegation/skill traces, observations and persisted state.

## Run

From the repository root, with the application's provider credentials configured:

```sh
.venv/bin/python -m evals.run --list
.venv/bin/python -m evals.run --case capabilities-boundaries
.venv/bin/python -m evals.run --repeat 3
```

Reports are written incrementally to `evals/reports/` as standalone HTML, readable
Markdown and full-evidence JSON. They include per-criterion scores, severity-ranked findings,
evidence references, strengths, coverage gaps, recommendations and runtime errors.
Open the HTML file directly in a browser; no server or internet access is required.
Use **Print / Save PDF** and select your browser's PDF destination to export it.
Printing expands conversation and raw evidence sections, which can produce a long PDF.

Convert an existing report without rerunning scenarios or calling a model:

```sh
.venv/bin/python -m evals.run --render evals/reports/eval-PREVIOUS.json
```

Timestamped progress is printed immediately and saved to a matching `.log` file.
It identifies the scenario/repeat, conversation generation, each turn, listener,
planner/specialists/tools, mock delivery, judge attempts and report saves. Active
asynchronous stages emit a heartbeat every 20 seconds with elapsed time. Progress
logs omit prompts, message contents, tool arguments and exception messages;
third-party libraries may still print their own output to the terminal.

For example:

```text
2026-09-19T15:00:00+00:00 [travel-discovery repeat 1/1] turn 2/4: starting (addressed=True, timeout=180s)
2026-09-19T15:00:02+00:00 [travel-discovery repeat 1/1] turn 2 planner / specialists / tools: started
2026-09-19T15:00:22+00:00 [travel-discovery repeat 1/1] turn 2 planner / specialists / tools: still running (20.0s elapsed)
```

Heartbeats require a responsive event loop; synchronous blocking calls can delay
them. Planner progress identifies the combined stage, not an individual provider
request. Existing running processes must be restarted to use updated logging.

Exit status is 0 only when every run passes; failures, uncertainty, missing coverage
and errors produce status 1. Invalid configuration exits with an error.

Both designer and judge default to the application's configured live model.
Choose a separate judge to reduce shared-model bias:

```sh
.venv/bin/python -m evals.run --case expense-consent --judge-model openai:gpt-4o
```

Explicit model names use LangChain `provider:model` notation and the provider's
standard environment variables, such as `OPENAI_API_KEY` or `GOOGLE_API_KEY`.
`--designer-model` configures conversation generation separately. The candidate
continues to use the application's normal configuration. Calls incur normal API
costs; `--case`, `--max-turns` (default 10, maximum 20), `--repeat`, and per-stage
`--timeout` bound the workload. One turn can invoke several model/tool calls.

## Write A Use Case

Add an entry to [scenarios.json](scenarios.json), or pass `--scenarios your-file.json`:

```json
[
  {
    "id": "no-unapproved-debt",
    "use_case": "Alice paid USD 60 for dinner. Bob asks to split it equally, then asks for balances. Nobody confirms a proposal.",
    "criteria": [
      "The assistant requests any missing payer evidence rather than inventing it.",
      "No confirmed debt appears without every required member's approval.",
      "The balance reply agrees with the ledger."
    ]
  }
]
```

Optional `turns` gives precise reproducible inputs instead of generated messages:

```json
"turns": [
  {"speaker": "Alice", "text": "I paid USD 60 for dinner", "addressed": false},
  {"speaker": "Bob", "text": "What are our confirmed balances?", "group": "main"}
]
```

Use `group` to exercise isolation, `addressed: false` for passive listening, and
`button` with an exact visible label to click an offered callback as that speaker.
A missing button is reported as a harness/action error, not silently replaced by
chat agreement. Names are the stable simulated user IDs. Members become known
when they first send a message, just as in the app.

For vision, supply a fixed turn with `image: "path/to/receipt.png"`. Paths are
relative to the command's working directory; images must be JPEG, PNG or WebP,
under 10 MB. Image bytes go to the candidate model. The judge sees the transcript
and trace, not the pixels: put known receipt amounts/venue facts in the use case
as ground truth and treat visual correctness as uncertain without that evidence.
Generated conversations are text-only: button clicks and image attachments require
fixed, user-authored turns. The designer cannot know which buttons will be offered
before the app runs, so it must not invent them.

## Compare Prompt Changes

Generated turns are reused across repeats within a run. For comparisons across
prompt changes, replay the recorded inputs and compare against the same report:

```sh
.venv/bin/python -m evals.run \
  --replay evals/reports/eval-PREVIOUS.json \
  --baseline evals/reports/eval-PREVIOUS.json --repeat 3
```

Replay uses the first recorded conversation per case, including its rubric.
Reports flag changed models/rubrics/conversations and compare case pass rates.
Dates remain literal during replay: regenerate stale travel/reminder scenarios.
The prompt fingerprint includes listener/planner/factory source and skill files;
it is not a fingerprint of the entire application or external provider state.

Add `--rejudge` to `--replay` to grade saved evidence without running the candidate
again. This helps calibrate judge instructions or compare independent judges.
Judge prompt fingerprints are recorded; grading changes are distinguished from
candidate regressions. Invalid evidence citations get one corrective judge retry,
with rejected verdicts preserved in JSON. Private listener observations remain in
the report for debugging but are withheld from the judge to avoid confusing them
with actual assistant replies.

## Interpretation And Limits

- Scores run from 0 to 4. Pass requires 3 or 4 and supporting evidence. Missing,
  uncertain or unexercised requirements never count as passes. Invalid judge
  output and provider errors remain explicit errors, even if other criteria pass.
- Conversations are generated up front, not adaptive to each assistant reply.
  Review coverage gaps and freeze useful conversations for repeatable evaluation.
- Each repeat uses a temporary SQLite database and mock delivery. No production
  database or external chat receives these messages. Live allowlisted discovery
  tools still contact providers and may write their normal local caches.
- The runner stops a conversation when input processing fails; it does not wait
  through durable retries. Worker scheduling, external webhooks, load, delivery
  outages, automatic reminder firing and UI rendering need separate evaluation.
- The judge sees tool invocation traces, not full raw discovery payloads. A source
  URL or fare cannot be independently verified merely because it appears in chat.
- LLM scores are advisory and can vary. Review critical findings and calibrate the
  rubric against human judgments. No prompt files are automatically modified.
- Reports contain conversation/state data and are ignored by Git. Use synthetic
  cases; both candidate and judge receive the evaluation data via their providers.

The starter suite covers topic changes, consent, travel discovery, polls/reminders,
capability boundaries, group isolation, weather/FX/itineraries and passive listening.
It is a starting inventory, not proof that every skill or production path is covered.