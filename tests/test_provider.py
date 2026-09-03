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
if endpoint == 'user/repos': out=[repo]
elif endpoint == 'search/issues':
    is_pr='is:pr' in fields.get('q',''); out={'total_count':2 if is_pr else 4,'items':[pr if is_pr else issue]}
elif endpoint in ('notifications','repos/acme/widgets/notifications'): out=[notification]
elif endpoint == 'repos/acme/widgets': out=repo
elif endpoint == 'repos/acme/widgets/issues/12': out=issue
elif endpoint == 'repos/acme/widgets/pulls/13':
    out=dict(pr, requested_reviewers=[{'login':'reviewer'}], statuses_url='https://api.github.com/repos/acme/widgets/commits/abc/status', draft=False, merged=False, head={'ref':'feature'}, base={'ref':'main'}, additions=10, deletions=3, changed_files=2, mergeable=True)
elif endpoint == 'repos/acme/widgets/commits/abc/status': out=[{'state':'success'},{'state':'success'}]
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
        self.env = os.environ.copy()
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.env["GH_LOG"] = str(self.log)

    def tearDown(self):
        self.temp.cleanup()

    def run_provider(self, *args):
        result = subprocess.run([str(PROVIDER), *args], env=self.env, text=True,
                                capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def test_root_is_static_and_global_search_loads_separately(self):
        rows = self.run_provider("root")
        self.assertEqual([row["label"] for row in rows],
                         ["Repositories", "Issues", "Pull Requests", "Notifications"])
        self.assertTrue(all(row["globalSearch"] is False for row in rows))
        search_rows = self.run_provider("global-search")
        self.assertLessEqual(len(search_rows), 100)
        self.assertTrue(any(row["id"].startswith("repo:") and "submenu" in row for row in search_rows))
        self.assertTrue(any(row["id"].startswith("issue:") and "document" in row for row in search_rows))
        self.assertTrue(any(row["id"].startswith("pr:") and "document" in row for row in search_rows))
        self.assertTrue(any(row["id"].startswith("notification:") for row in search_rows))

    def test_repository_drills_into_lists_and_overview(self):
        rows = self.run_provider("repository", "acme/widgets")
        self.assertEqual([row["id"] for row in rows[:4]],
                         ["overview", "issues", "pull-requests", "notifications"])
        self.assertTrue(all(row.get("icon") for row in rows))
        self.assertIn("document", rows[0])
        self.assertTrue(all("submenu" in row for row in rows[1:4]))
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
        pull = self.run_provider("pr-document", "acme/widgets", "13")
        fields = {field["label"]: field["value"] for field in pull["fields"]}
        self.assertEqual(fields["Checks"], "Success")
        self.assertIn("feature", fields["Branches"])

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
