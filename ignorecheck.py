#!/usr/bin/env python3
"""ignorecheck - find files git tracks that it should not.

Adding a line to .gitignore does nothing to a file git is already
tracking. The rule sits there looking correct, the file keeps being
committed, and everybody assumes it is handled. `.env` is the one that
costs you.

    $ ignorecheck
    TRACKED  .env        matches .gitignore:3 -- the rule does nothing
    SECRET   deploy.pem  private key
    junk     .DS_Store   macOS folder metadata

Exit codes: 0 clean, 1 not a git repository, 2 usage, 3 findings.

Zero dependencies. Python 3.9+.
"""

import argparse
import json
import os
import re
import subprocess
import sys

VERSION = "0.1.0"
EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_FOUND = 0, 1, 2, 3

# Hech qachon repoda bo'lmasligi kerak bo'lgan narsalar. Birinchi guruh
# jiddiy: ular sir tutadi.
SECRET = [
    # .env.example va shunga o'xshash shablonlar ataylab commit qilinadi,
    # shuning uchun ular bu yerga tushmasligi kerak.
    (re.compile(r"(^|/)\.env(?!\.(example|sample|template|dist|defaults))(\.|$)"),
     "secrets live here"),
    (re.compile(r"\.pem$"), "private key"),
    (re.compile(r"\.p12$|\.pfx$"), "key store"),
    (re.compile(r"(^|/)id_(rsa|dsa|ecdsa|ed25519)$"), "private ssh key"),
    (re.compile(r"\.keystore$|\.jks$"), "key store"),
]
JUNK = [
    (re.compile(r"(^|/)\.DS_Store$"), "macOS folder metadata"),
    (re.compile(r"(^|/)Thumbs\.db$"), "Windows thumbnail cache"),
    (re.compile(r"\.pyc$|(^|/)__pycache__/"), "Python bytecode"),
    (re.compile(r"(^|/)node_modules/"), "installed dependencies"),
    (re.compile(r"(^|/)\.venv/|(^|/)venv/"), "virtual environment"),
    (re.compile(r"\.log$"), "log file"),
    (re.compile(r"(^|/)\.idea/"), "IDE settings"),
    (re.compile(r"\.swp$|~$"), "editor leftovers"),
    (re.compile(r"(^|/)\.pytest_cache/|(^|/)\.mypy_cache/"), "tool cache"),
]
MAX_CHECK = 5000     # check-ignore uchun yo'llar soni chegarasi


class Finding:
    def __init__(self, kind, path, message, rule=None):
        self.kind, self.path, self.message, self.rule = kind, path, message, rule

    def as_dict(self):
        d = {"kind": self.kind, "path": self.path, "message": self.message}
        if self.rule:
            d["rule"] = self.rule
        return d


def run(root, *args, **kw):
    return subprocess.run(["git", *args], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, universal_newlines=True,
                          errors="replace", **kw)


def repo_root(start):
    out = run(start, "rev-parse", "--show-toplevel")
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return os.path.realpath(out.stdout.strip())


def lines_of(root, *args):
    out = run(root, *args)
    if out.returncode != 0:
        return []
    return [l for l in out.stdout.split("\0" if "-z" in args else "\n") if l]


def tracked_but_ignored(root):
    """Git kuzatayotgan, lekin qoidaga tushadigan fayllar.

    Bu eng muhim topilma: qoida yozilgan, fayl esa allaqachon kuzatuvda
    bo'lgani uchun qoida unga ta'sir qilmaydi. Hamma "hal qilingan" deb
    o'ylab yuradi.
    """
    return lines_of(root, "ls-files", "-z", "-c", "-i", "--exclude-standard")


def which_rule(root, paths):
    """Har bir yo'l uchun qaysi qoida ishlaganini git'dan so'raydi."""
    if not paths:
        return {}
    # --no-index shart: usiz check-ignore kuzatuvdagi fayl haqida hech
    # narsa aytmaydi, bizda esa aynan o'shalar tekshiriladi.
    #
    # -z ham shart. Usiz chiqish "<fayl>:<qator>:<qoida>\t<yo'l>" bo'ladi va
    # uni ikki nuqta bo'yicha ajratish Windows'da buziladi: yo'lda "C:" bor.
    # -z bilan maydonlar NUL bilan ajratiladi va hech qanday taxmin kerak
    # emas.
    out = run(root, "check-ignore", "-v", "-z", "--no-index", "--stdin",
              input="\0".join(paths[:MAX_CHECK]) + "\0")
    fields = out.stdout.split("\0")
    found = {}
    for i in range(0, len(fields) - 3, 4):
        source, number, rule, path = fields[i:i + 4]
        if path:
            found[path] = ("%s:%s" % (source, number), rule)
    return found


def check(root):
    findings = []
    tracked = lines_of(root, "ls-files", "-z")
    ignored_tracked = set(tracked_but_ignored(root))
    rule_for = which_rule(root, sorted(ignored_tracked))

    for path in sorted(ignored_tracked):
        where, rule = rule_for.get(path, (None, None))
        findings.append(Finding(
            "tracked", path,
            "matches %s -- the rule does nothing while the file is tracked"
            % (where or ".gitignore"), rule))

    for path in tracked:
        if path in ignored_tracked:
            continue
        for pattern, why in SECRET:
            if pattern.search(path):
                findings.append(Finding("secret", path, why))
                break
        else:
            for pattern, why in JUNK:
                if pattern.search(path):
                    findings.append(Finding("junk", path, why))
                    break

    return findings


LABEL = {"tracked": "TRACKED", "secret": "SECRET ", "junk": "junk   "}


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="ignorecheck",
        description="Find files git tracks that it should not.",
        epilog="example: ignorecheck --json")
    p.add_argument("path", nargs="?", default=".", metavar="PATH")
    p.add_argument("--json", action="store_true")
    p.add_argument("--version", action="version", version="ignorecheck " + VERSION)
    args = p.parse_args(argv)

    start = os.path.abspath(args.path)
    if not os.path.isdir(start):
        print("error: not a folder: %s" % args.path, file=sys.stderr)
        return EXIT_USAGE
    root = repo_root(start)
    if root is None:
        print("error: not a git repository", file=sys.stderr)
        return EXIT_ERROR

    findings = check(root)

    if args.json:
        print(json.dumps({"ok": not findings,
                          "findings": [f.as_dict() for f in findings]},
                         indent=2, sort_keys=True, ensure_ascii=False))
    elif not findings:
        print("clean: nothing tracked that should not be")
    else:
        width = min(40, max(len(f.path) for f in findings))
        for f in findings:
            print("%s  %s  %s" % (LABEL[f.kind], f.path.ljust(width), f.message))
        serious = sum(1 for f in findings if f.kind in ("tracked", "secret"))
        print("\n%d finding%s, %d serious"
              % (len(findings), "" if len(findings) == 1 else "s", serious))
        if any(f.kind in ("tracked", "secret") for f in findings):
            print("to stop tracking without deleting: git rm --cached <path>")
    return EXIT_FOUND if findings else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
