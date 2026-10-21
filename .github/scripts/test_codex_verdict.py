import copy
import json
import unittest

from codex_verdict import APP_ID, BOT, BOT_ID, SUMMARY, eligible

HEAD = 'a' * 40
OLD = 'b' * 40


def review(sha=HEAD, **changes):
    return dict(commit_sha=sha, status='completed', has_any_findings=False,
                has_unresolved_findings=False, **changes)


def comment(code=None, security=None):
    state = {'code_review': review() if code is None else code}
    if security is not None:
        state['security_review'] = security
    return {'user': {'login': BOT, 'type': 'Bot', 'id': BOT_ID},
            'performed_via_github_app': {'id': APP_ID}, 'editor': None,
            'body': SUMMARY + '\n<!-- codex-review-state:v1 ' + json.dumps(state) + ' -->'}


class VerdictTests(unittest.TestCase):
    def test_clean_and_bot_edited(self):
        row = comment()
        self.assertTrue(eligible(row, HEAD))
        row['editor'] = {'login': BOT[:-5], '__typename': 'Bot'}
        self.assertTrue(eligible(row, HEAD))
        row['editor'] = {'login': BOT[:-5], '__typename': 'User'}
        self.assertFalse(eligible(row, HEAD))
        row['editor'] = {'login': BOT, 'type': 'Bot'}
        self.assertTrue(eligible(row, HEAD))

    def test_stale_and_unfinished_code(self):
        self.assertFalse(eligible(comment(review(OLD)), HEAD))
        for status in ('running', 'pending', 'failed', 'cancelled', 'queued', 'mystery'):
            state = review()
            state['status'] = status
            with self.subTest(status=status):
                self.assertFalse(eligible(comment(state), HEAD))

    def test_findings_and_strict_booleans(self):
        for key in ('has_any_findings', 'has_unresolved_findings'):
            for value in (True, 0, 1, None, 'false'):
                state = review()
                state[key] = value
                self.assertFalse(eligible(comment(state), HEAD))
            state.pop(key)
            self.assertFalse(eligible(comment(state), HEAD))

    def test_forged_identity_app_and_editor(self):
        for key, value in [('user', {'login': BOT, 'type': 'User'}),
                           ('user', {'login': 'other[bot]', 'type': 'Bot'}),
                           ('performed_via_github_app', {'id': str(APP_ID)}),
                           ('performed_via_github_app', {'id': 15368}),
                           ('editor', {'login': 'maintainer', '__typename': 'User'})]:
            row = comment()
            row[key] = value
            self.assertFalse(eligible(row, HEAD))
        row = comment()
        del row['editor']
        self.assertFalse(eligible(row, HEAD))

    def test_rest_author_id_is_mandatory_and_numeric(self):
        for identity in (None, BOT_ID + 1, str(BOT_ID), True):
            row = comment()
            row['user']['id'] = identity
            self.assertFalse(eligible(row, HEAD))
        row = comment()
        del row['user']['id']
        self.assertFalse(eligible(row, HEAD))

    def test_malformed_multiple_unknown_and_duplicate_json(self):
        for body in ('👍', SUMMARY, comment()['body'] * 2,
                     SUMMARY + '<!-- codex-review-state:v1 {} -->',
                     SUMMARY + '<!-- codex-review-state:v1 {broken} -->',
                     SUMMARY + '<!-- codex-review-state:v1 {"code_review":{},"code_review":{}} -->'):
            row = comment()
            row['body'] = body
            self.assertFalse(eligible(row, HEAD))
        state = review()
        state['extra'] = 'unknown'
        self.assertFalse(eligible(comment(state), HEAD))

    def test_security_policy(self):
        self.assertTrue(eligible(comment(), HEAD))
        self.assertFalse(eligible(comment(), HEAD, require_security_review=True))
        self.assertTrue(eligible(comment(security=review(OLD)), HEAD))
        self.assertFalse(eligible(comment(security=review(OLD)), HEAD, require_security_review=True))
        self.assertTrue(eligible(comment(security=review()), HEAD, require_security_review=True))
        for status in ('running', 'failed', 'pending'):
            state = review()
            state['status'] = status
            self.assertTrue(eligible(comment(security=state), HEAD))
            self.assertFalse(eligible(comment(security=state), HEAD, require_security_review=True))
        state = review()
        state.update(status='running', has_any_findings=None, has_unresolved_findings=None)
        self.assertTrue(eligible(comment(security=state), HEAD))
        self.assertFalse(eligible(comment(security=state), HEAD, require_security_review=True))

    def test_optional_incomplete_security_does_not_delay_clean_code(self):
        for status in ('running', 'pending', 'queued', 'failed', 'cancelled'):
            state = review(OLD)
            state.update(status=status, has_any_findings=None, has_unresolved_findings=None)
            with self.subTest(status=status):
                self.assertTrue(eligible(comment(security=state), HEAD))
                self.assertFalse(eligible(comment(security=state), HEAD, require_security_review=True))
                state['commit_sha'] = HEAD
                self.assertTrue(eligible(comment(security=state), HEAD))
                self.assertFalse(eligible(comment(security=state), HEAD, require_security_review=True))

    def test_optional_security_never_ignores_known_findings(self):
        for status in ('completed', 'running', 'pending', 'queued', 'failed', 'cancelled'):
            for key in ('has_any_findings', 'has_unresolved_findings'):
                state = review()
                state['status'] = status
                state[key] = True
                with self.subTest(status=status, key=key):
                    self.assertFalse(eligible(comment(security=state), HEAD))

    def test_native_disabled_security_block(self):
        disabled = dict.fromkeys(review())
        self.assertTrue(eligible(comment(security=disabled), HEAD))
        self.assertFalse(eligible(comment(security=disabled), HEAD, require_security_review=True))
        self.assertFalse(eligible(comment(code=review(OLD), security=disabled), HEAD))
        for key in disabled:
            changed = dict(disabled)
            changed[key] = False
            self.assertFalse(eligible(comment(security=changed), HEAD))
        for changed in ({}, {**disabled, 'extra': None}, None):
            row = comment()
            row['body'] = (SUMMARY + '\n<!-- codex-review-state:v1 '
                           + json.dumps({'code_review': review(), 'security_review': changed}) + ' -->')
            self.assertFalse(eligible(row, HEAD))

    def test_optional_security_never_replaces_current_clean_code(self):
        security = review()
        security.update(status='running', has_any_findings=None, has_unresolved_findings=None)
        self.assertFalse(eligible(comment(code=review(OLD), security=security), HEAD))
        for status in ('running', 'pending', 'queued', 'failed', 'cancelled'):
            code = review()
            code.update(status=status, has_any_findings=None, has_unresolved_findings=None)
            self.assertFalse(eligible(comment(code=code, security=security), HEAD))

    def test_nullable_incomplete_code_never_approves(self):
        for status in ('running', 'pending', 'queued', 'failed', 'cancelled'):
            state = review()
            state.update(status=status, has_any_findings=None, has_unresolved_findings=None)
            self.assertFalse(eligible(comment(code=state), HEAD))

    def test_nullable_state_still_rejects_completed_and_malformed_flags(self):
        for key in ('has_any_findings', 'has_unresolved_findings'):
            for value in (None, 'false', 0, 1, {}, []):
                state = review(OLD)
                state[key] = value
                self.assertFalse(eligible(comment(security=state), HEAD))
            for value in ('false', 0, 1, {}, []):
                state = review(OLD)
                state.update(status='running', has_any_findings=None, has_unresolved_findings=None)
                state[key] = value
                self.assertFalse(eligible(comment(security=state), HEAD))
        for change in ({'status': 'unknown'}, {'unexpected': None}):
            state = review(OLD)
            state.update(status='running', has_any_findings=None, has_unresolved_findings=None)
            state.update(change)
            self.assertFalse(eligible(comment(security=state), HEAD))

    def test_bad_input_never_approves(self):
        for head in (None, '', 'a' * 39, 'G' * 40):
            self.assertFalse(eligible(comment(), head))
        for row in (None, [], {}, copy.copy({'body': None})):
            self.assertFalse(eligible(row, HEAD))


if __name__ == '__main__':
    unittest.main()
