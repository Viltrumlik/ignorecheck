<h1 align="center">ignorecheck</h1>

<p align="center">
  <b>Find files git tracks that it should not.</b>
</p>

<p align="center">
  <a href="https://github.com/Viltrumlik/ignorecheck/actions/workflows/ci.yml"><img src="https://github.com/Viltrumlik/ignorecheck/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen" alt="Zero dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT"></a>
</p>

Adding a line to `.gitignore` does nothing to a file git is already tracking. The rule sits there looking correct, the file keeps being committed, and everybody assumes it is handled.

```console
$ ignorecheck
TRACKED  config/secrets.yml   matches .gitignore:4 -- the rule does nothing while the file is tracked
SECRET   frontend/.env.production  secrets live here
junk     .DS_Store            macOS folder metadata

3 findings, 2 serious
to stop tracking without deleting: git rm --cached <path>
```

## The three things it looks for

**TRACKED** — git tracks the file *and* a `.gitignore` rule matches it. This is the silent one: somebody wrote the rule, so it looks handled, but git ignores rules for files already in the index. The finding names the file and line of the rule that is doing nothing.

**SECRET** — `.env`, `.env.production`, `*.pem`, `id_rsa`, key stores. Templates like `.env.example`, `.env.sample` and `.env.template` are meant to be committed and are left alone.

**junk** — `.DS_Store`, `__pycache__`, `node_modules`, `*.log`, editor leftovers. Not dangerous, just weight and noise in every diff.

Exit codes: `0` clean · `1` not a git repository · `2` usage · `3` findings.

## In CI

```yaml
- run: pipx install git+https://github.com/Viltrumlik/ignorecheck
- run: ignorecheck
```

A pull request that adds a `.env` turns the build red instead of turning into an incident.

## What it does not do

It does not look for rules that match nothing. An early version did, and it was wrong: `dist/`, `build/` and `.DS_Store` are *preventive* rules — matching nothing today is exactly what a correct one looks like. A check that fires on correct configuration teaches people to ignore the tool, so it was removed.

It does not read file contents, and it never prints them. It reports paths.

## Install

```bash
pipx install git+https://github.com/Viltrumlik/ignorecheck
```

Or take the file:

```bash
curl -O https://raw.githubusercontent.com/Viltrumlik/ignorecheck/main/ignorecheck.py
python3 ignorecheck.py
```

## Development

```bash
python3 -m unittest discover -s tests -v
```

16 tests, each building a real repository so the findings are checked against real git behaviour — including the part that makes this work: `git check-ignore` says nothing about a tracked file unless you pass `--no-index`, which is the whole case this tool exists for. CI runs on Ubuntu, macOS and Windows with Python 3.9 through 3.13.

## License

[MIT](LICENSE) © Alisher Muhammadaliyev ([@Viltrumlik](https://github.com/Viltrumlik))
