import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import scout
from test_scout import issue


def candidate(title="sdcardSdio_poll loops indefinitely if card reads fail"):
    raw = issue(); raw["title"] = title
    return scout.rank([scout.normalize_issue(raw, "a/b")], {})[0]


def search_row(number=15748, repo="a/b", state="open", merged=None):
    return {"number": number, "html_url": f"https://github.com/{repo}/pull/{number}",
            "repository_url": f"https://api.github.com/repos/{repo}", "title": "Bound SDIO transfer recovery",
            "state": state, "pull_request": {"merged_at": merged}}


def results(*rows, total=None, incomplete=False):
    return {"items": list(rows), "total_count": len(rows) if total is None else total,
            "incomplete_results": incomplete}


class FollowupTests(unittest.TestCase):
    def test_unlinked_recovery_pr_is_found_but_not_claimed_as_a_fix(self):
        client = Mock(); client.get.return_value = results(search_row())
        item = candidate()
        scout.search_related(client, item, ["sdio"], {})
        self.assertEqual(item["potential_prs"][0]["url"], "https://github.com/a/b/pull/15748")
        self.assertEqual(item["triage"], "possible-upstream-work")
        self.assertEqual(item["checks"]["code"], "not-checked")
        query = parse_qs(urlsplit(client.get.call_args.args[0]).query)["q"][0]
        self.assertEqual(query, 'repo:a/b is:pr in:title "sdio"')

    def test_shared_queries_are_fetched_once(self):
        client = Mock(); client.get.return_value = results(search_row())
        cache = {}
        for _ in range(3):
            scout.search_related(client, candidate(), ["sdio"], cache)
        self.assertEqual(client.get.call_count, 1)

    def test_failed_query_is_not_retried_per_candidate(self):
        client = Mock(); client.get.side_effect = RuntimeError("rate limit")
        cache = {}
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                scout.search_related(client, candidate(), ["sdio"], cache)
        self.assertEqual(client.get.call_count, 1)

    def test_partial_or_timed_out_search_is_explicit(self):
        for response in [results(search_row(), total=99), results(search_row(), incomplete=True)]:
            with self.subTest(response=response):
                client = Mock(); client.get.return_value = response
                item = candidate(); scout.search_related(client, item, ["sdio"], {})
                self.assertEqual(item["checks"]["pr_search"], "partial")
                self.assertFalse(item["searches"][0]["complete"])

    def test_closed_pr_is_not_assumed_merged(self):
        client = Mock(); client.get.return_value = results(search_row(state="closed"))
        item = candidate(); scout.search_related(client, item, ["sdio"], {})
        self.assertEqual(item["potential_prs"][0]["state"], "closed-merge-unchecked")

    def test_cross_repository_results_and_non_prs_are_discarded(self):
        client = Mock()
        non_pr = search_row(); non_pr.pop("pull_request")
        spoof = search_row(); spoof["html_url"] = "https://github.com.evil.test/a/b/pull/15748"
        client.get.return_value = results(search_row(repo="private/project"), non_pr, spoof)
        item = candidate(); scout.search_related(client, item, ["sdio"], {})
        self.assertEqual(item["potential_prs"], [])
        self.assertEqual(item["triage"], "needs-triage")

    def test_explicit_links_are_not_duplicated_as_search_leads(self):
        client = Mock(); client.get.return_value = results(search_row())
        item = candidate(); item["related_prs"] = [{"url": search_row()["html_url"]}]
        item["triage"] = "upstream-work-needs-review"
        scout.search_related(client, item, ["sdio"], {})
        self.assertEqual(item["potential_prs"], [])
        self.assertEqual(item["triage"], "upstream-work-needs-review")

    def test_external_title_cannot_inject_query_scope(self):
        client = Mock(); client.get.return_value = results()
        item = candidate('sdio repo:private/project OR is:issue')
        scout.search_related(client, item, ["sdio"], {})
        self.assertNotIn("private", client.get.call_args.args[0])
        config = {"repository": "a/b", "pr_search_terms": ["sdio repo:private/project"]}
        with self.assertRaises(ValueError):
            scout.discover(client, config)

    def test_title_relevance_beats_configuration_dump_keywords(self):
        relevant = scout.normalize_issue(issue(number=1), "a/b")
        noisy = dict(relevant, id="noisy", title="Help", _body="```blackbox msp diagnostics```")
        ranked = scout.rank([noisy, relevant], {"logging": ["blackbox"], "interop": ["msp"], "diagnostics": ["diagnostics"]})
        self.assertEqual(ranked[0]["id"], relevant["id"])
        self.assertEqual(ranked[1]["score"], 0)

    def test_watched_item_is_refreshed_and_checked_outside_ranking_budget(self):
        raw = issue(number=8690); raw["state"] = "closed"
        client = Mock()
        def get(path):
            if path == "/repos/a/b": return {"private": False}
            if path == "/repos/a/b/issues/8690": return raw
            if "/issues?" in path: return []
            raise AssertionError(path)
        client.get.side_effect = get
        with patch.object(scout, "collect_discussions", return_value=([], True)), patch.object(scout, "enrich") as enrich:
            report = scout.discover(client, {"repository": "a/b", "topics": {}, "enrich_limit": 0, "watch_issues": [8690]})
        self.assertEqual(enrich.call_args.args[1]["number"], 8690)
        self.assertEqual(report["candidates"][0]["triage"], "inactive")

    def test_oldest_and_newest_discussions_are_collected(self):
        client = Mock(); client.get.side_effect = [{"private": False}, [], []]
        with patch.object(scout, "collect_discussions", return_value=([], False)) as collect:
            report = scout.discover(client, {"repository": "a/b", "topics": {}, "discussion_orders": ["ASC", "DESC"]})
        self.assertEqual([call.args[-1] for call in collect.call_args_list], ["ASC", "DESC"])
        self.assertEqual(len(report["coverage"]), 4)
        self.assertFalse(report["coverage"][-1]["complete"])


if __name__ == "__main__":
    unittest.main()
