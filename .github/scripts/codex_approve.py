"""Turn a verified native Codex verdict into a dedicated GitHub App approval.

Dry-run is the default. This file only reads PR content as API data; it never
checks out or executes PR files. Keep it and its workflow protected by CODEOWNERS.
"""
import argparse
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from codex_verdict import APP_ID, BOT, SUMMARY, eligible

REPOSITORY = "BBS-GuT/smartcity-roboter"
REPOSITORY_ID = 1428070579
PREFIX = "/repos/" + REPOSITORY
WORKFLOW = "Codex - Mergefreigabe"
MARKER = "<!-- codex-approval-bridge:v1 -->"
CHECKS = {
    "D1 / Python-Syntax (3.10)",
    "D1 / Shell-Syntax (bash)",
    "D1 / Softwaretests (Ubuntu 22.04, Python 3.10)",
}
OWNER_LINES = [
    "/.github/ @letsc4 @davidheinrich73",
    "AGENTS.md @letsc4 @davidheinrich73",
    "CODEOWNERS @letsc4 @davidheinrich73",
    "/docs/entwicklung/D-reviewbot.md @letsc4 @davidheinrich73",
]
CI_PATH = ".github/workflows/grundbetrieb-tests.yml"
CI_WORKFLOW_ID = 391455112


class API:
    def __init__(self, token):
        self.token = token
        self.allow_writes = False

    def request(self, method, path, body=None):
        # Never follow API-provided URLs or send credentials to another host.
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("invalid API path")
        if method != "GET" and path != "/graphql" and not (self.allow_writes and self.token):
            raise ValueError("API writes require the configured App token and --apply")
        headers = {"Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "smartcity-codex-approval-bridge"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        data = None if body is None else json.dumps(body).encode("utf-8")
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request("https://api.github.com" + path,
                                         data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
        return json.loads(raw) if raw else None

    def get(self, path):
        return self.request("GET", path)

    def pages(self, path, key=None):
        result = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 101):
            data = self.get(f"{path}{separator}per_page=100&page={page}")
            rows = data[key] if key else data
            if not isinstance(rows, list):
                raise ValueError("invalid paginated API data")
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise ValueError("pagination limit exceeded")

    def graphql(self, query, variables):
        data = self.request("POST", "/graphql", {"query": query, "variables": variables})
        if data.get("errors") or not isinstance(data.get("data"), dict):
            raise ValueError("GraphQL metadata unavailable")
        return data["data"]


def protected_path(path):
    return (path.startswith(".github/") or path.split("/")[-1].lower() in
            {"agents.md", "codeowners"} or
            path == "docs/entwicklung/D-reviewbot.md")


def approval_identity(api, *, required=False):
    """Resolve the configured App's bot account; never fall back to Actions/PAT."""
    raw_id = os.environ.get("BBS_CODEX_APPROVAL_APP_ID", "")
    login = os.environ.get("BBS_CODEX_APPROVAL_BOT_LOGIN", "")
    if not raw_id and not login and not required:
        return None
    if (not raw_id.isdecimal() or int(raw_id) in {APP_ID, 15368, 0}
            or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]*\[bot\]", login)
            or login in {BOT, "github-actions[bot]"}):
        raise ValueError("dedicated approval App is not configured")
    user = api.get("/users/" + urllib.parse.quote(login, safe=""))
    if user.get("type") != "Bot" or user.get("login") != login or type(user.get("id")) is not int:
        raise ValueError("approval App bot identity cannot be verified")
    return {"app_id": int(raw_id), "login": login, "user_id": user["id"]}


def own_approval(review, identity):
    if not identity:
        return False
    user = review.get("user") or {}
    app = review.get("performed_via_github_app")
    return (user.get("login") == identity["login"] and user.get("id") == identity["user_id"]
            and user.get("type") == "Bot" and MARKER in (review.get("body") or "")
            and review.get("state") == "APPROVED"
            and (app is None or isinstance(app, dict) and app.get("id") == identity["app_id"]))


