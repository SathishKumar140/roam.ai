"""Self-contained, escaped HTML rendering for recorded evaluations."""

import json
from collections import Counter
from html import escape


def text(value):
    return escape(str(value), quote=True)


def badge(value):
    tone = value if value in {"pass", "fail", "error", "incomplete", "critical", "high", "medium", "low"} else "incomplete"
    return f'<span class="badge {tone}">{text(value).replace("_", " ")}</span>'


def html_report(report):
    results = report["results"]
    counts = Counter(result["status"] for result in results)
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>RoamAI | Evaluation Report</title>",
        "<style>" + STYLES + "</style></head><body>",
        '<header><div class="wrap header-row"><strong>RoamAI <span>/ Evaluations</span></strong>',
        '<button type="button" onclick="window.print()">Print / Save PDF</button></div></header>',
        '<main class="wrap"><section class="intro"><p class="eyebrow">CONVERSATION QUALITY REVIEW</p>',
        "<h1>Evaluation Report</h1>",
        f'<p class="muted">Recorded {text(report["created_at"])} &middot; {len(results)} evaluated runs</p>',
        '<p class="notice">LLM judgments are advisory, not a safety certification. Uncertain and unexercised criteria do not pass. '
        "Same-model judging can share blind spots. Live discovery availability can affect results.</p></section>",
        '<section class="metrics" aria-label="Results summary">',
    ]
    for status, label in (("pass", "Passed"), ("fail", "Failed"), ("incomplete", "Incomplete"), ("error", "Errors")):
        parts.append(f'<div class="metric {status}"><strong>{counts[status]}</strong><span>{label}</span></div>')
    parts += [
        '</section><section><h2>Run Overview</h2><div class="table-scroll"><table>',
        "<thead><tr><th>Scenario</th><th>Repeat</th><th>Verdict</th><th>Duration</th><th>Findings</th></tr></thead><tbody>",
    ]
    for index, result in enumerate(results, 1):
        finding_count = len((result.get("judgment") or {}).get("findings", []))
        parts.append(
            f'<tr><td><a href="#case-{index}">{text(result["case_id"])}</a></td>'
            f"<td>{text(result['repeat'])}</td><td>{badge(result['status'])}</td>"
            f"<td>{result['seconds']:.1f}s</td><td>{finding_count}</td></tr>"
        )
    parts += ["</tbody></table></div></section>"]
    if report.get("comparison"):
        parts.append("<section><h2>Baseline Comparison</h2>" + bullet_list(report["comparison"]) + "</section>")
    for index, result in enumerate(results, 1):
        prefix = f"case-{index}"
        evidence = result.get("evidence", [])
        anchors = {item["id"]: f"{prefix}-evidence-{position}" for position, item in enumerate(evidence)}

        def evidence_links(identities):
            links = [
                f'<a class="evidence-link" href="#{anchors[identity]}">{text(identity)}</a>' if identity in anchors else text(identity)
                for identity in identities
            ]
            return '<p class="evidence-links">Evidence: ' + (", ".join(links) or "none") + "</p>"

        parts += [
            f'<section class="case" id="{prefix}"><div class="section-heading">',
            f"<h2>{text(result['case_id'])}</h2>{badge(result['status'])}</div>",
            f'<p class="muted">Repeat {text(result["repeat"])} &middot; {result["seconds"]:.1f} seconds</p>',
            f"<p>{text(result['scenario']['use_case'])}</p>",
        ]
        for error in result["errors"]:
            parts.append(
                '<div class="finding error"><strong>Execution / Judge Error</strong><pre>'
                + text(json.dumps(error, indent=2))
                + "</pre></div>"
            )
        for rejection in result.get("rejected_judgments", []):
            parts.append('<p class="notice">Judge output rejected: ' + text(rejection["reason"]) + "</p>")
        judgment = result.get("judgment")
        if judgment:
            parts += [f'<p class="assessment">{text(judgment["summary"])}</p>', '<h3>Criteria</h3><div class="criteria">']
            for criterion in judgment["criteria"]:
                label = result["scenario"]["criteria"][criterion["criterion_id"] - 1]
                parts += [
                    '<article class="criterion"><div class="criterion-heading">',
                    f"{badge(criterion['verdict'])}<strong>{criterion['score']}/4</strong></div>",
                    f"<h4>{text(label)}</h4><p>{text(criterion['explanation'])}</p>",
                    evidence_links(criterion["evidence_ids"]),
                    "</article>",
                ]
            parts += ["</div><h3>Findings</h3>"]
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            findings = sorted(judgment["findings"], key=lambda item: severity_order.get(item["severity"], 4))
            if not findings:
                parts.append('<p class="muted">No findings reported by the judge.</p>')
            for finding in findings:
                parts += [
                    f'<article class="finding">{badge(finding["severity"])}',
                    f"<h4>{text(finding['title'])}</h4><p>{text(finding['explanation'])}</p>",
                    f"<p><strong>Recommendation:</strong> {text(finding['recommendation'])}</p>",
                    evidence_links(finding["evidence_ids"]),
                    "</article>",
                ]
            parts += [
                '<div class="notes"><div><h3>Strengths</h3>',
                bullet_list(judgment["strengths"]),
                "</div><div><h3>Coverage Gaps</h3>",
                bullet_list(judgment["coverage_gaps"]),
                "</div></div>",
            ]
        parts += ['<details class="transcript"><summary>Conversation and Evidence</summary>']
        for item in evidence:
            anchor = anchors[item["id"]]
            if item["id"].startswith("turn-"):
                turn = item["input"]
                mode = "addressed" if turn["addressed"] else "passive"
                parts += [
                    f'<article class="turn" id="{anchor}"><p class="muted">{text(item["id"])} &middot; '
                    f"{text(turn['group'])} &middot; {mode}</p>",
                    f'<h4>{text(turn["speaker"])}</h4><div class="message">{text(turn["text"])}</div>',
                ]
                if turn.get("button"):
                    parts.append("<p>Button: " + text(turn["button"]) + "</p>")
                if not item.get("replies"):
                    parts.append(
                        '<p class="muted">' + ("Turn not executed." if item.get("not_executed") else "No delivered reply.") + "</p>"
                    )
                for reply in item.get("replies", []):
                    parts += [
                        '<div class="reply"><h4>RoamAI</h4><div class="message">' + text(reply["text"]) + "</div>",
                        '<p class="muted">Tools: '
                        + text(", ".join(call["name"] for call in reply.get("tool_calls", [])) or "none")
                        + "</p></div>",
                    ]
                parts.append("</article>")
            else:
                parts += [
                    f'<details class="raw" id="{anchor}"><summary>{text(item["id"])}</summary>',
                    "<pre>" + text(json.dumps(item, indent=2, default=str)) + "</pre></details>",
                ]
        parts += ["</details></section>"]
    parts += ["<section><h2>Run Metadata</h2><dl>"]
    for label, value in report.get("models", {}).items():
        parts += [f"<dt>{text(label)} model</dt><dd>{text(value)}</dd>"]
    for key in ("prompt_fingerprint", "judge_fingerprint", "subject_evidence_from", "progress_log"):
        if report.get(key):
            parts += [f"<dt>{text(key.replace('_', ' '))}</dt><dd><code>{text(report[key])}</code></dd>"]
    parts += [
        "</dl></section><footer>Contains evaluation conversation and state data. Share only with intended reviewers.</footer>",
        "</main><script>" + SCRIPT + "</script></body></html>",
    ]
    return "".join(parts)


