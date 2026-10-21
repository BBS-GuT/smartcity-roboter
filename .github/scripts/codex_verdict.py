"""Offline policy only. Callers must fetch trusted metadata from GitHub APIs."""
import json
import re

BOT = 'chatgpt-codex-connector[bot]'
BOT_ID = 199175422
APP_ID = 1144995
SUMMARY = '<!-- codex-pull-request-review-summary -->'
STATE = re.compile(r'<!-- codex-review-state:v1 (.*?) -->', re.DOTALL)
SHA = re.compile(r'[0-9a-f]{40}\Z')
FIELDS = {'commit_sha', 'status', 'has_any_findings', 'has_unresolved_findings'}
INCOMPLETE_STATUSES = {'running', 'pending', 'failed', 'cancelled', 'queued'}
STATUSES = {'completed'} | INCOMPLETE_STATUSES


def _bot(actor):
    if not isinstance(actor, dict):
        return False
    if 'type' in actor:
        return actor['type'] == 'Bot' and actor.get('login') == BOT
    return actor.get('__typename') == 'Bot' and actor.get('login') == BOT[:-5]


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate JSON key')
        obj[key] = value
    return obj


def _valid_state(state):
    return (isinstance(state, dict) and set(state) == FIELDS
            and isinstance(state['commit_sha'], str)
            and SHA.fullmatch(state['commit_sha']) is not None
            and isinstance(state['status'], str) and state['status'] in STATUSES
            and all(type(state[key]) is bool or (
                state[key] is None and state['status'] in INCOMPLETE_STATUSES)
                for key in ('has_any_findings', 'has_unresolved_findings')))


def _clean(state, head_sha):
    return (state['commit_sha'] == head_sha and state['status'] == 'completed'
            and state['has_any_findings'] is False
            and state['has_unresolved_findings'] is False)


def eligible(comment, head_sha, *, require_security_review=False):
    """Return True only for a clean current native Codex summary.

    `comment` is REST issue-comment data enriched with GraphQL `editor` (null
    or Bot identity). Missing editor metadata blocks approval. Current
    security findings still block approval. An optional security review need not
    finish; set require_security_review to demand a clean current security
    review. Stale security results never grant approval. This function does not
    evaluate CI, review threads, or PR state.
    """
    if not isinstance(head_sha, str) or SHA.fullmatch(head_sha) is None:
        return False
    if not isinstance(comment, dict):
        return False
    author = comment.get('user')
    if (not _bot(author) or author.get('type') != 'Bot'
            or type(author.get('id')) is not int or author['id'] != BOT_ID):
        return False
    app = comment.get('performed_via_github_app')
    if not isinstance(app, dict) or type(app.get('id')) is not int or app['id'] != APP_ID:
        return False
    if 'editor' not in comment or (comment['editor'] is not None and not _bot(comment['editor'])):
        return False
    body = comment.get('body')
    if not isinstance(body, str) or body.count(SUMMARY) != 1:
        return False
    matches = STATE.findall(body)
    if len(matches) != 1 or body.count('<!-- codex-review-state:') != 1:
        return False
    try:
        state = json.loads(matches[0], object_pairs_hook=_unique_object)
        if not isinstance(state, dict) or not {'code_review'} <= set(state) <= {'code_review', 'security_review'}:
            return False
        code = state['code_review']
        security = state.get('security_review')
        if not _valid_state(code) or not _clean(code, head_sha):
            return False
        if 'security_review' in state:
            if not _valid_state(security):
                return False
            if security['commit_sha'] == head_sha:
                if require_security_review:
                    return _clean(security, head_sha)
                return (security['has_any_findings'] is not True
                        and security['has_unresolved_findings'] is not True)
        return not require_security_review
    except (ValueError, TypeError, RecursionError):
        return False
