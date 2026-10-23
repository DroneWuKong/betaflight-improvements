import unittest
from unittest.mock import Mock

import scout


def issue(number=1, **kw):
    return dict(number=number, title="Blackbox storage", state="open", body="logging",
                created_at="2019-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z", labels=[], **kw)


class ScoutTests(unittest.TestCase):
    def test_pull_requests_are_not_bugs(self):
        self.assertIsNone(scout.normalize_issue(issue(pull_request={}), "a/b"))

    def test_duplicates_and_issue_discussion_number_collision(self):
        a = scout.normalize_issue(issue(), "a/b")
        b = dict(a, id="a/b#discussion-1", kind="discussion")
        ranked = scout.rank([a, a, b], {"logging": ["blackbox"]})
        self.assertEqual(len(ranked), 2)
        self.assertTrue(all(x["triage"] == "needs-triage" for x in ranked))

    def test_old_requests_remain_eligible_and_closed_do_not(self):
        a = scout.normalize_issue(issue(), "a/b")
        ranked = scout.rank([a, dict(a, id="closed", state="closed")], {"logging": ["blackbox"]})
        self.assertEqual({x["triage"] for x in ranked}, {"inactive", "needs-triage"})

    def test_pagination_reports_truncation(self):
        client = Mock()
        client.get.return_value = [issue()] * 100
        rows, complete = scout.pages(client, "/repos/a/b/issues?state=open", limit=2)
        self.assertEqual(len(rows), 200)
        self.assertFalse(complete)
        self.assertIn("&per_page=100&page=2", client.get.call_args.args[0])

    def test_linked_pr_in_comment_prevents_unqualified_candidate(self):
        client = Mock()
        client.get.side_effect = [issue(), [{"body": "See https://github.com/a/b/pull/4"}], [],
                                  {"title": "Fix", "state": "open", "merged_at": None, "base": {"repo": {"private": False}}}]
        item = scout.rank([scout.normalize_issue(issue(), "a/b")], {})[0]
        scout.enrich(client, item)
        self.assertEqual(item["triage"], "upstream-work-needs-review")
        self.assertEqual(item["checks"]["linked_work"], "complete")

    def test_timeline_merged_pr_is_also_existing_work(self):
        client = Mock()
        client.get.side_effect = [issue(), [], [{"source": {"issue": {"pull_request": {"url": "x"},
            "html_url": "https://github.com/a/b/pull/4"}}}], {"title": "Fix", "state": "closed", "merged_at": "date", "base": {"repo": {"private": False}}}]
        item = scout.rank([scout.normalize_issue(issue(), "a/b")], {})[0]
        scout.enrich(client, item)
        self.assertEqual(item["related_prs"][0]["state"], "merged")
        self.assertEqual(item["triage"], "upstream-work-needs-review")

    def test_untrusted_links_cannot_select_an_api_host(self):
        text = "https://evil.test/a/b/pull/4 https://github.com.evil.test/a/b/pull/4"
        self.assertEqual(scout.PULL_URL.findall(text), [])

    def test_closed_during_scan_is_not_kept_open(self):
        raw = issue(); raw["state"] = "closed"
        client = Mock(); client.get.side_effect = [raw, [], []]
        item = scout.rank([scout.normalize_issue(issue(), "a/b")], {})[0]
        scout.enrich(client, item)
        self.assertEqual(item["triage"], "inactive")

    def test_complete_scan_drops_bodies_and_reports_source_errors(self):
        client = Mock()
        client.get.side_effect = [{"private": False}, [issue()], [issue()], RuntimeError("unavailable")]
        report = scout.discover(client, {"repository": "a/b", "topics": {}, "enrich_limit": 0})
        self.assertEqual(len(report["candidates"]), 1)
        self.assertNotIn("_body", report["candidates"][0])
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("Incomplete", scout.render(report))

    def test_private_related_pr_does_not_enter_report(self):
        client = Mock()
        client.get.side_effect = [issue(), [{"body": "https://github.com/private/project/pull/1"}], [],
                                  {"title": "Confidential", "base": {"repo": {"private": True}}}]
        item = scout.rank([scout.normalize_issue(issue(), "a/b")], {})[0]
        with self.assertRaises(RuntimeError):
            scout.enrich(client, item)
        self.assertEqual(item["related_prs"], [])

    def test_private_source_is_rejected(self):
        client = Mock(); client.get.return_value = {"private": True}
        with self.assertRaises(ValueError):
            scout.discover(client, {"repository": "a/b", "topics": {}})

    def test_report_neutralizes_markup_and_line_injection(self):
        value = scout.safe_text("<script>\n| [click](bad) `run`")
        self.assertNotIn("<script>", value)
        self.assertNotIn("\n", value)
        self.assertNotIn("|", value)
        self.assertNotIn("[", value)


if __name__ == "__main__":
    unittest.main()
