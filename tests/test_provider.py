import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / "bin" / "omalaunch-github"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
args=sys.argv[1:]
if args[:2] == ['auth', 'status']:
    if os.environ.get('GH_AUTH_LOG'):
        with open(os.environ['GH_AUTH_LOG'],'a') as f: f.write('auth status github.com\n')
    state=os.environ.get('GH_AUTH_STATE','valid')
    if state == 'valid': raise SystemExit(0)
    print('not logged into github.com', file=sys.stderr); raise SystemExit(1)
if os.environ.get('GH_FAIL'):
    print(os.environ.get('GH_FAIL_MESSAGE','authentication required'), file=sys.stderr); raise SystemExit(4)
method=args[args.index('--method')+1]
endpoint=args[args.index('--method')+2]
fields={}
if os.environ.get('GH_CALL_LOG'):
    with open(os.environ['GH_CALL_LOG'],'a') as f: f.write(method+' '+endpoint+'\n')
for i, value in enumerate(args):
    if value == '-f' and i+1 < len(args):
        key, data=args[i+1].split('=',1); fields[key]=data
if method == 'PATCH':
    with open(os.environ['GH_LOG'],'a') as f: f.write(method+' '+endpoint+'\n')
    raise SystemExit(0)
repo={'full_name':'acme/widgets','description':'Widget tools','language':'Python','html_url':'https://github.com/acme/widgets','archived':False,'private':False,'owner':{'login':'acme'},'default_branch':'main','stargazers_count':7,'forks_count':2,'open_issues_count':3,'updated_at':'2026-01-02T03:04:05Z'}
issue={'number':12,'title':'Fix widget','body':'Issue body','html_url':'https://github.com/acme/widgets/issues/12','repository_url':'https://api.github.com/repos/acme/widgets','user':{'login':'octo'},'assignees':[{'login':'dev'}],'labels':[{'name':'bug'}],'comments':2,'state':'open','created_at':'2026-01-01T00:00:00Z','updated_at':'2026-01-02T00:00:00Z'}
pr=dict(issue, number=13, title='Improve widget', html_url='https://github.com/acme/widgets/pull/13', pull_request={'url':'x'})
notification={'id':'99','unread':True,'reason':'review_requested','updated_at':'2026-01-02T00:00:00Z','repository':repo,'subject':{'title':'Improve widget','type':'PullRequest','url':os.environ.get('GH_SUBJECT_URL','https://api.github.com/repos/acme/widgets/pulls/13')}}
if endpoint == 'user': out={'login':'acme'}
elif endpoint == 'user/repos': out=[repo]
elif endpoint == 'search/issues':
    is_pr='is:pr' in fields.get('q',''); out={'total_count':2 if is_pr else 4,'items':[pr if is_pr else issue]}
elif endpoint in ('notifications','repos/acme/widgets/notifications'): out=[notification]
elif endpoint == 'repos/acme/widgets': out=repo
elif endpoint == 'repos/acme/widgets/issues/12': out=issue
elif endpoint == 'repos/acme/widgets/pulls/13':
    out=dict(pr, requested_reviewers=[{'login':'reviewer'}], statuses_url='https://api.github.com/repos/acme/widgets/commits/abc/status', draft=False, merged=False, head={'ref':'feature','sha':'abc'}, base={'ref':'main'}, additions=10, deletions=3, changed_files=2, mergeable=True)
elif endpoint == 'repos/acme/widgets/commits/abc/status': out=[{'state':'success'},{'state':'success'}]
elif endpoint == 'repos/acme/widgets/commits/abc/check-runs': out={'check_runs':[{'name':'Tests','status':'completed','conclusion':'success'},{'name':'Build','status':'completed','conclusion':'failure'}]}
elif endpoint.endswith('/actions/runs'):
    out=json.loads(os.environ['GH_RUNS_JSON']) if os.environ.get('GH_RUNS_JSON') else {'workflow_runs':[{'id':77,'name':'CI','display_title':'Improve widget','head_branch':'feature','head_sha':'abc','event':'pull_request','status':'completed','conclusion':'failure','updated_at':'2026-01-02T00:00:00Z'}]}
