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
if os.environ.get('GH_FAIL'):
    print('authentication required', file=sys.stderr); raise SystemExit(4)
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
elif endpoint == 'repos/acme/widgets/actions/runs': out={'workflow_runs':[{'id':77,'name':'CI','display_title':'Improve widget','head_branch':'feature','head_sha':'abc','event':'pull_request','status':'completed','conclusion':'failure','updated_at':'2026-01-02T00:00:00Z'}]}
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
        self.log = self.bin / "gh.log"
        self.call_log = self.bin / "gh-calls.log"
        self.env = os.environ.copy()
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.env["HOME"] = str(self.bin / "home")
        self.env["GH_LOG"] = str(self.log)
        self.env["GH_CALL_LOG"] = str(self.call_log)
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
        self.assertLessEqual(len(search_rows), 100)
        self.assertTrue(any(row["id"].startswith("repo:") and "submenu" in row for row in search_rows))
        self.assertFalse(any(row["id"].startswith("issue:") for row in search_rows))
        self.assertFalse(any(row["id"].startswith("pr:") for row in search_rows))
        self.assertFalse(any(row["id"].startswith("notification:") for row in search_rows))
        self.assertTrue(all(row.get("trailingText") for row in search_rows))

    def test_configuration_menu_opens_editor_or_default_agent(self):
        rows = self.run_provider("configuration")
        self.assertEqual([row["label"] for row in rows], ["Open config file", "Edit with agent"])
        config_path = str(Path(self.env["HOME"]) / ".config/omarchy/omalaunch/extensions/quantumfire.github.jsonc")
        self.assertEqual(rows[0]["command"], ["omarchy-launch-editor", config_path])
        self.assertEqual(rows[1]["command"][:2], ["omarchy-agent", "--prompt"])
        self.assertIn(config_path, rows[1]["command"][2])
        self.assertIn("config.example.jsonc", rows[1]["command"][2])
        self.assertTrue(all(row["closeOnSuccess"] for row in rows))

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
        self.assertIn("authentication required", result.stderr)

    def test_notification_rejects_non_github_api_host(self):
        env = self.env.copy()
        env["GH_SUBJECT_URL"] = "https://evil.example/repos/acme/widgets/issues/12"
        result = subprocess.run([str(PROVIDER), "notification-document", "99"], env=env,
                                text=True, capture_output=True, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported GitHub API host", result.stderr)

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
        self.assertTrue(any(row["id"].startswith("repo:") for row in rows))
        self.assertFalse(any(row["id"].startswith("issue:") for row in rows))

    def test_lists_use_cache_and_explicit_refresh_bypasses_it(self):
        self.run_provider("repositories")
        self.run_provider("repositories")
        calls = self.call_log.read_text().splitlines()
        self.assertEqual(calls.count("GET user/repos"), 1)
        self.run_provider("repositories", "--refresh")
        calls = self.call_log.read_text().splitlines()
        self.assertEqual(calls.count("GET user/repos"), 2)

    def test_general_and_repository_shortcuts_publish_distinct_starred_labels(self):
        self.run_provider("set-star", "general:issues", "true")
        self.run_provider("set-star", "repo:acme/widgets:actions", "true")
        root = self.run_provider("root")
        issues = next(row for row in root if row["label"] == "Issues")
        self.assertTrue(issues["starred"])
        search = self.run_provider("global-search")
        labels = [row["starredLabel"] for row in search if row.get("starred")]
        self.assertIn("GitHub · Issues", labels)
        self.assertIn("acme/widgets · Actions", labels)
        repo = self.run_provider("repository", "acme/widgets")
        actions = next(row for row in repo if row["label"] == "Actions")
        self.assertTrue(actions["starred"])

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
