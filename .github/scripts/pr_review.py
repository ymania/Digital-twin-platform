"""
Called by the PR Review workflow.
Reads pr.diff, optionally calls Claude, writes comment.txt.
"""
import json
import os
import re
import urllib.request

diff = open("pr.diff").read()

# ── Basic diff stats (always computed) ────────────────────────────────────────
added   = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
files   = re.findall(r"^diff --git a/.+ b/(.+)$", diff, re.MULTILINE)

stats = (
    f"**{len(files)} file(s) changed** · **+{added}** additions · **-{removed}** deletions\n\n"
    + "\n".join(f"- `{f}`" for f in files)
)

pr_header = (
    f"**PR #{os.environ['PR_NUMBER']}:** {os.environ['PR_TITLE']}  \n"
    f"**Author:** {os.environ['PR_AUTHOR']}  \n"
    f"**Branch:** `{os.environ['PR_HEAD']}` → `{os.environ['PR_BASE']}`"
)

commands = (
    "\n\n---\n"
    "*Commands: `/claude approve` · `/claude merge` · `/claude resolve`*"
)

api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

if api_key:
    prompt = (
        "You are reviewing a pull request for the room-digital-twin project "
        "(Docker Compose stack: Mosquitto MQTT · InfluxDB 2.7 · Grafana 10.4 · "
        "Python simulator · Three.js 3D viz).\n\n"
        + pr_header + "\n\n"
        + stats + "\n\n"
        "Diff (truncated to 12 000 chars):\n"
        + diff[:12000]
        + "\n\nWrite a structured review with exactly these sections:\n\n"
        "## Summary\n"
        "2-3 sentences describing what this PR does.\n\n"
        "## Key changes\n"
        "Bullet list of the most important modifications.\n\n"
        "## Concerns\n"
        "Issues, risks, or things to double-check. Write \"None\" if the PR looks clean.\n\n"
        "## Recommendation\n"
        "Exactly one of: APPROVE | REQUEST CHANGES | NEEDS DISCUSSION\n"
        "Followed by one sentence explaining your recommendation."
    )

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        review = json.load(resp)["content"][0]["text"]

    comment = f"## Claude AI Review\n\n{pr_header}\n\n{stats}\n\n---\n\n{review}{commands}"

else:
    diff_excerpt = "\n".join(diff.splitlines()[:80])
    comment = (
        f"## PR Summary\n\n{pr_header}\n\n{stats}\n\n"
        "<details>\n<summary>Diff excerpt</summary>\n\n"
        f"```diff\n{diff_excerpt}\n```\n\n</details>"
        + commands
    )

open("comment.txt", "w").write(comment)
print("comment.txt written.")
