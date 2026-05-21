"""
Called by the PR Commands workflow for /claude resolve.
Resolves every Git-conflicted file in the working tree using Claude.
Writes resolved.txt with the list of files it fixed.
"""
import json
import os
import subprocess
import urllib.request

api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY is not set.")
    raise SystemExit(1)

conflicted = subprocess.run(
    ["git", "diff", "--name-only", "--diff-filter=U"],
    capture_output=True, text=True,
).stdout.strip().split("\n")
conflicted = [f for f in conflicted if f]

resolved = []
for filepath in conflicted:
    raw = open(filepath).read()
    prompt = (
        "Resolve all Git conflict markers in this file from the room-digital-twin project.\n"
        "Return ONLY the complete resolved file content — no explanations, no markdown fences.\n\n"
        f"File: {filepath}\n\n{raw}"
    )
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        clean = json.load(resp)["content"][0]["text"]
    open(filepath, "w").write(clean)
    resolved.append(filepath)
    print(f"Resolved: {filepath}")

open("resolved.txt", "w").write("\n".join(resolved))