elif endpoint == 'repos/acme/widgets/actions/runs/77': out={'id':77,'name':'CI','run_number':9,'head_branch':'feature','head_sha':'abc','event':'pull_request','status':'completed','conclusion':'failure','actor':{'login':'octo'},'created_at':'2026-01-02T00:00:00Z','updated_at':'2026-01-02T00:01:00Z','html_url':'https://github.com/acme/widgets/actions/runs/77'}
elif endpoint == 'repos/acme/widgets/actions/runs/77/jobs': out={'jobs':[{'name':'Tests','status':'completed','conclusion':'success','started_at':'2026-01-02T00:00:00Z','completed_at':'2026-01-02T00:00:30Z'},{'name':'Build','status':'completed','conclusion':'failure'}]}
elif endpoint == 'notifications/threads/99': out=notification
else:
    print('unexpected endpoint '+endpoint,file=sys.stderr); raise SystemExit(2)
json.dump(out,sys.stdout)
'''


class ProviderTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bin = Path(self.temp.name)
        fake = self.bin / "gh"
        fake.write_text(FAKE_GH)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        for command in ("omarchy-launch-editor", "omarchy-agent"):
            launcher = self.bin / command
            launcher.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$LAUNCH_LOG\"\n")
            launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
        self.log = self.bin / "gh.log"
        self.call_log = self.bin / "gh-calls.log"
        self.env = os.environ.copy()
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.env["HOME"] = str(self.bin / "home")
        self.env["GH_LOG"] = str(self.log)
        self.env["GH_CALL_LOG"] = str(self.call_log)
        self.env["GH_AUTH_LOG"] = str(self.bin / "gh-auth.log")
        self.env["LAUNCH_LOG"] = str(self.bin / "launch.log")
        self.env["XDG_STATE_HOME"] = str(self.bin / "state")

    def tearDown(self):
        self.temp.cleanup()

    def run_provider(self, *args):
        result = subprocess.run([str(PROVIDER), *args], env=self.env, text=True,
                                capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def write_config(self, content):
        path = Path(self.env["HOME"]) / ".config/omarchy/omalaunch/extensions/quantumfire.github.jsonc"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_root_is_static_and_global_search_loads_separately(self):
        rows = self.run_provider("root")
        self.assertEqual([row["label"] for row in rows],
                         ["Repositories", "Issues", "Pull Requests", "Notifications", "Configuration"])
        self.assertTrue(all(row["globalSearch"] is False for row in rows))
        self.assertTrue(all(row["starAction"] == "star" for row in rows[:4]))
        self.assertNotIn("starAction", rows[4])
        self.assertTrue(all(row["submenu"]["refreshCommand"][-1] == "--refresh" for row in rows))
        search_rows = self.run_provider("global-search")
        self.assertEqual([row["id"] for row in search_rows], [
            "general:repositories", "general:issues", "general:pull-requests", "general:notifications"])
        self.assertEqual([row["label"] for row in search_rows], [
            "GitHub · Repositories", "GitHub · Issues", "GitHub · Pull Requests", "GitHub · Notifications"])
        self.assertIn("repos", search_rows[0]["aliases"])
        self.assertIn("prs", search_rows[2]["aliases"])
        self.assertNotIn("general:configuration", [row["id"] for row in search_rows])
        self.assertTrue(all(not row["starred"] for row in search_rows))
        self.assertFalse(any(row["id"].startswith("issue:") for row in search_rows))
        self.assertFalse(any(row["id"].startswith("pr:") for row in search_rows))
        self.assertFalse(any(row["id"].startswith("notification:") for row in search_rows))
        self.assertFalse(self.call_log.exists(), "static shortcuts must not call GitHub")

    def test_unauthenticated_root_offers_bounded_login_and_recheck(self):
        self.env["GH_AUTH_STATE"] = "missing"
        rows = self.run_provider("root")
        setup = next(row for row in rows if row["id"] == "setup")
        self.assertEqual(setup["badge"], "Required")
        self.assertFalse(self.call_log.exists(), "authentication onboarding must not call the GitHub API")

        actions = self.run_provider("setup")
        login = actions[0]
        self.assertEqual(login["command"], ["xdg-terminal-exec", "--hold", "--", "gh",
                                                   "auth", "login", "--hostname", "github.com"])
        self.assertTrue(login["closeOnDispatch"])
        self.assertEqual(actions[1]["submenu"]["command"], [str(PROVIDER), "setup"])
        self.assertNotIn("scope", " ".join(login["command"]))
        self.assertNotIn("token", json.dumps(rows + actions).lower())

        self.env["GH_AUTH_STATE"] = "valid"
        ready = self.run_provider("setup")
        self.assertEqual(ready[0]["badge"], "Ready")
        self.assertNotIn("setup", [row["id"] for row in self.run_provider("root")])
        self.assertFalse(self.call_log.exists())

    def test_configuration_menu_opens_editor_or_default_agent(self):
        rows = self.run_provider("configuration")
        self.assertEqual([row["label"] for row in rows], ["Open config file", "Edit with agent"])
        config_path = str(Path(self.env["HOME"]) / ".config/omarchy/omalaunch/extensions/quantumfire.github.jsonc")
        self.assertEqual(rows[0]["command"], [str(PROVIDER), "open-config"])
        self.assertEqual(rows[1]["command"], [str(PROVIDER), "edit-config-agent"])
        self.assertTrue(all(row["closeOnDispatch"] for row in rows))

        self.run_provider("open-config")
        config = Path(config_path)
        self.assertTrue(config.is_file())
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertIn('"version": 1', config.read_text())
        self.assertEqual((self.bin / "launch.log").read_text().strip(), config_path)

        self.run_provider("edit-config-agent")
        launch = (self.bin / "launch.log").read_text()
        self.assertIn("--prompt", launch)
        self.assertIn(config_path, launch)
        self.assertIn("config.example.jsonc", launch)
        self.assertIn("concise summary of the settings they can change", launch)
        self.assertIn("ask what they want to change", launch)
        self.assertIn("Do not change the configuration until the user provides follow-up instructions", launch)

    def test_configuration_menu_reports_invalid_config(self):
        self.write_config('{"version":1,"unknown":true}')
        rows = self.run_provider("configuration")
        self.assertEqual(rows[0]["label"], "Invalid configuration")
        self.assertEqual(rows[0]["badgeTone"], "danger")
        self.assertIn("unknown root field", rows[0]["description"])
        self.assertEqual(rows[0]["command"], [str(PROVIDER), "open-config"])

    def test_repository_drills_into_lists_and_overview(self):
        rows = self.run_provider("repository", "acme/widgets")
        self.assertEqual([row["label"] for row in rows[:5]],
                         ["Overview", "Issues", "Pull Requests", "Notifications", "Actions"])
        self.assertTrue(all(row.get("icon") for row in rows))
        self.assertTrue(all(row.get("starredLabel", "").startswith("acme/widgets · ") for row in rows[:5]))
        self.assertIn("document", rows[0])
        self.assertTrue(all("submenu" in row for row in rows[1:5]))
        self.assertEqual([row["badge"] for row in rows[1:4]], ["4", "2", "1"])
        document = self.run_provider("repo-document", "acme/widgets")
        self.assertEqual(document["title"], "acme/widgets")
        self.assertTrue(document["icon"])
        self.assertEqual([stat["label"] for stat in document["stats"]], ["Stars", "Forks", "Open issues"])
        self.assertEqual(len(document["actions"]), 2)

    def test_combined_work_lists_show_repository_first_and_keep_dates(self):
        for command, expected_id, expected_detail in (
                ("issues", "issue:acme/widgets#12", "#12"),
                ("pull-requests", "pr:acme/widgets#13", "#13"),
                ("notifications", "notification:99", "review_requested")):
            row = self.run_provider(command)[0]
            self.assertEqual(row["id"], expected_id)
            self.assertTrue(row["description"].startswith("acme/widgets · "))
            self.assertIn(expected_detail, row["description"])
            self.assertTrue(row["trailingText"])

    def test_repository_work_lists_do_not_repeat_repository(self):
        for command, expected_id, expected_detail in (
                ("repo-issues", "issue:acme/widgets#12", "#12"),
                ("repo-pull-requests", "pr:acme/widgets#13", "#13"),
                ("repo-notifications", "notification:99", "review_requested")):
            row = self.run_provider(command, "acme/widgets")[0]
            self.assertEqual(row["id"], expected_id)
            self.assertNotIn("acme/widgets", row["description"])
            self.assertIn(expected_detail, row["description"])
            self.assertTrue(row["trailingText"])
            self.assertIn("document", row)

    def test_issue_and_pr_documents_include_details(self):
        issue = self.run_provider("issue-document", "acme/widgets", "12")
        self.assertEqual(issue["status"], "Open")
        self.assertEqual(issue["sections"][0]["text"], "Issue body")
        self.assertEqual(issue["sections"][0]["format"], "markdown")
        pull = self.run_provider("pr-document", "acme/widgets", "13")
        fields = {field["label"]: field["value"] for field in pull["fields"]}
        self.assertEqual(fields["Checks"], "1 passed · 1 failed")
        self.assertEqual(pull["sections"][0]["heading"], "Checks")
        self.assertIn("Build — Failure", pull["sections"][0]["text"])
        self.assertIn("feature", fields["Branches"])
        self.assertEqual(pull["sections"][0]["format"], "markdown")

    def test_gh_failure_is_reported_without_partial_json(self):
        env = self.env.copy()
        env["GH_FAIL"] = "1"
        result = subprocess.run([str(PROVIDER), "repositories"], env=env, text=True,
                                capture_output=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("authentication is invalid", result.stderr)

    def test_api_failures_distinguish_auth_network_rate_and_permission_without_secrets(self):
        cases = (
            ("Bad credentials token ghp_supersecret", "authentication is invalid"),
            ("connection timed out", "could not be reached"),
            ("API rate limit exceeded", "rate limit reached"),
            ("403 Resource not accessible by personal access token", "denied this request"),
        )
        for message, expected in cases:
            env = dict(self.env, GH_FAIL="1", GH_FAIL_MESSAGE=message)
            result = subprocess.run([str(PROVIDER), "repositories"], env=env, text=True,
                                    capture_output=True, timeout=8)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stderr)
            self.assertNotIn("ghp_supersecret", result.stderr)
        self.assertIn("will not expand", result.stderr)

    def test_notification_rejects_non_github_api_host(self):
        env = self.env.copy()
        env["GH_SUBJECT_URL"] = "https://evil.example/repos/acme/widgets/issues/12"
        result = subprocess.run([str(PROVIDER), "notification-document", "99"], env=env,
                                text=True, capture_output=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported GitHub API host", result.stderr)

    def test_config_can_enable_repository_global_search(self):
        self.write_config('''{
          "version": 1,
          "repositories": {"globalSearch": {"enabled": true, "scope": "owned", "limit": 10}}
        }''')
        rows = self.run_provider("global-search")
        self.assertEqual(len(rows), 5)
        self.assertTrue(any(row["id"].startswith("repository:") for row in rows))

    def test_config_enables_exact_work_items_and_excludes_repository_defaults(self):
        self.write_config('''{
          "version": 1,
          "repositories": {"globalSearch": {"enabled": true, "scope": "owned", "limit": 10,
            "overrides": {"acme/widgets": false}}},
          "issues": {"globalSearch": {"enabled": false, "overrides": {"acme/widgets#12": true}}},
          "pullRequests": {"globalSearch": {"enabled": false, "overrides": {"acme/widgets#13": true}}},
          "notifications": {"globalSearch": {"enabled": false}},
          "globalSearch": {"excludedRepositories": ["acme/widgets"]},
        }''')
        rows = self.run_provider("global-search")
        self.assertFalse(any(row["id"].startswith("repo:") for row in rows))
        self.assertTrue(any(row["id"].startswith("issue:") for row in rows))
        self.assertTrue(any(row["id"].startswith("pr:") for row in rows))
        self.assertFalse(any(row["id"].startswith("notification:") for row in rows))

    def test_invalid_config_uses_quiet_defaults(self):
        self.write_config('{"version":1,"unknown":true}')
        result = subprocess.run([str(PROVIDER), "global-search"], env=self.env, text=True,
                                capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0)
        self.assertIn("ignored invalid configuration", result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual([row["id"] for row in rows], [
            "general:repositories", "general:issues", "general:pull-requests", "general:notifications"])
        self.assertFalse(self.call_log.exists())

    def cache_files(self):
        cache = Path(self.env["XDG_STATE_HOME"]) / "omarchy/omalaunch/extensions/quantumfire.github-cache"
        return sorted(cache.glob("*.json"))

    def test_lists_use_cache_and_explicit_refresh_bypasses_it(self):
        self.run_provider("repositories")
        self.run_provider("repositories")
        calls = self.call_log.read_text().splitlines()
        self.assertEqual(calls.count("GET user/repos"), 1)
        self.run_provider("repositories", "--refresh")
        calls = self.call_log.read_text().splitlines()
        self.assertEqual(calls.count("GET user/repos"), 2)

    def test_expired_and_corrupt_cache_entries_are_replaced(self):
        self.run_provider("repositories")
        cache_file = self.cache_files()[0]
        os.utime(cache_file, (0, 0))
        self.run_provider("repositories")
        self.assertEqual(self.call_log.read_text().splitlines().count("GET user/repos"), 2)
        cache_file.write_text("{")
        self.run_provider("repositories")
        self.assertEqual(self.call_log.read_text().splitlines().count("GET user/repos"), 3)
        json.loads(cache_file.read_text())

    def test_cache_writes_are_private_and_leave_no_temporary_file(self):
        self.run_provider("repositories")
        cache_file = self.cache_files()[0]
        self.assertEqual(cache_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(cache_file.parent.glob(".*.tmp")), [])

    def test_failed_refresh_preserves_the_previous_cache(self):
        self.run_provider("repositories")
        cache_file = self.cache_files()[0]
        previous = cache_file.read_bytes()
        failing_env = dict(self.env, GH_FAIL="1")
        result = subprocess.run([str(PROVIDER), "repositories", "--refresh"], env=failing_env,
                                text=True, capture_output=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(cache_file.read_bytes(), previous)
        self.run_provider("repositories")
        self.assertEqual(self.call_log.read_text().splitlines().count("GET user/repos"), 1)

    def test_expired_cache_is_used_when_normal_refresh_fails(self):
        expected = self.run_provider("repositories")
        cache_file = self.cache_files()[0]
        os.utime(cache_file, (0, 0))
        result = subprocess.run([str(PROVIDER), "repositories"], env=dict(self.env, GH_FAIL="1"),
                                text=True, capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), expected)

    def test_star_updates_are_locked_and_invalid_state_is_not_overwritten(self):
        commands = [
            [str(PROVIDER), "set-star", "general:issues", "true"],
            [str(PROVIDER), "set-star", "general:notifications", "true"],
        ]
        processes = [subprocess.Popen(command, env=self.env, text=True, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE) for command in commands]
        for process in processes:
            _, error = process.communicate(timeout=8)
            self.assertEqual(process.returncode, 0, error)
        state_path = Path(self.env["XDG_STATE_HOME"]) / "omarchy/omalaunch/extensions/quantumfire.github.json"
        state = json.loads(state_path.read_text())
        self.assertEqual(set(state["stars"]), {"general:issues", "general:notifications"})
        self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)

        state_path.write_text('{"version":1,"stars":[],"unknown":true}')
        previous = state_path.read_text()
        result = subprocess.run([str(PROVIDER), "set-star", "general:issues", "true"], env=self.env,
                                text=True, capture_output=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state_path.read_text(), previous)

    def test_general_and_repository_shortcuts_publish_distinct_starred_labels(self):
        repository_rows = self.run_provider("repositories")
        self.assertEqual(repository_rows[0]["starAction"], "star")
        self.assertEqual(repository_rows[0]["starredLabel"], "acme/widgets")
        self.run_provider("set-star", "general:issues", "true")
        self.run_provider("set-star", "repository:acme/widgets", "true")
        self.run_provider("set-star", "repo:acme/widgets:actions", "true")
        root = self.run_provider("root")
        issues = next(row for row in root if row["label"] == "Issues")
        self.assertTrue(issues["starred"])
        search = self.run_provider("global-search")
        self.assertEqual(len(search), len({row["id"] for row in search}))
        labels = [row["starredLabel"] for row in search if row.get("starred")]
        self.assertIn("GitHub · Issues", labels)
        self.assertIn("acme/widgets", labels)
        self.assertIn("acme/widgets · Actions", labels)
        starred_repository = next(row for row in search if row.get("starredLabel") == "acme/widgets")
        self.assertIn("submenu", starred_repository)
        repo = self.run_provider("repository", "acme/widgets")
        actions = next(row for row in repo if row["label"] == "Actions")
        self.assertTrue(actions["starred"])

    def test_top_level_actions_are_disabled_without_api_requests(self):
        snapshot = self.run_provider("preload")
        self.assertEqual(snapshot["topLevelItems"], [])
        self.assertEqual([row["id"] for row in snapshot["globalSearchItems"]], [
            "general:repositories", "general:issues", "general:pull-requests", "general:notifications"])
        self.assertFalse(self.call_log.exists())

    def test_top_level_actions_filter_order_deduplicate_and_route(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        old = (now - timedelta(minutes=60)).isoformat().replace("+00:00", "Z")
        runs = {"workflow_runs": [
            {"id": 1, "name": "Active", "status": "in_progress", "updated_at": old},
            {"id": 2, "name": "Failed", "status": "completed", "conclusion": "failure", "completed_at": recent},
            {"id": 2, "name": "Duplicate", "status": "completed", "conclusion": "failure", "completed_at": recent},
            {"id": 3, "name": "Old success", "status": "completed", "conclusion": "success", "completed_at": old},
        ]}
        self.env["GH_RUNS_JSON"] = json.dumps(runs)
        self.write_config('''{"version":1,"actions":{"topLevel":{"enabled":true,
          "repositories":["acme/widgets"],"statuses":["in_progress","success","failure"],
          "completedWithinMinutes":30,"limit":5}}}''')
        snapshot = self.run_provider("preload")
        rows = snapshot["topLevelItems"]
        self.assertEqual([row["label"] for row in rows], ["acme/widgets · Active", "acme/widgets · Failed"])
        self.assertEqual(len({row["id"] for row in rows}), 2)
        self.assertTrue(all(row["topLevel"] and row["globalSearch"] is False for row in rows))
        self.assertEqual(rows[0]["document"]["command"][-2:], ["acme/widgets", "1"])

    def test_top_level_config_bounds_are_rejected(self):
        self.write_config('{"version":1,"actions":{"topLevel":{"enabled":true,"repositories":[],"limit":21}}}')
        result = subprocess.run([str(PROVIDER), "preload"], env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["topLevelItems"], [])
        self.assertIn("actions.topLevel.limit", result.stderr)

    def test_action_runs_show_semantic_status_and_job_details(self):
        rows = self.run_provider("repo-actions", "acme/widgets")
        self.assertEqual(rows[0]["badge"], "Failure")
        self.assertEqual(rows[0]["badgeTone"], "danger")
        self.assertTrue(rows[0]["trailingText"])
        document = self.run_provider("action-run-document", "acme/widgets", "77")
        self.assertEqual(document["status"], "Failure")
        self.assertIn("Tests — Success", document["sections"][0]["text"])
        self.assertIn("Build — Failure", document["sections"][0]["text"])

    def test_notification_requires_explicit_mark_read(self):
        document = self.run_provider("notification-document", "99")
        self.assertEqual(document["status"], "Unread")
        mark = next(action for action in document["actions"] if action["id"] == "mark-read")
        self.assertEqual(mark["command"][-2:], ["mark-read", "99"])
        self.assertFalse(self.log.exists())
        self.run_provider("mark-read", "99")
        self.assertEqual(self.log.read_text(), "PATCH notifications/threads/99\n")


if __name__ == "__main__":
    unittest.main()
