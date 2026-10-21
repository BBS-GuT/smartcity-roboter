"""Offline integration tests: no network, credentials or GitHub writes."""
import base64
import copy
import json
import unittest
from unittest.mock import patch

import codex_approve as bridge

SHA = "a" * 40
OTHER = "b" * 40
IDENTITY = {"app_id": 9999999, "user_id": 8888888, "login": "bbs-codex-approval[bot]"}


def run(api, number, **kwargs):
    return bridge.reconcile(api, number, identity=IDENTITY, **kwargs)


def review(identifier=10, state="APPROVED", own=True, sha=SHA):
    return {"id": identifier, "node_id": f"REVIEW_{identifier}", "state": state, "commit_id": sha,
            "user": {"id": IDENTITY["user_id"] if own else 123,
                     "login": IDENTITY["login"] if own else "developer", "type": "Bot" if own else "User"},
            "body": bridge.MARKER if own else "human review"}


class FakeAPI:
    def __init__(self):
        self.writes = []
        self.reviews = []
        self.pr = {"number": 1, "state": "open", "draft": False,
                   "base": {"ref": "main"}, "head": {"sha": SHA}, "changed_files": 1}
        self.heads = []
        self.files = [{"filename": "software/component.py"}]
        self.owner_text = "\n".join(bridge.OWNER_LINES)
        self.rules = {"enforcement": "active", "bypass_actors": [],
                      "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}}, "rules": [
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
                "required_review_thread_resolution": True, "require_code_owner_review": True}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": name, "integration_id": 15368} for name in bridge.CHECKS]}},
            {"type": "deletion"}, {"type": "non_fast_forward"}]}
        state = {"code_review": {"commit_sha": SHA, "status": "completed",
                                  "has_any_findings": False, "has_unresolved_findings": False}}
        self.comments = [{"id": 1, "node_id": "COMMENT_1", "user": {
            "login": bridge.BOT, "type": "Bot", "id": 199175422}, "performed_via_github_app": {"id": bridge.APP_ID},
            "body": bridge.SUMMARY + "\n<!-- codex-review-state:v1 " + json.dumps(state) + " -->"}]
        self.editor = {"__typename": "Bot", "login": bridge.BOT.removesuffix("[bot]")}
        self.editor_body = None
        self.checks = [{"id": i, "name": name, "head_sha": SHA, "app": {"id": 15368},
                        "status": "completed", "conclusion": "success", "check_suite": {"id": 555},
                        "details_url": f"https://github.com/BBS-GuT/smartcity-roboter/actions/runs/777/job/{i}"}
                       for i, name in enumerate(bridge.CHECKS, 1001)]
        self.run = {"id": 777, "path": bridge.CI_PATH, "workflow_id": bridge.CI_WORKFLOW_ID,
                    "event": "pull_request", "head_sha": SHA, "repository": {"id": bridge.REPOSITORY_ID},
                    "status": "completed", "conclusion": "success",
                    "check_suite_id": 555, "pull_requests": [{"number": 1, "head": {"sha": SHA},
                        "base": {"ref": "main", "repo": {"id": bridge.REPOSITORY_ID}}}]}
        self.job_change = {}
        self.extra_runs = []
        self.effective_rules = None
        self.thread_pages = [{"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}]
        self.fail_after_write = False
        self.counting_changes = {}
        self.counting_missing = False
        self.counting_error = False
        self.counting_queries = []

    def get(self, path):
        if "/rulesets/" in path:
            return copy.deepcopy(self.rules)
        if "/rules/branches/main" in path:
            return (copy.deepcopy(self.effective_rules) if self.effective_rules is not None else
                    [dict(row, ruleset_id=25533179) for row in copy.deepcopy(self.rules["rules"])])
        if "/contents/" in path:
            return {"encoding": "base64", "content": base64.b64encode(self.owner_text.encode()).decode()}
        if "/actions/jobs/" in path:
            job_id = int(path.rsplit("/", 1)[1])
            check = next(row for row in self.checks if row["id"] == job_id)
            return dict({"id": job_id, "run_id": 777, "name": check["name"], "status": "completed",
                         "conclusion": "success", "check_run_url": f"https://api.github.com{bridge.PREFIX}/check-runs/{job_id}"},
                        **self.job_change)
        if "/actions/runs/" in path:
            return copy.deepcopy(self.run)
        if "/pulls/" in path:
            if self.fail_after_write and self.writes:
                raise ValueError("API unavailable after write")
            pr = copy.deepcopy(self.pr)
            if self.heads:
                pr["head"]["sha"] = self.heads.pop(0)
            return pr
        raise AssertionError(path)

    def pages(self, path, key=None):
        if path.endswith("/reviews"):
            return copy.deepcopy(self.reviews)
        if path.endswith("/files"):
            return copy.deepcopy(self.files)
        if path.endswith("/comments"):
            return copy.deepcopy(self.comments)
        if "/check-runs" in path:
            return copy.deepcopy(self.checks)
        if "/actions/workflows/" in path:
            return copy.deepcopy([self.run] + self.extra_runs)
        if "/jobs?" in path:
            return [self.get(bridge.PREFIX + f"/actions/jobs/{check['id']}") for check in self.checks
                    if check["id"] < 2000]
        raise AssertionError(path)

    def graphql(self, query, variables):
        if "authorCanPushToRepository" in query:
            self.counting_queries.append(variables["id"])
            if self.counting_error:
                raise ValueError("counting API metadata unavailable")
            node = {"databaseId": int(variables["id"].split("_")[-1]), "state": "APPROVED",
                    "authorCanPushToRepository": True, "commit": {"oid": SHA},
                    "author": {"__typename": "Bot", "login": IDENTITY["login"].removesuffix("[bot]")},
                    "pullRequest": {"number": 1, "repository": {"databaseId": bridge.REPOSITORY_ID}}}
            node.update(self.counting_changes)
            if self.counting_missing:
                del node["authorCanPushToRepository"]
            return {"node": node}
        if "IssueComment" in query:
            return {"node": {"body": self.editor_body if self.editor_body is not None else self.comments[0]["body"],
                             "editor": self.editor}}
        result = self.thread_pages[0] if len(self.thread_pages) == 1 else self.thread_pages.pop(0)
        return {"repository": {"pullRequest": {"reviewThreads": copy.deepcopy(result)}}}

    def request(self, method, path, body):
        self.writes.append((method, path, copy.deepcopy(body)))
        if method == "POST":
            created = review(identifier=999)
            created["body"] = body["body"]
            return created
        return {"state": "DISMISSED"}


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()

    def test_default_dry_run_never_writes(self):
        self.assertEqual(run(self.api, 1)["action"], "would-approve")
        self.assertEqual(self.api.writes, [])

    def test_apply_approves_explicit_sha_once_and_is_honest(self):
        self.assertEqual(run(self.api, 1, apply=True)["action"], "approved")
        method, _, body = self.api.writes[0]
        self.assertEqual((method, body["event"], body["commit_id"]), ("POST", "APPROVE", SHA))
        self.assertIn("keine menschliche", body["body"])
        self.assertIn("keine Freigabe fuer den Roboterbetrieb", body["body"])

    def test_idempotent_existing_current_approval(self):
        self.api.reviews = [review()]
        result = run(self.api, 1, apply=True)
        self.assertEqual(result["action"], "already-approved")
        self.assertIs(result["approval_counted"], True)
        self.assertEqual(result["merge_readiness"], "not-evaluated")
        self.assertEqual(self.api.writes, [])

    def test_uncounted_new_and_existing_reviews_never_report_success(self):
        for existing in [False, True]:
            for missing, value in [(False, False), (False, None), (True, None)]:
                with self.subTest(existing=existing, missing=missing, value=value):
                    self.api = FakeAPI()
                    foreign = review(20, own=False)
                    self.api.reviews = ([review()] if existing else []) + [foreign]
                    self.api.counting_changes["authorCanPushToRepository"] = value
                    self.api.counting_missing = missing
                    result = run(self.api, 1, apply=True)
                    self.assertEqual(result["action"], "uncounted")
                    self.assertIs(result["approval_counted"], False)
                    self.assertEqual(result["merge_readiness"], "not-evaluated")
                    expected_id = 10 if existing else 999
                    withdrawals = [row for row in self.api.writes if row[0] == "PUT"]
                    self.assertEqual(len(withdrawals), 1)
                    self.assertIn(f"/reviews/{expected_id}/dismissals", withdrawals[0][1])
                    self.assertNotIn("/reviews/20/", withdrawals[0][1])
                    self.assertEqual(self.api.reviews[-1], foreign)

    def test_counting_api_errors_block_new_and_existing_reviews_safely(self):
        for existing in [False, True]:
            with self.subTest(existing=existing):
                self.api = FakeAPI()
                self.api.reviews = ([review()] if existing else []) + [review(20, own=False)]
                self.api.counting_error = True
                result = run(self.api, 1, apply=True)
                self.assertEqual(result["action"], "blocked")
                withdrawals = [row for row in self.api.writes if row[0] == "PUT"]
                self.assertEqual(len(withdrawals), 1)
                self.assertNotIn("/reviews/20/", withdrawals[0][1])

    def test_counting_accepts_only_own_marker_app_and_exact_head(self):
        foreign = review(20, own=False)
        unmarked = review()
        unmarked["body"] = "another review"
        wrong_app = review()
        wrong_app["performed_via_github_app"] = {"id": 15368}
        for candidate in [foreign, unmarked, wrong_app, review(sha=OTHER)]:
            with self.subTest(candidate=candidate):
                self.assertFalse(bridge.counted_approval(self.api, candidate, 1, SHA, IDENTITY))
        self.assertEqual(self.api.counting_queries, [])

    def test_counting_metadata_must_match_own_review_and_head(self):
        for key, value in [("databaseId", 11), ("state", "DISMISSED"),
                           ("authorCanPushToRepository", "true"), ("commit", {"oid": OTHER}),
                           ("author", {"__typename": "User", "login": "developer"}),
                           ("pullRequest", {"number": 2, "repository": {"databaseId": bridge.REPOSITORY_ID}})]:
            with self.subTest(key=key, value=value):
                self.api = FakeAPI()
                self.api.counting_changes[key] = value
                self.assertFalse(bridge.counted_approval(self.api, review(), 1, SHA, IDENTITY))

    def test_existing_counted_review_rechecks_current_head_before_success(self):
        self.api.reviews = [review()]
        self.api.heads = [SHA, OTHER]
        self.assertEqual(run(self.api, 1, apply=True)["action"], "revoked-after-push")
        self.assertEqual([row[0] for row in self.api.writes], ["PUT"])

    def test_ci_failure_revokes_only_own_marked_approval(self):
        self.api.reviews = [review(), review(identifier=11, own=False)]
        self.api.checks[0]["conclusion"] = "failure"
        self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
        self.assertEqual(len(self.api.writes), 1)
        self.assertIn("/reviews/10/dismissals", self.api.writes[0][1])

    def test_protected_paths_and_renames_cannot_auto_approve(self):
        for path in [".github/workflows/new.yml", "AGENTS.md", "docs/AGENTS.md", "CODEOWNERS",
                     "docs/entwicklung/D-reviewbot.md"]:
            for key in ["filename", "previous_filename"]:
                with self.subTest(path=path, key=key):
                    self.api.files = [{"filename": "docs/safe.md", key: path}]
                    self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
        self.assertEqual(self.api.writes, [])

    def test_comments_do_not_clear_change_requests(self):
        self.api.reviews = [review(1, "CHANGES_REQUESTED", own=False), review(2, "COMMENTED", own=False)]
        self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
        self.api.reviews[1]["state"] = "DISMISSED"
        self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
        self.api.reviews[0]["state"] = "DISMISSED"
        self.assertEqual(run(self.api, 1)["action"], "would-approve")

    def test_foreign_edited_and_duplicate_summary_block(self):
        original = copy.deepcopy(self.api.comments)
        for mutate in [lambda: self.api.comments[0]["user"].update(login="someone"),
                       lambda: self.api.comments[0]["performed_via_github_app"].update(id=0),
                       lambda: self.api.comments.append(copy.deepcopy(self.api.comments[0]))]:
            self.api.comments = copy.deepcopy(original)
            mutate()
            self.assertEqual(run(self.api, 1)["action"], "blocked")
        self.api.comments = original
        self.api.editor = {"__typename": "User", "login": "developer"}
        self.assertEqual(run(self.api, 1)["action"], "blocked")
        self.api.editor = None
        self.api.editor_body = "changed concurrently"
        self.assertEqual(run(self.api, 1)["action"], "blocked")

    def test_changed_head_before_approve_does_not_write(self):
        self.api.heads = [SHA, OTHER]
        self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
        self.assertEqual(self.api.writes, [])

    def test_changed_head_after_approve_dismisses_new_review(self):
        self.api.heads = [SHA, SHA, OTHER]
        self.assertEqual(run(self.api, 1, apply=True)["action"], "revoked-after-push")
        self.assertEqual([row[0] for row in self.api.writes], ["POST", "PUT"])
        self.assertIn("/reviews/999/dismissals", self.api.writes[1][1])

    def test_api_error_after_approve_also_dismisses_new_review(self):
        self.api.fail_after_write = True
        self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
        self.assertEqual([row[0] for row in self.api.writes], ["POST", "PUT"])

    def test_native_guard_and_codeowners_changes_fail_closed(self):
        self.api.rules["rules"][0]["parameters"]["require_code_owner_review"] = False
        self.assertEqual(run(self.api, 1)["action"], "blocked")
        self.api = FakeAPI()
        self.api.owner_text += "\n/.github/scripts/\n"
        self.assertEqual(run(self.api, 1)["action"], "blocked")

    def test_paginated_unresolved_thread_blocks(self):
        self.api.thread_pages = [
            {"nodes": [{"isResolved": True}], "pageInfo": {"hasNextPage": True, "endCursor": "next"}},
            {"nodes": [{"isResolved": False}], "pageInfo": {"hasNextPage": False, "endCursor": None}}]
        self.assertEqual(run(self.api, 1)["action"], "blocked")

    def test_stale_or_foreign_ci_check_does_not_count(self):
        self.api.checks[0]["head_sha"] = OTHER
        self.assertEqual(run(self.api, 1)["action"], "blocked")
        self.api.checks[0]["head_sha"] = SHA
        self.api.checks[0]["app"]["id"] = 999
        self.assertEqual(run(self.api, 1)["action"], "blocked")

    def test_apply_without_dedicated_app_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            bridge.reconcile(self.api, 1, apply=True)
        self.assertEqual(self.api.writes, [])

    def test_identity_configuration_never_falls_back_to_native_or_actions_bot(self):
        for app_id, login in [("15368", "github-actions[bot]"),
                              (str(bridge.APP_ID), bridge.BOT), ("9999999", "letsc4"),
                              ("", ""), ("bad", IDENTITY["login"])]:
            with self.subTest(app_id=app_id, login=login):
                with patch.dict("os.environ", {"BBS_CODEX_APPROVAL_APP_ID": app_id,
                                               "BBS_CODEX_APPROVAL_BOT_LOGIN": login}):
                    with self.assertRaises(ValueError):
                        bridge.approval_identity(self.api, required=True)

    def test_own_review_identity_and_marker_are_both_required(self):
        own = review()
        self.assertTrue(bridge.own_approval(own, IDENTITY))
        own["body"] = "unrelated approval by same bot"
        self.assertFalse(bridge.own_approval(own, IDENTITY))
        own["body"] = bridge.MARKER
        own["performed_via_github_app"] = {"id": 15368}
        self.assertFalse(bridge.own_approval(own, IDENTITY))

    def test_local_apply_flag_is_rejected_before_network(self):
        with patch("sys.argv", ["codex_approve.py", "--apply"]), patch.dict("os.environ", {}, clear=True):
            with patch("codex_approve.API.get") as api_get, patch("sys.stderr"):
                with self.assertRaises(SystemExit) as error:
                    bridge.main()
                self.assertEqual(error.exception.code, 2)
                api_get.assert_not_called()

    def test_dry_run_api_blocks_mutations(self):
        api = bridge.API("readonly-token")
        with self.assertRaises(ValueError):
            api.request("POST", bridge.PREFIX + "/pulls/1/reviews", {"event": "APPROVE"})

    def test_forged_ci_from_other_branch_or_workflow_does_not_count(self):
        for key, value in [("event", "push"), ("event", "workflow_dispatch"),
                           ("path", ".github/workflows/fake.yml"), ("head_sha", OTHER),
                           ("workflow_id", 999), ("repository", {"id": 999}),
                           ("pull_requests", [{"number": 2}]), ("check_suite_id", 999)]:
            with self.subTest(key=key, value=value):
                self.api = FakeAPI()
                self.api.run[key] = value
                self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
                self.assertEqual(self.api.writes, [])

    def test_ref_qualified_ci_workflow_paths_are_accepted(self):
        for ref in ["main", "refs/heads/main", "refs/pull/1/merge", SHA]:
            with self.subTest(ref=ref):
                self.api.run["path"] = bridge.CI_PATH + "@" + ref
                self.assertEqual(run(self.api, 1)["action"], "would-approve")
                self.assertEqual(self.api.writes, [])

    def test_ref_qualification_does_not_relax_ci_run_identity(self):
        for key, value in [("path", ".github/workflows/fake.yml@main"),
                           ("path", bridge.CI_PATH + "@"), ("workflow_id", 999),
                           ("event", "push"), ("head_sha", OTHER),
                           ("pull_requests", [{"number": 2}])]:
            with self.subTest(key=key, value=value):
                self.api = FakeAPI()
                self.api.run["path"] = bridge.CI_PATH + "@main"
                self.api.run[key] = value
                self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
                self.assertEqual(self.api.writes, [])

    def test_forged_ci_details_url_and_check_job_mismatch_do_not_count(self):
        self.api.checks[0]["details_url"] = "https://attacker.example/job/1001"
        self.assertEqual(run(self.api, 1)["action"], "blocked")
        self.api = FakeAPI()
        self.api.job_change["check_run_url"] = f"https://api.github.com{bridge.PREFIX}/check-runs/666"
        self.assertEqual(run(self.api, 1)["action"], "blocked")

    def test_duplicate_push_checks_do_not_block_a_valid_pr_run(self):
        duplicates = copy.deepcopy(self.api.checks)
        for row in duplicates:
            row["id"] += 1000
            row["details_url"] = row["details_url"].replace("/runs/777/", "/runs/888/")
        self.api.checks.extend(duplicates)
        self.assertEqual(run(self.api, 1)["action"], "would-approve")

    def test_newer_failed_or_pending_pr_run_blocks_older_success(self):
        for status, conclusion in [("completed", "failure"), ("in_progress", None)]:
            with self.subTest(status=status):
                newer = copy.deepcopy(self.api.run)
                newer.update(id=888, status=status, conclusion=conclusion)
                self.api.extra_runs = [newer]
                self.assertEqual(run(self.api, 1, apply=True)["action"], "blocked")
                self.assertEqual(self.api.writes, [])

    def test_least_privilege_rules_response_without_hidden_bypass_is_supported(self):
        del self.api.rules["bypass_actors"]
        self.assertTrue(bridge.native_guards(self.api))
        self.assertEqual(run(self.api, 1)["action"], "would-approve")
        self.api.rules["bypass_actors"] = [{"actor_id": 123, "actor_type": "Integration"}]
        self.assertFalse(bridge.native_guards(self.api))

    def test_only_effective_rules_of_expected_main_ruleset_count(self):
        self.api.effective_rules = []
        self.assertFalse(bridge.native_guards(self.api))
        self.api.effective_rules = [dict(row, ruleset_id=999) for row in self.api.rules["rules"]]
        self.assertFalse(bridge.native_guards(self.api))
        self.api.effective_rules = [dict(copy.deepcopy(row), ruleset_id=25533179)
                                    for row in self.api.rules["rules"]]
        self.api.effective_rules[0]["parameters"]["require_code_owner_review"] = False
        self.assertFalse(bridge.native_guards(self.api))


if __name__ == "__main__":
    unittest.main()
