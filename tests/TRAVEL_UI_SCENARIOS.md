# Travel Topic Switching: Live UI Verification

Run date: 2026-09-18. Application: http://127.0.0.1:8000.

The [DeepAgent restoration](#deepagent-restoration) below is the latest result.
Earlier runs and the 55/100 review are retained as historical evidence, not current status.

## DeepAgent Restoration

Date: 2026-09-18. `GroupPlanner` now calls the scoped `create_roamai_companion` factory.
The supervisor uses native DeepAgent task delegation, planning and progressive skill loading.
Specialists receive isolated conversations, the same topic-scoped request snapshot and only
their authorized tool subset. Read-only virtual skill files replace host filesystem access;
no shell, file writes, unscoped ledger, global image cache or chat-driven MCP installation is exposed.
Follow-up cleanup removed the legacy adapter, singleton and no-argument factory fallback.
The factory now requires explicit scoped tools; former compatibility tests use that same path.

### Automated Verification

**156 passed, four external-provider integrations deselected, zero xfails.**

```bash
.venv/bin/python -m pytest tests/test_roamai_listener.py tests/test_normalization.py tests/test_deepagents_skills.py tests/test_mcp_client.py tests/test_travelassistant_mcp.py -k 'not test_travelassistant_geocoder and not test_travelassistant_weather and not test_travelassistant_finance and not test_travelassistant_flights_and_hotels' -q
```

New cases execute actual DeepAgent graphs with scripted chat models, not mocked graph factories:
- Supervisor-to-specialist handoff and tool execution.
- All 14 active skill files advertised by native SkillsMiddleware and read inside delegated tasks.
- Rejection of legacy expense/confirmation, MCP installation, shell and file-write tools.
- Read-only delegation cannot regain an expense mutation tool.
- Nested discovery results retain citation provenance; a specialist's invented JSON URL is rejected.
- Expense delegation preserves payer amount/currency evidence, pending consent and exact stored amounts.
- Image analysis cannot fall back to another request's attachment.
- Balance rendering uses the ledger even when both specialist and supervisor invent another currency/amount.

### Live Evidence

Fresh simulator conversation: `web_deepagent_f410ea52-7355-4ad6-97cb-27e03f05eec0`.
Playwright used the real composer and speaker buttons, with DOM activation because the shared
browser is hidden. This is not a pointer-ergonomics or external-channel delivery test.

| Scenario | Actual trace and result |
| --- | --- |
| Capability query | `skill_specialist` -> read `mcp-acquisition`; correctly refused chat-driven server installation |
| Empty confirmed balances | `expense_specialist` -> `get_group_balances`; initially fabricated EUR 50 despite an empty ledger; fixed and reproduced in regression tests |
| USD 150 dinner for You and Bob | `expense_specialist` -> `propose_group_expense`; exact pending proposal with authenticated confirmation buttons |
| Separate badminton poll | `proactive_concierge` -> `create_group_poll`; Saturday/Sunday, 60-minute deadline |
| Balance retry after fix | `expense_specialist` -> `get_group_balances`; correctly reported no confirmed balances, without promoting pending debt |
| London LHR to Tokyo HND, 10-13 November 2026, one adult, GBP | `travel_specialist` -> read `flight-search` -> guarded flight searches; public Google Flights citation and unconfirmed-availability disclaimer |

Read-only SQLite assertions: all six inputs are done, one USD 150 expense remains pending with
zero approvals, and exactly one open poll contains the requested options. `/ready` returned 200.
A transient Gemini 503 high-demand response was retried; no inbox row failed in this run.
The initial incorrect balance reply remains in history as evidence; the run was not initially flawless.

The web composer does not upload images. Vision was verified separately through the active
planner with a generated receipt and a temporary database: `vision_specialist` -> read
`menu-receipt-ocr` -> `analyze_attached_image`. The live model returned USD 35 subtotal, USD 7 tax,
USD 42 total and created zero expenses. The first probe's assertions passed but its cleanup used
a nonexistent method; the corrected probe reran successfully with `mcp_manager.shutdown()`.

### Limits

All five specialist handoffs now have live evidence, but not every skill workflow is live-tested.
The native harness exposes skill indexes progressively; it does not guarantee the model reads
every skill on every turn. In this run, expense and poll tools were used without a separate skill read.
Live hotel, weather, FX, full itinerary, venue-scouting and reminder journeys were not rerun in this pass.
Dynamic acquisition is administrator-only; departure support is explicit reminders, not automatic
lifecycle transitions. Generated MCP skill files are not automatically exposed to group chat.
Flight fare units, every source claim and URL reachability remain unverified. Multi-step delegation
adds model calls and latency. No production-readiness score is assigned by this pass.

## Earlier Travel Run

Playwright drove the actual web composer, speaker picker, Address RoamAI checkbox,
and task buttons against the configured live model and discovery tools. No mocked
chat responses were used. All scenarios ran in one isolated simulator chat:
`web_travel_qa_1ca9a757-cc85-472e-b8ca-8278e0d5ddb8`.

The run contains 21 inbound messages, including retries and callbacks. The two
failed inbox records and the erroneous pre-fix poll remain as evidence; this is
not a clean all-green run. State inspection was read-only and scoped to this chat.

## Scenarios And Results

| Scenario | Expected | Observed result |
| --- | --- | --- |
| You introduces Tokyo, 10-13 November 2026, Alice + You, USD 900 ground budget, vegetarian food, trains | Record one trip without booking | Pass |
| Bob introduces solo Paris, 1-4 December 2026, EUR 220/night, seafood, taxis | Separate trip and preferences | Pass |
| You changes subject to a Saturday/Sunday badminton poll | Sports task separate from travel | Pass |
| You returns to Tokyo and changes only the ground budget to USD 1200 | Retain Tokyo's other facts | Initially failed twice due to invalid observer evidence IDs; passed after constraining IDs |
| Bob asks for his Paris details | No Tokyo dates, participants, currency, food or transport | Pass |
| Bob answers the earlier hotel offer without Address RoamAI | Continue Paris despite an intervening Tokyo turn | Pass |
| Paris hotel search for one adult | Preserve dates, currency and occupancy at provider boundary | Found ignored occupancy; fixed forwarding, tested it, and observed `adults=1` in refreshed provider links |
| Open hotel details | Public links, not authenticated API endpoints | Initial provider link returned Unauthorized; fixed normalization and verified public links in the UI |
| Alice proposes an unrelated JPY 6000 dinner split with You | New expense, not an automatic trip-budget change | Pass; both participant IDs recorded |
| Alice confirms, then You votes on the earlier badminton poll | Expense remains pending; vote belongs to the poll | Pass; only Alice appears in expense confirmations |
| You says "Make that 3" | Ask before changing state | Initially created a duplicate poll with an invented option. Added a non-mutating clarification path and active-poll guard; retest asked a question without another poll tool call |
| Return to Tokyo for vegetarian, train-friendly dining areas | Tokyo-only web discovery, no hotel/flight search | Topic routing passed; citation verification did not fully pass (see below) |
| Ask about Tokyo flights without an origin | Ask for departure city/airport | Initially guessed LAX and used SGD. Added inbound-evidence guard and removed default routes; retest asked for origin |
| Supply Chennai (MAA) as an unmentioned follow-up | Continue Tokyo with supplied origin and USD | First guard version re-asked because evidence selection remained unreliable. After constraining IDs, live flight search returned Chennai-to-Tokyo options in USD |
| Request a side-by-side recap without changing either trip | Preserve independent facts and no booking claims | Five exact Playwright table assertions passed; both statuses remained proposed |

## Final Asserted Recap

| Field | Tokyo | Paris |
| --- | --- | --- |
| Travelers | 2 | 1 |
| Dates | 10-13 Nov 2026 | 1-4 Dec 2026 |
| Budget | USD 1200 (ground) | EUR 220/night (hotel) |
| Food | Vegetarian | Seafood |
| Transport | Trains | Taxis |

SQLite inspection corroborated distinct Tokyo, Paris, dinner and sports topic IDs.
The comparison itself was saved as a separate summary topic. The dinner expense
remained pending, denominated in JPY, with Alice's confirmation only.

## Remaining Findings And Limits

- A generated Time Out dining citation returned 404. The Japan Guide link opened
  and supported transit information, but did not establish the vegetarian claim.
  Successful tool invocation alone does not guarantee grounded recommendations.
  Citation provenance and claim support remain open work.
- The ambiguity retest asked about a third poll option, influenced by the earlier
  erroneous conversation. It did not mutate tasks, but neutral clarification
  across every ambiguous context is not proven.
- The guard validates an origin quote against an inbound message, not full semantic
  ownership of every travel fact. Another trip's user-supplied origin still needs
  correct model routing. This run does not prove isolation for all conversations.
- This is a 21-message local simulator run, not a long-history, load, or external
  Telegram/WhatsApp delivery test. No bookings or payments were executed.
- Flight prices, per-person versus party-total interpretation, hotel availability,
  and every external source URL were not independently verified.
- Some Playwright pointer/scroll operations timed out in the integrated browser.
  Keyboard activation and DOM assertions completed the same UI workflows.

## Automated Regressions

47 focused tests passed after the fixes; editor diagnostics were clean.

```bash
.venv/bin/python -m pytest tests/test_roamai_listener.py tests/test_normalization.py tests/test_deepagents_skills.py tests/test_mcp_client.py tests/test_travelassistant_mcp.py::test_travelassistant_events tests/test_travelassistant_mcp.py::test_hotel_search_preserves_traveler_count_dates_and_currency tests/test_travelassistant_mcp.py::test_hotel_search_rejects_invalid_occupancy tests/test_travelassistant_mcp.py::test_flight_search_does_not_guess_route_and_preserves_travelers -q
```

These include observer evidence enums, non-mutating clarification, active-poll
uniqueness, user-sourced flight origins, and exact hotel/flight argument forwarding.
Provider forwarding tests mock HTTP; the browser scenarios above exercised live calls.

## Adversarial Self-Review

Date: 2026-09-18. Production code was not changed during this review. Only review
tests and this report were added. This is risk-based coverage, not an exhaustive
proof of all possible conversations or a security certification.

### Evidence And Scope

- A fresh live-model UI chat contained 17 submitted messages:
  `web_review_9a2302a6-e449-4737-83db-6ed5633b2ef5`.
- Playwright exercised the real React controls and backend. The hidden integrated
  browser did not deliver initial keyboard actions, so the completed run used
  DOM-activated controls, not direct chat API submissions. Pointer ergonomics were
  not assessed by that fallback.
- SQLite reads were limited to this synthetic chat. All 17 messages processed,
  but several responses and persisted values were functionally wrong.
- Added 21 review cases: 14 passed and 7 reproduced defects. Combined with the
  earlier focused suite: **61 passed, 7 strict expected failures**.
- The seven defect probes were also run with `--runxfail`; all seven produced
  ordinary assertion failures. They are not successful checks or skipped coverage.
- Existing datetime deprecation warnings remain; editor diagnostics were clean.

### Prioritized Findings

| ID | Priority | Reproduction and impact | Evidence / owner |
| --- | --- | --- | --- |
| R1 | High | A request to note Kyoto travel received an unrelated offer to recreate a rejected EUR 120 dinner expense. Stored trip separation does not prevent response-topic contamination. | Live UI; [planner receives the whole group context](../src/agents/group_planner.py#L138) |
| R2 | High | London-only seafood/taxi choices were persisted as global user preferences. The rejected instruction to bypass confirmation was also saved as `confirmation_method`; ephemeral split approval became another preference. This can contaminate later planning even though it did not bypass ledger consent in this run. | Live UI + SQLite; [preference key lacks topic scope](../src/storage/roamai.py#L40), [unfiltered model preference persistence](../src/services/roamai.py#L125) |
| R3 | High | A delta summary replaces the original trip facts. After 45 unrelated messages, dates were absent from the context; after 12 newer topics, an older active topic was absent. There is no retrieval step in this path to recover it. | Two failing deterministic probes; [message/topic limits](../src/storage/roamai.py#L146), [summary replacement](../src/storage/roamai.py#L187) |
| R4 | High | Alice reports paying; Bob says thanks before debounce ends. The offer is bound to Bob, so Alice's acceptance is refused as belonging to another member. | Live UI + failing probe; [recipient uses final event sender](../src/services/roamai.py#L138) |
| R5 | High | Alice says `$150`, identifies three participants, then agrees to send a proposal. No currency question is asked; the stored expense uses USD. The expense remains pending, but its currency was never established. | Live UI + SQLite; [expense tool boundary](../src/agents/group_planner.py#L80), [store validates format, not source](../src/storage/roamai.py#L335) |
| R6 | High | Both hotel and flight date helpers changed `2000-01-02` into `2027-01-02` instead of requiring clarification. A successful lookup could therefore answer a different date request. | Two failing probes; [flight dates](../src/mcp/travelassistant/flight_server.py#L85), [hotel dates](../src/mcp/travelassistant/hotel_server.py#L53) |
| R7 | Medium | The statement `Do NOT depart from Chennai` satisfies the departure quote guard for MAA. Quote presence is not affirmative intent, and does not prove ownership by the selected trip. | Failing boundary probe with a simulated provider; [quote guard](../src/agents/group_planner.py#L57). Not a claim that the live model always chooses this invalid call. |
| R8 | Medium | Bob rejects the split but is added to the `confirmed` list alongside Alice. The expense state correctly remains rejected and no balance is finalized, but the approval audit is misleading. | Live state + failing probe; [unconditional confirmation insertion](../src/storage/roamai.py#L372) |
| R9 | Medium | The earlier live restaurant recommendation included a 404 citation and another source that did not establish the dietary claim. Tool invocation is not source/claim validation. | Earlier live travel run on the same implementation; [unvalidated model response](../src/agents/group_planner.py#L150) |

### Positive And Negative Checks That Held

| Check | Result and coverage |
| --- | --- |
| Explicit expense proposal | Created a pending EUR 120 split for Alice and Bob in the live UI |
| Outsider attempts approval | Charlie's callback was refused in the live UI |
| One participant approves | Alice's approval did not finalize the split |
| Text tries to bypass approvals | The model refused; no confirmation was synthesized from text. However, the request polluted preference memory (R2) |
| Participant rejects, then replays an approval | The expense remained rejected; stale approval was refused. Audit-list defect is tracked separately (R8) |
| Request other chats, shell execution and MCP installation | Refused in the live UI; no prohibited tool execution observed. This tests one prompt, not all injection variants |
| Same speaker has two trip-specific preference sets | Short-chat Kyoto recap retained its vegetarian/train preferences, dates, travelers and updated USD 1400 budget after London. Long-history safety is not established |
| Insufficient expense participants | Asked for identities and whether the payer was included. Missing currency was not handled (R5) |
| Invalid amounts and currency syntax | Seven deterministic cases rejected negative, zero, NaN, infinity, invalid fractional precision and `$` as a currency code |
| Concurrent duplicate intake | 20 submissions across four threads produced one inbox entry |
| Repeated delivery failure | Stopped after six attempts and allowed the next response to proceed; existing tests verify delivery retry does not rerun the planner |
| Forged or tampered WhatsApp webhook | Rejected missing/invalid signatures; an authentic duplicate was persisted once in ASGI tests |
| Listener off / unapproved account | Passive intake refused; exact configured account/chat accepted in ASGI tests |
| Existing isolation and recovery checks | Group/account identities, cross-group task rejection, poll votes/expiry, confirmed balances, processing retry, chunk ordering and reminder restart cases remained passing |

### Confidence Score

**55/100: supervised development trial only; not ready for unattended use.**

This is a weighted engineering-readiness judgment for the requested behavior, not
a measured probability that 55% of requests will succeed. Unit-test pass counts
are not used as a success-rate estimate: their cases are selected, correlated,
and do not cover the full live-model behavior space.

| Area | Weight | Assessment | Main reason |
| --- | --- | --- | --- |
| Context, participation and memory | 30% | 40/100 | Wrong offer recipient, response-topic mixing, global preference pollution, bounded context loss |
| Consent and group isolation | 25% | 85/100 | Outsider/stale approvals and override attempts blocked; audit semantics still wrong |
| Travel and expense data accuracy | 20% | 40/100 | Guessed currency, changed dates, incomplete origin and citation validation |
| Durable processing and delivery | 15% | 75/100 | Focused retry, deduplication and recovery checks pass; real provider outage behavior remains untested |
| Production operations and channels | 10% | 25/100 | Local simulator and single-process SQLite only; external delivery and operational controls not proven |

Weighted total: `0.30*40 + 0.25*85 + 0.20*40 + 0.15*75 + 0.10*25 = 55`.

### What Would Raise Confidence

1. Bind offers to the intended participant using message evidence, not the final batch sender.
2. Store durable structured trip facts and topic-scoped preferences; reject security-policy and transaction-status data as preferences. Retrieve older topics on demand.
3. Give the planner selected-topic context and explicit comparison context, not unrestricted conversational carryover. Suppress unsolicited re-offers after rejection.
4. Require explicit currency and truthful date/route inputs before querying or proposing; show immutable amount/currency/participant details on confirmation controls.
5. Store approvals and rejections separately; validate citation provenance and support before presenting recommendations as verified.
6. Re-run the failed probes and repeat fresh live UI journeys, then validate external channels, downtime recovery, load, retention/deletion and operator recovery.

Unverified: long real-model histories beyond the fixture probes, large-group load,
actual Telegram/WhatsApp delivery and permissions, provider outages/rate limits,
media transcription/OCR, time-zone/DST edge cases, price-unit accuracy, quiet hours,
cross-platform identity linking, retention/deletion and comprehensive prompt-injection resistance.

To reproduce all review probes, including their actual failures:

```bash
.venv/bin/python -m pytest tests/test_roamai_listener.py -k review --runxfail -q --tb=short
```

At the time of that review, known defects were explicit `xfail(strict=True)` records.
The hardening work below removed all seven markers after fixing the corresponding probes.

## Post-Review Hardening

Date: 2026-09-18. Runtime fixes were authorized after the review. This section supersedes
the earlier readiness assessment without erasing the original failures.

### Implemented Changes

| Area | Change and verification |
| --- | --- |
| Topic state | Evidence-backed field updates, retained initial context, per-topic message history, older-topic visibility, and planner context limited to the selected topic. Tests cover long unrelated history, field merging, cross-topic evidence rejection, and group isolation. |
| Preferences | Supported-key allowlist, exact speaker/quote evidence, topic scope by default, and explicit wording required for global scope. Legacy unscoped preferences are preserved but excluded from trusted context. Tests reject confirmation-policy pollution and unauthorized/global attribution. |
| Comparisons | Only explicit comparison requests receive the named topics; the planner has no tools in this mode. Tests verify source topics stay unchanged and the actual graph tool list is empty. |
| Offer ownership | Recipient comes from the cited payment/help message. Ambiguous ownership suppresses the offer instead of selecting the final batch speaker. The original payer regression and live acceptance now pass. |
| Expense safety | Payer-authored topic-local currency evidence is required. Proposal details come from the stored record; rejected/pending expenses cannot be recreated under a new request in the same topic. Rejectors are not added to approvals. |
| Travel inputs | Invalid, missing, past and reversed dates fail before provider access. Departure evidence rejects negation, uncertainty, destination-only mentions and superseded source IDs. The English wording guard is conservative and may request clarification for legitimate phrasing. |
| Truthful fallback | Monthly searches require explicit month/year, forward adult count, label four-window sampling, and return unavailable rather than a hardcoded fare/flight. The active planner no longer falls back to legacy flight/hotel wrappers. |
| Citations | Response URLs must occur in structured tool results; invented or credential-bearing API URLs suppress the recommendation. This does not establish reachability or support for every factual claim. R9 is only partially addressed. |
| Provider compatibility | A live Gemini request rejected the expanded observer schema. Compacting transport-only annotations fixed the same input; full Pydantic validation and evidence enums remain. Tests check retained fields, enums and output bounds. |

### Automated Gate

**100 passed, zero xfails, four external-provider integration tests deselected.**
All seven original failing probes are now required passing tests. This is the focused
suite below, not a claim that every repository test or every provider path was run.
Editor diagnostics and `git diff --check` were clean. Existing datetime deprecation
warnings remain unrelated to these changes.

```bash
.venv/bin/python -m pytest tests/test_roamai_listener.py tests/test_normalization.py tests/test_deepagents_skills.py tests/test_mcp_client.py tests/test_travelassistant_mcp.py -k 'not test_travelassistant_geocoder and not test_travelassistant_weather and not test_travelassistant_finance and not test_travelassistant_flights_and_hotels' -q
```

### Fresh Live UI Journey

Chat: `web_fix_5f4263a9-5519-482b-bc52-b7f893358371`.
Playwright exercised React controls against the live model. As in the review, hidden-tab
controls were activated through DOM-backed clicks, not direct chat API submissions.

1. Alice passively reports EUR 120 dinner payment; Bob thanks her in the same batch.
2. Alice accepts the offer successfully, then confirms payer inclusion and the equal split.
3. The app displays the authoritative EUR 120 proposal for Alice and Bob. Bob rejects it.
4. A new Kyoto trip acknowledgment does not mention or re-offer that dinner expense.
5. The same user adds London-only seafood/taxi preferences and a GBP 180/night budget.
6. A Kyoto-only budget update to USD 1400 preserves April 10-14 2027, two people,
  vegetarian food and trains. Playwright asserts those facts and absence of London/dinner data.
7. Alice requests another split for `$150`. The model attempts a proposal, but the tool guard
  refuses it. The reply asks for currency; no expense or new confirmation buttons are created.
8. The first passive `USD` follow-up fails with a provider schema error after three attempts.
  It remains in the inbox as evidence. The exact read-only observer input succeeds after the
  schema fix, and a new UI `USD` message creates the correct pending USD 150 proposal.
9. An explicit read-only Kyoto/London comparison retains distinct dates, travelers, budgets,
  food and transport with no tool calls. All eight text assertions pass.

Read-only SQLite checks confirm separate topic IDs/facts, zero global preferences for this
chat, the EUR 120 expense rejected with an empty approval list, and the USD 150 expense
pending with no approvals. This was not a flawless first-pass run; the provider failure is
recorded above. No bookings, payments or external-channel messages were executed.

### Updated Assessment

**75/100: suitable for a supervised pilot, not unattended production.** This remains a
weighted engineering-readiness judgment, not a measured user-request success probability.

| Area | Weight | Assessment |
| --- | --- | --- |
| Context, participation and memory | 30% | 80/100 |
| Consent and group isolation | 25% | 90/100 |
| Travel and expense data accuracy | 20% | 75/100 |
| Durable processing and delivery | 15% | 75/100 |
| Production operations and channels | 10% | 25/100 |

Weighted total: `0.30*80 + 0.25*90 + 0.20*75 + 0.15*75 + 0.10*25 = 75.25`, rounded to 75.

Remaining risks at that checkpoint: topic selection and semantic fact extraction still use the model; literal
quotes do not prove arbitrary intent. Comparisons use an explicit English-language gate.
Older topics are retained in the observer catalog, not indexed for large-scale retrieval.
Previously overwritten facts cannot be restored automatically; old unscoped preferences
must be restated. Passive follow-ups that fail before observation can still fail silently.
Citation reachability/claim support, fare units, long live histories, external delivery,
provider outages, load, retention/deletion, quiet hours and operator recovery remain unproven.

## Reliability And Retrieval Pass

Date: 2026-09-18. This follow-up fixes additional reproducible gaps rather than increasing
the numeric score based on test count. The prior 75/100 assessment is not a production
certification; no new external-channel or full source-verification evidence was obtained.

### Changes And Evidence

| Area | Additional protection |
| --- | --- |
| Observer outages | Recent addressed questions are tracked before model execution, including clarification without a selected topic. If the observer exhausts retries, the responding member gets an error notice. Restart-based tests reject different-speaker and expired-question notifications. This marker grants no tool permission. |
| Financial evidence | Proposals require an exact payer-authored numeric quote in payment context. Four previously accepted bad cases now fail: USD 150 changed to 1500, year 2027 used as the amount, another speaker's amount, and substring 50 extracted from 150. A valid USD 150 proposal still succeeds. |
| Immutable retries | Reusing a proposal request cannot change amount, currency, payer or participants, including after partial approval. Existing terms and approvals remain intact. |
| Bounded retrieval | SQLite FTS5 retrieves matching and recent topics with a 20-topic observer cap. A named older trip is recovered among 101 topics after reopening storage. Search results remain group-scoped. Generic observer titles no longer overwrite a meaningful existing title. |
| Source retention | Messages supporting current structured facts survive the 80-message planner window. A fixture with 85 subsequent topic messages still provides the original departure evidence. |
| Busy groups | Every claimed message reaches the observer. A reproduced 50-message batch previously lost its first ten messages, including the payment author; all 50 are now present. Topic retrieval considers the claimed batch rather than only the final speaker. |
| Read-only requests | Explicit English refusal patterns remove mutation tools while retaining balances and discovery. Tests cover creation, sending, changes and reminders. This is a conservative boundary, not complete multilingual intent understanding. |
| Model initialization | The active listener/planner do not silently fall back to a fake model. Missing/failed live initialization produces an explicit processing failure. Legacy test callers retain their factory default. |
| Readiness | `/ready` checks workers, database access, model configuration and overdue queues; failed components return 503 without secrets. `/api/runtime` exposes aggregate queue diagnostics only in development. Provider connectivity remains explicitly unprobed. |

Eight additional failing cases were reproduced before their fixes. The final focused suite
contains **129 passing tests, zero xfails, four external-provider integration tests deselected**.
This adds 29 passing cases to the previous 100-test gate. The command in the previous section
is unchanged. Editor diagnostics and `git diff --check` passed. The whole repository suite,
production load and live external-channel failure recovery were not run.

### Fresh Live UI Check

Chat: `web_hardening_353a85cb-ea3b-4cf9-a1fa-2bd7c8a08980`.
Seven inbound UI messages completed, with no failed inbox rows. Playwright used the real
composer/speaker controls and live model; read-only SQLite assertions checked persisted state.

- Alice states `USD 150` and the year `2027`. The proposal is exactly USD 150, for Alice and Bob,
  pending with no approvals. No year or substring is used as the payment amount.
- An explicit no-new-tasks request reports that proposal as pending, with no mutation calls
  or new confirmation buttons.
- Tokyo and London remain distinct. Returning to Tokyo changes only its ground budget to
  USD 1600; November 10-13 2027, two travelers, vegetarian food and train travel remain intact.
- `Make that 3` asks whether the target is travelers, nights or something else. It invokes no
  tools and changes neither trip facts nor the pending expense. No polls or reminders exist.
- The running `/ready` endpoint returned 200 with workers, database, configuration and queues
  passing, and `provider_connectivity: not_probed`.

An initial browser assertion expected the literal word "trains" and rejected the correct
wording "train travel". The assertion was corrected and rerun; this was not an application
failure. The integrated browser's HTTP helper lacked a protocol command, so the readiness
GET used the page's ordinary fetch API; chat messages still used React controls.

### Remaining Release Gates

The new evidence improves bounded-memory behavior, failure visibility and tool safety, but
does not establish unattended readiness. Real Telegram/WhatsApp delivery, credential/quota
failures, sustained load, authenticated operator recovery, retention/deletion, quiet hours,
citation reachability and claim support remain open. Exact quotation does not prove all
natural-language semantics; the model still selects topics and extracts facts. Indexed
retrieval can miss vague older references, which must be clarified rather than guessed.
The payment wording and refusal guards are deliberately conservative English-language checks.