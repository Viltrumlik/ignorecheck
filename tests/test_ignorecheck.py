"""Haqiqiy git repo quriladi; har bir topilma turi alohida tekshiriladi."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "ignorecheck.py")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="ignorecheck-"))
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.tmp, check=True,
                              capture_output=True, text=True)

    def add(self, rel, text="x\n"):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        self.git("add", "-f", rel)
        self.git("commit", "-q", "-m", "add " + rel)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, self.tmp, *args],
                              capture_output=True, text=True)

    def findings(self):
        return json.loads(self.run_cli("--json").stdout)["findings"]

    def kinds(self):
        return {(f["kind"], f["path"]) for f in self.findings()}


class TrackedButIgnoredTest(Base):
    def test_a_rule_that_cannot_work_is_reported(self):
        self.add("secrets.txt")
        self.add(".gitignore", "secrets.txt\n")
        found = [f for f in self.findings() if f["kind"] == "tracked"]
        self.assertEqual([f["path"] for f in found], ["secrets.txt"])
        self.assertIn("the rule does nothing", found[0]["message"])

    def test_the_rule_and_its_line_are_named(self):
        self.add("build.out")
        self.add(".gitignore", "# a comment\n*.out\n")
        found = [f for f in self.findings() if f["kind"] == "tracked"][0]
        self.assertEqual(found["rule"], "*.out")
        self.assertIn(".gitignore:2", found["message"])

    def test_a_file_that_is_ignored_and_untracked_is_not_a_finding(self):
        self.add(".gitignore", "ignored.txt\n")
        with open(os.path.join(self.tmp, "ignored.txt"), "w") as f:
            f.write("x")
        self.assertEqual(self.findings(), [])


class SecretTest(Base):
    def test_env_files_are_serious(self):
        self.add(".env", "KEY=value\n")
        self.assertIn(("secret", ".env"), self.kinds())

    def test_env_in_a_subfolder_counts(self):
        self.add("frontend/.env.production", "KEY=value\n")
        self.assertIn(("secret", "frontend/.env.production"), self.kinds())

    def test_templates_are_meant_to_be_committed(self):
        for name in (".env.example", ".env.sample", ".env.template"):
            self.add(name, "KEY=\n")
        self.assertEqual(self.findings(), [])

    def test_private_keys_are_serious(self):
        self.add("deploy.pem")
        self.add("id_rsa")
        kinds = self.kinds()
        self.assertIn(("secret", "deploy.pem"), kinds)
        self.assertIn(("secret", "id_rsa"), kinds)


class JunkTest(Base):
    def test_platform_junk(self):
        self.add(".DS_Store")
        self.assertIn(("junk", ".DS_Store"), self.kinds())

    def test_build_output_and_caches(self):
        self.add("app/__pycache__/mod.pyc")
        self.add("debug.log")
        kinds = self.kinds()
        self.assertIn(("junk", "app/__pycache__/mod.pyc"), kinds)
        self.assertIn(("junk", "debug.log"), kinds)

    def test_ordinary_source_is_left_alone(self):
        self.add("src/app.py", "print(1)\n")
        self.add("README.md", "# hi\n")
        self.assertEqual(self.findings(), [])


class CliTest(Base):
    def test_a_clean_repo_exits_zero(self):
        self.add("src/app.py")
        out = self.run_cli()
        self.assertEqual(out.returncode, 0)
        self.assertIn("clean", out.stdout)

    def test_findings_exit_three(self):
        self.add(".env", "K=v\n")
        out = self.run_cli()
        self.assertEqual(out.returncode, 3)
        self.assertIn("1 serious", out.stdout)

    def test_the_fix_is_spelled_out(self):
        self.add(".env", "K=v\n")
        self.assertIn("git rm --cached", self.run_cli().stdout)

    def test_junk_alone_is_not_called_serious(self):
        self.add(".DS_Store")
        self.assertIn("0 serious", self.run_cli().stdout)

    def test_outside_a_repository_it_says_so(self):
        plain = tempfile.mkdtemp(prefix="ignorecheck-plain-")
        self.addCleanup(shutil.rmtree, plain, True)
        out = subprocess.run([sys.executable, SCRIPT, plain],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("not a git repository", out.stderr)

    def test_a_missing_folder_is_a_usage_error(self):
        out = subprocess.run([sys.executable, SCRIPT, os.path.join(self.tmp, "no")],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
