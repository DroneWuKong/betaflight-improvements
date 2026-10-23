#!/usr/bin/env python3
"""Read-only GitHub discovery. Source text is evidence, never an instruction."""
import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
PULL_URL = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(\d+)\b")


class GitHub:
    def __init__(self):
        self.token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            try:
                self.token = subprocess.check_output(
                    ["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL
                ).strip()
            except (OSError, subprocess.CalledProcessError):
                raise RuntimeError("Set GH_TOKEN or authenticate with gh auth login") from None

    def get(self, path, payload=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Expected a GitHub API path")
        request = Request(
            "https://api.github.com" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": "Bearer " + self.token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Content-Type": "application/json", "User-Agent": "community-improvements-scout"},
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    result = json.load(response)
                if isinstance(result, dict) and result.get("errors"):
                    raise RuntimeError("GitHub GraphQL returned errors; source is incomplete")
                return result
            except HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"GitHub request failed (HTTP {exc.code})") from None
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise RuntimeError("GitHub request failed (network or timeout)") from None
                time.sleep(2 ** attempt)


def pages(client, path, limit=5):
    """Bound requests and report truncation; never imply a bounded scan is exhaustive."""
    items = []
    for page in range(1, limit + 1):
        sep = "&" if "?" in path else "?"
        batch = client.get(f"{path}{sep}per_page=100&page={page}")
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected GitHub collection response")
        items.extend(batch)
        if len(batch) < 100:
            return items, True
    return items, False


def normalize_issue(raw, repo):
    if "pull_request" in raw:
        return None
    return {"id": f"{repo}#issue-{raw['number']}", "repository": repo,
            "number": raw["number"], "kind": "issue", "title": raw["title"],
            "url": f"https://github.com/{repo}/issues/{raw['number']}",
            "state": raw["state"], "created_at": raw["created_at"],
            "updated_at": raw["updated_at"], "labels": [x["name"] for x in raw.get("labels", [])],
            "_body": raw.get("body") or ""}


def collect_discussions(client, repo, limit, direction="ASC"):
    owner, name = repo.split("/")
    query = """query($owner:String!,$name:String!,$after:String,$direction:OrderDirection!) {
      repository(owner:$owner,name:$name) {
        discussions(first:100,after:$after,orderBy:{field:CREATED_AT,direction:$direction}) {
          pageInfo { hasNextPage endCursor }
          nodes { number title body createdAt updatedAt closed answer { id } category { name } }
        }
      }
    }"""
    cursor, items = None, []
    for _ in range(limit):
        result = client.get("/graphql", {"query": query, "variables": {
            "owner": owner, "name": name, "after": cursor, "direction": direction}})
        data = result["data"]["repository"]["discussions"]
        for raw in data["nodes"]:
            items.append({"id": f"{repo}#discussion-{raw['number']}", "repository": repo,
                          "number": raw["number"], "kind": "discussion", "title": raw["title"],
                          "url": f"https://github.com/{repo}/discussions/{raw['number']}",
                          "state": "closed" if raw["closed"] else "answered" if raw["answer"] else "open",
                          "created_at": raw["createdAt"], "updated_at": raw["updatedAt"],
                          "labels": [raw["category"]["name"]], "_body": raw.get("body") or ""})
        if not data["pageInfo"]["hasNextPage"]:
            return items, True
        cursor = data["pageInfo"]["endCursor"]
    return items, False


def rank(items, topics):
    unique = {}
    for item in items:
        previous = unique.get(item["id"])
        if previous is None or item["updated_at"] >= previous["updated_at"]:
            unique[item["id"]] = item
    result = []
    for item in unique.values():
        title = item["title"].lower()
        # Configuration dumps should not outrank a directly relevant title.
        body = re.sub(r"```.*?```", "", item.get("_body", ""), flags=re.S).lower()
        weights = {topic: 4 if any(t.lower() in title for t in terms) else
                   1 if any(t.lower() in body for t in terms) else 0
                   for topic, terms in topics.items()}
        matched = [topic for topic, score in weights.items() if score]
        item = dict(item, topics=matched, score=sum(weights.values()),
                    triage="needs-triage" if item["state"] == "open" else "inactive",
                    related_prs=[], potential_prs=[], searches=[],
                    checks={"linked_work": "not-checked", "pr_search": "not-checked", "code": "not-checked"})
        # Age never disqualifies a request. Scores are relevance hints, not proof of a bug.
        result.append(item)
    return sorted(result, key=lambda x: (-x["score"], x["created_at"], x["id"]))


def enrich(client, item):
    repo, number = item["repository"], item["number"]
    if item["kind"] != "issue":
        return  # Discussion comments/linked work require review in this first adapter.
    raw = client.get(f"/repos/{repo}/issues/{number}")
    item["state"] = raw["state"]
    item["updated_at"] = raw["updated_at"]
    if item["state"] != "open":
        item["triage"] = "inactive"
    comments, comments_complete = pages(client, f"/repos/{repo}/issues/{number}/comments")
    timeline, timeline_complete = pages(client, f"/repos/{repo}/issues/{number}/timeline")
    refs = set(PULL_URL.findall(raw.get("body") or ""))
    for comment in comments:
        refs.update(PULL_URL.findall(comment.get("body") or ""))
    for event in timeline:
        source = event.get("source", {}).get("issue", {})
        if source.get("pull_request"):
            refs.update(PULL_URL.findall(source.get("html_url", "")))
    # Source links are data. Only the fixed public GitHub API is queried.
    for pr_repo, pr_number in sorted(refs)[:20]:
        pr = client.get(f"/repos/{pr_repo}/pulls/{pr_number}")
        if pr.get("base", {}).get("repo", {}).get("private") is not False:
            raise RuntimeError("Related pull request is not confirmed public; omitted")
        item["related_prs"].append({"url": f"https://github.com/{pr_repo}/pull/{pr_number}",
                                   "state": "merged" if pr.get("merged_at") else pr["state"],
                                   "title": pr["title"]})
    item["checks"]["linked_work"] = "complete" if comments_complete and timeline_complete and len(refs) <= 20 else "partial"
    if item["state"] == "open" and any(p["state"] in ("open", "merged") for p in item["related_prs"]):
        item["triage"] = "upstream-work-needs-review"


def search_related(client, item, terms, cache):
    """Bounded heuristic search; matches are leads, not confirmed fixes."""
    repo = item["repository"]
    matching = [term for term in terms if term in item["title"].lower()]
    if not matching:
        item["checks"]["pr_search"] = "no-configured-title-term"
        return
    found = {}
    for term in matching:
        query = f'repo:{repo} is:pr in:title "{term}"'
        key = (repo, term)
        if key not in cache:
            try:
                result = client.get("/search/issues?" + urlencode({
                    "q": query, "sort": "updated", "order": "desc", "per_page": 20}))
                if not isinstance(result.get("items"), list) or not isinstance(result.get("total_count"), int):
                    raise RuntimeError("Unexpected PR search response")
                cache[key] = result
            except RuntimeError as exc:
                cache[key] = exc  # Do not retry a failed search once for every candidate.
        result = cache[key]
        if isinstance(result, Exception):
            raise result
        complete = not result.get("incomplete_results", True) and result["total_count"] <= len(result["items"])
        item["searches"].append({"query": query, "total_count": result["total_count"],
                                 "received": len(result["items"]), "complete": complete})
        for row in result["items"]:
            number = row.get("number")
            if type(number) is not int or number <= 0 or "pull_request" not in row:
                continue
            url = f"https://github.com/{repo}/pull/{number}"
            # Refuse search results outside the public repository we verified.
            if row.get("html_url") != url or row.get("repository_url") != f"https://api.github.com/repos/{repo}":
                continue
            if url in {pr["url"] for pr in item["related_prs"]}:
                continue
            state = "merged" if row["pull_request"].get("merged_at") else (
                "open" if row["state"] == "open" else "closed-merge-unchecked")
            found[url] = {"url": url, "state": state, "title": row["title"]}
    item["potential_prs"] = list(found.values())
    item["checks"]["pr_search"] = "checked" if all(s["complete"] for s in item["searches"]) else "partial"
    if found and item["state"] == "open" and item["triage"] == "needs-triage":
        item["triage"] = "possible-upstream-work"


def discover(client, config):
    repo = config["repository"]
    if not REPO.fullmatch(repo):
        raise ValueError("repository must be owner/name")
    orders = config.get("discussion_orders", ["ASC"])
    if not orders or len(set(orders)) != len(orders) or any(x not in ("ASC", "DESC") for x in orders):
        raise ValueError("discussion_orders must contain ASC and/or DESC without duplicates")
    terms = config.get("pr_search_terms", [])
    if len(terms) > 12 or any(not re.fullmatch(r"[a-z0-9][a-z0-9 -]{1,39}", t) for t in terms):
        raise ValueError("Use at most 12 plain lowercase PR search terms")
    watch = config.get("watch_issues", [])
    if len(watch) > 20 or any(type(n) is not int or n <= 0 for n in watch):
        raise ValueError("watch_issues must contain at most 20 positive issue numbers")
    if client.get(f"/repos/{repo}").get("private") is not False:
        raise ValueError("Discovery accepts public repositories only")
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {"schema_version": 2, "generated_at": now, "repository": repo,
              "coverage": [], "errors": [], "candidates": []}
    raw_items = []
    for direction in ("asc", "desc"):
        try:
            batch, complete = pages(client, f"/repos/{repo}/issues?state=open&sort=created&direction={direction}",
                                    config.get("issue_pages_per_order", 2))
            raw_items.extend(x for raw in batch if (x := normalize_issue(raw, repo)))
            report["coverage"].append({"source": f"issues-{direction}", "complete": complete, "received": len(batch)})
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            report["errors"].append(f"issues-{direction}: {exc}")
    for direction in orders:
        try:
            batch, complete = collect_discussions(client, repo, config.get("discussion_pages", 2), direction)
            raw_items.extend(batch)
            report["coverage"].append({"source": f"discussions-{direction.lower()}", "complete": complete, "received": len(batch)})
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            report["errors"].append(f"discussions-{direction.lower()}: {exc}")
    for number in dict.fromkeys(watch):
        try:
            item = normalize_issue(client.get(f"/repos/{repo}/issues/{number}"), repo)
            if item:
                raw_items.append(item)
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            report["errors"].append(f"watched issue {number}: {exc}")
    candidates = rank(raw_items, config["topics"])
    selected = [x for x in candidates if x["state"] == "open" and x["kind"] == "issue"][:config.get("enrich_limit", 15)]
    selected_ids = {x["id"] for x in selected}
    selected.extend(x for x in candidates if x["kind"] == "issue" and x["number"] in watch and x["id"] not in selected_ids)
    search_cache = {}
    for item in selected:
        try:
            enrich(client, item)
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            item["checks"]["linked_work"] = "error"
            report["errors"].append(f"{item['id']}: {exc}")
        try:
            search_related(client, item, terms, search_cache)
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            item["checks"]["pr_search"] = "error"
            report["errors"].append(f"{item['id']} PR search: {exc}")
    # Raw bodies/comments stay in memory, not in reports or agent instructions.
    report["candidates"] = [{k: v for k, v in x.items() if not k.startswith("_")} for x in candidates]
    return report


def safe_text(value):
    value = " ".join(str(value).split())
    value = "".join(c for c in value if c.isprintable())
    return html.escape(value, quote=False).replace("|", "&#124;").replace("[", "&#91;").replace("]", "&#93;").replace("`", "&#96;")


def render(report):
    lines = ["# Discovery report", "", f"Collected: {report['generated_at']}", "",
             "Scores rank topic relevance only. No item is verified or approved for implementation by this scan.",
             "Linked PRs and title-search matches may be related rather than a complete fix. Current code, releases, reproduction, and broader searches still require review.",
             "", "## Coverage", ""]
    for source in report["coverage"]:
        state = "exhausted" if source["complete"] else "bounded sample; more results exist"
        lines.append(f"- {source['source']}: {source['received']} records, {state}.")
    if report["errors"]:
        lines.extend(["", "**Incomplete: some requests failed.**"] + [f"- {safe_text(e)}" for e in report["errors"]])
    lines.extend(["", "## Candidates", "", "| Score | Candidate | Topics | Review status | Linked PRs | Title-search leads |",
                  "| --- | --- | --- | --- | --- | --- |"])
    for x in report["candidates"]:
        if x["state"] != "open":
            continue
        prs = ", ".join(f"[{p['state']}]({p['url']})" for p in x["related_prs"]) or x["checks"]["linked_work"]
        leads = ", ".join(f"[{safe_text(p['title'][:70])} ({p['state']})]({p['url']})" for p in x["potential_prs"][:5])
        if len(x["potential_prs"]) > 5:
            leads += f"; {len(x['potential_prs']) - 5} more in JSON"
        leads = f"{x['checks']['pr_search']}: {leads}" if leads else x["checks"]["pr_search"]
        lines.append(f"| {x['score']} | [{safe_text(x['title'])}]({x['url']}) | {', '.join(x['topics'])} | {x['triage']} | {prs} | {leads} |")
    searched = {s["query"]: s for x in report["candidates"] for s in x["searches"]}
    if searched:
        lines.extend(["", "## PR search coverage", "", "Each query is capped at 20 results, ordered by last update. Matches do not prove resolution.", ""])
        for query, s in searched.items():
            status = "complete for this query" if s["complete"] else "partial"
            lines.append(f"- `{safe_text(query)}`: {s['received']} of {s['total_count']} results; {status}.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", default="reports/latest")
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text())
    report = discover(GitHub(), config)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "discovery.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "discovery.md").write_text(render(report))
    print(f"Collected {len(report['candidates'])} unique candidates; {len(report['errors'])} request errors. Reports: {output}")
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