def bullet_list(items):
    return "<ul>" + "".join("<li>" + text(item) + "</li>" for item in items) + "</ul>" if items else '<p class="muted">None reported.</p>'


STYLES = """
:root{color-scheme:light;--ink:#202a2a;--muted:#576766;--line:#d7dfdc;--green:#166a50;--red:#a62d3d;--amber:#895509}
*{box-sizing:border-box;letter-spacing:0}body{margin:0;color:var(--ink);background:#f6f8f7;font:15px/1.6 'Avenir Next','Segoe UI',sans-serif}
.wrap{max-width:1120px;margin:auto;padding:0 28px}header{background:#fff;border-bottom:1px solid var(--line)}
.header-row{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:72px}header strong{font-size:20px}header span{font-weight:400;color:var(--muted)}
button{font:inherit;background:#fff;border:1px solid #78908a;border-radius:4px;padding:7px 14px;cursor:pointer;color:var(--ink)}
button:hover{background:#edf3f0}a{color:var(--green);text-underline-offset:3px}a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #b06b00;outline-offset:3px}
section{padding:30px 0;border-bottom:1px solid var(--line)}.intro{padding-top:42px}.eyebrow{font-size:12px;font-weight:700;color:var(--green);margin:0}
h1{font:700 36px/1.2 'Palatino Linotype',Palatino,serif;margin:10px 0}h2{font-size:22px;line-height:1.3;margin:0 0 14px}h3{font-size:17px;margin:24px 0 12px}h4{font-size:15px;margin:8px 0}
p{margin:10px 0}.muted{color:var(--muted);font-size:13px}.notice{border-left:3px solid #b6923b;padding:8px 16px;color:#555b54;font-size:13px;max-width:900px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{border-top:3px solid var(--line);padding:12px 0}.metric strong{font-size:32px;display:block;line-height:1.2}.metric span{color:var(--muted)}
.metric.pass{border-color:var(--green)}.metric.fail,.metric.error{border-color:var(--red)}.metric.incomplete{border-color:#b6923b}
table{border-collapse:collapse;width:100%;text-align:left}th,td{padding:12px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:12px;color:var(--muted);background:#edf1ef}.table-scroll{overflow-x:auto}
.badge{display:inline-block;border:1px solid currentColor;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;text-transform:uppercase;white-space:nowrap;color:var(--muted)}
.badge.pass{color:var(--green);background:#edf8f2}.badge.fail,.badge.error,.badge.critical,.badge.high{color:var(--red);background:#fff0f0}.badge.incomplete,.badge.medium{color:var(--amber);background:#fff8e7}
.section-heading,.criterion-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.section-heading h2{margin:0}.section-heading{margin-bottom:12px}
.criteria{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.criterion{background:#fff;border:1px solid var(--line);border-radius:4px;padding:18px}.criterion p,.finding p{font-size:14px}
.finding{padding:16px 0;border-bottom:1px solid var(--line)}.finding.error{border-left:3px solid var(--red);padding-left:16px}.evidence-links{color:var(--muted);font-size:12px!important}
.notes{display:grid;grid-template-columns:1fr 1fr;gap:28px}li{margin:7px 0}ul{padding-left:20px}.assessment{font-size:16px}.transcript{margin-top:24px;border-top:1px solid var(--line)}
summary{cursor:pointer;padding:12px 0;font-weight:600}.turn{border-top:1px solid var(--line);padding:18px 0}.reply{border-left:3px solid #7ca895;padding-left:18px;margin-top:16px}
.message,pre{white-space:pre-wrap;overflow-wrap:anywhere}.message{font-size:14px}pre{font:12px/1.5 Menlo,Consolas,monospace;max-height:400px;overflow:auto;background:#edf1ef;padding:12px}
.raw{border-top:1px solid var(--line);font-size:13px}dt{font-weight:600;text-transform:capitalize}dd{margin:0 0 14px;color:var(--muted);overflow-wrap:anywhere}code{font-size:12px}footer{padding:28px 0;color:var(--muted);font-size:12px}
.case,h2,h4,p,td{overflow-wrap:anywhere}:target{outline:2px solid #b6923b;outline-offset:4px;scroll-margin-top:20px}
@media(max-width:640px){.wrap{padding:0 16px}.header-row{flex-wrap:wrap;padding-top:12px;padding-bottom:12px}h1{font-size:30px}.metrics{grid-template-columns:repeat(2,1fr)}.criteria,.notes{grid-template-columns:1fr}.section-heading{align-items:flex-start}th,td{padding:9px}.section-heading h2{font-size:19px}}
@media print{@page{margin:16mm}body{background:#fff;font-size:11px}.wrap{max-width:none;padding:0}header button{display:none}section{padding:16px 0}.intro{padding-top:20px}h1{font-size:28px}h2{font-size:19px}.case{break-before:page}.criterion,.finding,.metric{break-inside:avoid}pre{max-height:none;overflow:visible}.table-scroll{overflow:visible}.badge{-webkit-print-color-adjust:exact;print-color-adjust:exact}a{color:inherit}details>summary{font-size:12px}.message{font-size:11px}}
"""


SCRIPT = """
function revealEvidence(){
  const target=document.getElementById(location.hash.slice(1));
  if(!target)return;
  for(let node=target;node;node=node.parentElement){if(node.tagName==='DETAILS')node.open=true;}
  target.scrollIntoView();
}
addEventListener('hashchange',revealEvidence);
revealEvidence();
let printState=[];
addEventListener('beforeprint',()=>{
  printState=Array.from(document.querySelectorAll('details')).map(node=>[node,node.open]);
  printState.forEach(([node])=>node.open=true);
});
addEventListener('afterprint',()=>printState.forEach(([node,open])=>node.open=open));
"""