def counted_approval(api, review, number, sha, identity):
    """Check current counting metadata for this own review, not merge readiness."""
    if (not own_approval(review, identity) or review.get("commit_id") != sha
            or not isinstance(review.get("node_id"), str)):
        return False
    node = api.graphql("""query($id: ID!) { node(id: $id) {
      ... on PullRequestReview {
        databaseId state authorCanPushToRepository commit { oid }
        author { __typename login }
        pullRequest { number repository { databaseId } }
      }
    }}""", {"id": review["node_id"]}).get("node")
    if not isinstance(node, dict):
        return False
    author = node.get("author") or {}
    pr = node.get("pullRequest") or {}
    return (node.get("databaseId") == review["id"] and node.get("state") == "APPROVED"
            and node.get("authorCanPushToRepository") is True
            and (node.get("commit") or {}).get("oid") == sha
            and author.get("__typename") == "Bot"
            and author.get("login") == identity["login"].removesuffix("[bot]")
            and pr.get("number") == number
            and (pr.get("repository") or {}).get("databaseId") == REPOSITORY_ID)


def blocking_review(reviews):
    # A COMMENTED review does not retract an earlier REQUEST_CHANGES.
    latest = {}
    for review in sorted(reviews, key=lambda row: row["id"]):
        if review.get("state") in {"APPROVED", "CHANGES_REQUESTED"}:
            latest[review["user"]["id"]] = review["state"]
    return "CHANGES_REQUESTED" in latest.values()


