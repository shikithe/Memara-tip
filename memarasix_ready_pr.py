#!/usr/bin/env python3
"""Create exactly one AI-ready PR per verified ListaSix snapshot.

This is a NOTIFICATION HANDOFF, not permission to publish or bet.
The GitHub workflow uses its repo-scoped GITHUB_TOKEN. If repository policy
forbids Actions creating PRs, the step fails visibly and the normal sync stays
available. A ChatGPT Work PR-event task must be authorized separately.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

SAR = ZoneInfo("Europe/Sarajevo")
REPO = "shikithe/Memara-tip"
LABEL = "listasix-ready"


def parsed(value):
    value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Missing timezone on timestamp")
    return value.astimezone(timezone.utc)


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def ready_manifest(root, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(SAR).date().isoformat()
    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8"))
    active = read("listasix-data/active-list.json")
    history = read("listasix-data/history-h2h.json")
    ack = read("listasix-data/sync-receipt.json")
    if any(doc.get("date") != day for doc in (active, history, ack)):
        raise ValueError("List, history or receipt is not today's snapshot")
    if not active.get("publication_allowed"):
        raise ValueError("ListaSix list is not marked ready")
    if parsed(active.get("expires_at")) <= now:
        raise ValueError("ListaSix list has expired")
    if not history.get("fixtures") or not history.get("leagues"):
        raise ValueError("ESPN history is incomplete")
    fixtures = active.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("Daily fixture list empty")
    names = [x.get("fixture_id") for x in fixtures if isinstance(x, dict)]
    if len(names) != len(fixtures) or not all(names) or len(names) != len(set(names)):
        raise ValueError("Missing or duplicated fixture IDs")
    # The same list contains quotes; candidates without odds are not enough.
    if not any(isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool) and x.get(k) > 1
               for x in fixtures for k in ("home_odds", "away_odds", "over25_odds", "over15_odds")):
        raise ValueError("No market prices in synchronized fixtures")
    sha = fingerprint(active)
    if ack.get("active_sha256") != sha or ack.get("fixtures") != len(fixtures):
        raise ValueError("Ready receipt SHA256/count does not match imported list")
    synced = parsed(ack.get("synced_at_utc"))
    if synced > now or synced.astimezone(SAR).date().isoformat() != day:
        raise ValueError("Invalid receipt timestamp")
    return {
        "kind": "listasix-ready-for-ai-review",
        "date": day,
        "source_active_sha256": sha,
        "fixtures": len(fixtures),
        "synced_at_utc": synced.isoformat(),
        "source": "shikithe/Memara-tip:main/listasix-data/active-list.json",
        "approval_target": "shikithe/Memara-tip:main/memarasix-1455-approved.json",
        "status": "WAITING_FOR_CHATGPT_AI_ANALYST",
        "note": "Notification only. No picks, approvals or publication in this PR."
    }


def gh(method, endpoint, payload=None, optional=False):
    cmd = ["gh", "api", "--method", method, "-H",
           "Accept: application/vnd.github+json", endpoint]
    if payload is not None:
        cmd += ["--input", "-"]
    proc = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                          capture_output=True, text=True, check=False, timeout=35)
    if proc.returncode:
        output = (proc.stderr or proc.stdout).strip()
        if optional and ("404" in output or "Not Found" in output):
            return None
        raise RuntimeError("%s %s failed: %s" % (method, endpoint, output[:380]))
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def ensure_label():
    path = "repos/%s/labels/%s" % (REPO, LABEL)
    if gh("GET", path, optional=True) is None:
        gh("POST", "repos/%s/labels" % REPO, {
            "name": LABEL, "color": "0E8A16",
            "description": "Verified ListaSix active-list imported; ChatGPT AI review may begin"
        })


def ensure_ready_pr(manifest):
    sha = manifest["source_active_sha256"]
    day = manifest["date"]
    branch = "listasix-ready/%s/%s" % (day, sha[:16])
    marker = "ai-ready-events/%s-%s.json" % (day, sha[:16])
    head = gh("GET", "repos/%s/git/ref/heads/%s" % (REPO, quote(branch, safe="/")),
              optional=True)
    if head is None:
        main = gh("GET", "repos/%s/git/ref/heads/main" % REPO)
        gh("POST", "repos/%s/git/refs" % REPO,
           {"ref": "refs/heads/" + branch, "sha": main["object"]["sha"]})
        contents = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        gh("PUT", "repos/%s/contents/%s" % (REPO, marker), {
            "message": "Signal confirmed ListaSix ready snapshot for AI analysis",
            "branch": branch,
            "content": base64.b64encode(contents.encode("utf-8")).decode("ascii")
        })
    # One PR per exact hash; repeated dispatch/scheduled sync remains idempotent.
    prs = gh("GET", "repos/%s/pulls?state=all&head=shikithe:%s&per_page=100" %
             (REPO, quote(branch, safe="")))
    if isinstance(prs, list) and prs:
        number = prs[0]["number"]
        print("LISTASIX_READY_PR_ALREADY_EXISTS", number, sha)
        return number
    title = "[listasix-ready] %s | %s" % (day, sha[:12])
    body = (
        "### MemaraSix: verified ListaSix data awaiting independent ChatGPT AI review\n\n"
        "- **Date:** \`%s\`\n"
        "- **SHA-256:** \`%s\`\n"
        "- **Fixtures:** %s\n"
        "- **Synchronized at (UTC):** \`%s\`\n\n"
        "**Required AI process:** Read current **main** versions of "
        "\`listasix-data/active-list.json\`, \`listasix-data/history-h2h.json\`, "
        "\`listasix-data/sync-receipt.json\` and \`data.json\`. Verify the "
        "date/hash and that existing tickets have not already been published. "
        "Analyze independently; only the AI analyst may commit validated A/B/C "
        "to \`memarasix-1455-approved.json\` on main. "
        "Never merge this signaling PR and NEVER publish or edit bank from it.\n\n"
        "**This PR is only an event/notification**; it contains no betting ticket."
    ) % (day, sha, manifest["fixtures"], manifest["synced_at_utc"])
    pr = gh("POST", "repos/%s/pulls" % REPO, {
        "title": title, "head": branch, "base": "main", "body": body
    })
    gh("POST", "repos/%s/issues/%s/labels" % (REPO, pr["number"]),
       {"labels": [LABEL]})
    print("LISTASIX_READY_PR_CREATED", pr["number"], pr.get("html_url"), sha)
    return pr["number"]


def main():
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("GH_TOKEN missing (do not expose its value)")
    if os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise RuntimeError("Wrong GitHub repository for ready-event PR")
    manifest = ready_manifest(Path("."))
    ensure_label()
    ensure_ready_pr(manifest)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("LISTASIX_READY_PR_BLOCKED", str(exc)[:450], file=sys.stderr)
        sys.exit(1)