def native_guards(api):
    rule = api.get(PREFIX + "/rulesets/25533179")
    # GitHub hides bypass actors from tokens without ruleset-write permission.
    # Do not grant the approval App Administration just to inspect that field;
    # repository administrators audit bypass configuration separately.
    if (rule.get("enforcement") != "active"
            or "bypass_actors" in rule and rule["bypass_actors"] != []
            or rule.get("conditions", {}).get("ref_name", {}).get("include") != ["refs/heads/main"]
            or rule.get("conditions", {}).get("ref_name", {}).get("exclude") != []):
        return False
    # Effective rules contain only active rules actually applying to main. This
    # read needs Metadata permission, including for the narrowly scoped App.
    effective = api.get(PREFIX + "/rules/branches/main")
    if not isinstance(effective, list):
        return False
    rules = {row["type"]: row.get("parameters", {}) for row in effective
             if row.get("ruleset_id") == 25533179}
    pr = rules.get("pull_request", {})
    ci = rules.get("required_status_checks", {})
    contexts = {(row.get("context"), row.get("integration_id"))
                for row in ci.get("required_status_checks", [])}
    guards = (pr.get("required_approving_review_count", 0) >= 1
            and pr.get("dismiss_stale_reviews_on_push") is True
            and pr.get("required_review_thread_resolution") is True
            and pr.get("require_code_owner_review") is True
            and ci.get("strict_required_status_checks_policy") is True
            and {(name, 15368) for name in CHECKS} <= contexts
            and "deletion" in rules and "non_fast_forward" in rules)
    owners = api.get(PREFIX + "/contents/.github/CODEOWNERS?ref=main")
    if owners.get("encoding") != "base64":
        return False
    text = base64.b64decode(owners["content"], validate=False).decode("utf-8")
    lines = [line.strip() for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    return guards and lines == OWNER_LINES


def editor(api, comment):
    data = api.graphql("""query($id: ID!) { node(id: $id) {
      ... on IssueComment { body editor { __typename login } }
    }}""", {"id": comment["node_id"]})["node"]
    if not isinstance(data, dict) or "editor" not in data or data.get("body") != comment.get("body"):
        raise ValueError("comment changed while reading editor metadata")
    return data.get("editor")


def unresolved_threads(api, number):
    cursor = None
    for _ in range(100):
        data = api.graphql("""query($number: Int!, $cursor: String) {
          repository(owner: "BBS-GuT", name: "smartcity-roboter") {
            pullRequest(number: $number) { reviewThreads(first: 100, after: $cursor) {
              nodes { isResolved } pageInfo { hasNextPage endCursor }
            } }
          }
        }""", {"number": number, "cursor": cursor})
        threads = data["repository"]["pullRequest"]["reviewThreads"]
        if any(row.get("isResolved") is not True for row in threads["nodes"]):
            return True
        page = threads["pageInfo"]
        if not page["hasNextPage"]:
            return False
        if not page["endCursor"] or page["endCursor"] == cursor:
            raise ValueError("invalid review-thread pagination")
        cursor = page["endCursor"]
    raise ValueError("review-thread pagination limit exceeded")


def ci_workflow_path(path):
    # GitHub may qualify the API path with @ref. Identify the workflow file
    # separately; workflow ID, event, exact SHA and PR association remain gates.
    if not isinstance(path, str):
        return False
    filename, separator, ref = path.partition("@")
    return filename == CI_PATH and (not separator or bool(ref))


def trusted_ci(api, checks, number, sha):
    """Use the newest actual PR D1 run; ignore duplicate push-run check names."""
    runs = api.pages(PREFIX + f"/actions/workflows/{CI_WORKFLOW_ID}/runs?head_sha={sha}&event=pull_request", "workflow_runs")
    candidates = [run for run in runs if ci_workflow_path(run.get("path"))
                  and run.get("workflow_id") == CI_WORKFLOW_ID and run.get("event") == "pull_request"
                  and run.get("head_sha") == sha and (run.get("repository") or {}).get("id") == REPOSITORY_ID
                  and any(row.get("number") == number and (row.get("head") or {}).get("sha") == sha
                          and (row.get("base") or {}).get("ref") == "main"
                          and ((row.get("base") or {}).get("repo") or {}).get("id") == REPOSITORY_ID
                          for row in run.get("pull_requests", []))]
    if not candidates:
        return False
    run = max(candidates, key=lambda row: row["id"])
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return False
    run_id = run["id"]
    jobs = api.pages(PREFIX + f"/actions/runs/{run_id}/jobs?filter=latest", "jobs")
    for name in CHECKS:
        matches = [job for job in jobs if job.get("name") == name]
        if len(matches) != 1:
            return False
        job = matches[0]
        check_url = re.fullmatch(re.escape("https://api.github.com" + PREFIX)
                                 + r"/check-runs/([1-9][0-9]*)", job.get("check_run_url", ""))
        if (not check_url or job.get("run_id") != run_id or job.get("status") != "completed"
                or job.get("conclusion") != "success"):
            return False
        check_id = int(check_url[1])
        actual = [check for check in checks if check.get("id") == check_id]
        if len(actual) != 1:
            return False
        check = actual[0]
        # A spoofed check cannot point to an unrelated real Actions job: this
        # API-owned job links back to the exact check ID and selected PR run.
        if (check.get("name") != name or check.get("head_sha") != sha
                or (check.get("app") or {}).get("id") != 15368
                or check.get("status") != "completed" or check.get("conclusion") != "success"
                or (check.get("check_suite") or {}).get("id") != run.get("check_suite_id")
                or check.get("details_url") != f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/job/{job['id']}"):
            return False
    return True


def snapshot(api, number, reviews):
    pr = api.get(PREFIX + f"/pulls/{number}")
    sha = pr["head"]["sha"]
    if pr.get("state") != "open" or pr.get("draft") or pr["base"]["ref"] != "main":
        return pr, "PR ist geschlossen, Draft oder hat ein anderes Ziel"
    files = api.pages(PREFIX + f"/pulls/{number}/files")
    if len(files) != pr.get("changed_files"):
        return pr, "Dateiliste ist unvollstaendig"
    if any(protected_path(row["filename"]) or protected_path(row.get("previous_filename", "")) for row in files):
        return pr, "Kontrolldateien erfordern eine Codeowner-Freigabe"
    comments = api.pages(PREFIX + f"/issues/{number}/comments")
    summaries = [row for row in comments if
                 (row.get("user") or {}).get("login") == BOT
                 and (row.get("performed_via_github_app") or {}).get("id") == APP_ID
                 and SUMMARY in (row.get("body") or "")]
    if len(summaries) != 1:
        return pr, "Kein eindeutiger nativer Codex-Status"
    summary = dict(summaries[0])
    summary["editor"] = editor(api, summary)
    if not eligible(summary, sha):
        return pr, "Codex-Review fehlt, ist veraltet oder nicht sauber abgeschlossen"
    checks = api.pages(PREFIX + f"/commits/{sha}/check-runs?filter=all", "check_runs")
    if not trusted_ci(api, checks, number, sha):
        return pr, "D1-CI fuer den aktuellen PR-Commit ist nicht nachweisbar gruen"
    if blocking_review(reviews):
        return pr, "Eine bestehende Aenderungsanforderung blockiert"
    if unresolved_threads(api, number):
        return pr, "Offene Review-Threads blockieren"
    return pr, None


def dismiss(api, number, reviews, apply, identity):
    for review in reviews:
        if own_approval(review, identity):
            if apply:
                api.request("PUT", PREFIX + f"/pulls/{number}/reviews/{review['id']}/dismissals",
                            {"message": "Automatische Freigabe zurueckgezogen: Voraussetzungen nicht mehr erfuellt."})


def approval_result(api, review, number, sha, identity, apply, success_action):
    if not counted_approval(api, review, number, sha, identity):
        dismiss(api, number, [review], apply, identity)
        return {"number": number, "action": "uncounted", "sha": sha,
                "reason": "GitHub bestaetigt keine angerechnete Pflichtfreigabe",
                "approval_counted": False, "merge_readiness": "not-evaluated"}
    after = api.get(PREFIX + f"/pulls/{number}")
    if after["head"]["sha"] != sha or after.get("draft") or after.get("state") != "open":
        dismiss(api, number, [review], apply, identity)
        return {"number": number, "action": "revoked-after-push", "sha": sha}
    return {"number": number, "action": success_action, "sha": sha,
            "approval_counted": True, "merge_readiness": "not-evaluated"}


def reconcile(api, number, *, apply=False, identity=None):
    if apply and not identity:
        raise ValueError("a verified dedicated approval App is required")
    reviews = api.pages(PREFIX + f"/pulls/{number}/reviews")
    try:
        if not native_guards(api):
            raise ValueError("Native Schutzregeln fehlen oder sind nicht lesbar")
        pr, reason = snapshot(api, number, reviews)
        if reason:
            dismiss(api, number, reviews, apply, identity)
            return {"number": number, "action": "blocked", "reason": reason}
        sha = pr["head"]["sha"]
        existing = next((row for row in reversed(reviews)
                         if own_approval(row, identity) and row.get("commit_id") == sha), None)
        if existing:
            return approval_result(api, existing, number, sha, identity, apply, "already-approved")
        # Read all evidence again immediately before the write. Bind the review to
        # the checked SHA; dismiss it if a concurrent push is observed afterward.
        fresh_reviews = api.pages(PREFIX + f"/pulls/{number}/reviews")
        fresh, reason = snapshot(api, number, fresh_reviews)
        if reason or fresh["head"]["sha"] != sha:
            dismiss(api, number, fresh_reviews, apply, identity)
            return {"number": number, "action": "blocked", "reason": reason or "PR-Commit hat sich geaendert"}
        if not apply:
            return {"number": number, "action": "would-approve", "sha": sha}
        body = (MARKER + "\nAutomatische Freigabebruecke (`" + identity["login"] + "`) auf Basis des sauberen nativen Codex-Reviews "
                "und der gruenen D1-CI fuer Commit `" + sha + "`.\n"
                "Dies ist keine menschliche Codepruefung und keine Freigabe fuer den Roboterbetrieb. "
                "Diese Automatisierung mergt keine PRs.")
        review = api.request("POST", PREFIX + f"/pulls/{number}/reviews",
                             {"event": "APPROVE", "commit_id": sha, "body": body})
        reviews.append(review)
        return approval_result(api, review, number, sha, identity, True, "approved")
    except (KeyError, TypeError, ValueError, urllib.error.URLError):
        # Fail closed; do not print response bodies, authentication data, or PR text.
        dismiss(api, number, reviews, apply, identity)
        return {"number": number, "action": "blocked", "reason": "API-Daten oder Schutzregeln nicht sicher pruefbar"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Nur im vertrauenswuerdigen Main-Workflow schreiben")
    parser.add_argument("--pr", type=int, help="Optional nur diese PR-Nummer pruefen")
    args = parser.parse_args()
    if args.apply and not (os.environ.get("GITHUB_ACTIONS") == "true"
                          and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
                          and os.environ.get("GITHUB_REPOSITORY_ID") == str(REPOSITORY_ID)
                          and os.environ.get("GITHUB_REF") == "refs/heads/main"
                          and os.environ.get("GITHUB_WORKFLOW") == WORKFLOW):
        parser.error("--apply ist nur im vorgesehenen Main-Workflow erlaubt")
    api = API(os.environ.get("GH_TOKEN", ""))
    if api.get(PREFIX).get("id") != REPOSITORY_ID:
        raise SystemExit("Falsches Repository")
    identity = approval_identity(api, required=args.apply)
    api.allow_writes = args.apply
    prs = ([{"number": args.pr}] if args.pr else
           api.pages(PREFIX + "/pulls?state=open&base=main"))
    for pr in prs:
        print(json.dumps(reconcile(api, pr["number"], apply=args.apply, identity=identity), ensure_ascii=True))


if __name__ == "__main__":
    main()
