# Contributing

Thanks for helping make git-explained better. Bug reports, ideas and pull requests are all welcome.

## Ways to help

- **Report a bug** or **suggest an idea** with the [issue templates](https://github.com/mbaudran/git-explained/issues/new/choose).
- **Add a language**: add one column to the `STR` table in `skills/git-explained/scripts/render_report.py`, add the code to the `--language` choices, and add a line to the README.
- **Improve the instructions** Claude follows in `skills/git-explained/SKILL.md`: better commit explanations, better quiz questions, new checks to detect.
- **Improve the report layout** in `render_report.py` (CSS and HTML live in that one file).

## Ground rules

- **Standard library only.** The renderer must run on a fresh Python 3.8+ with no `pip install`.
- **Everything stays local.** No network calls, no analytics, no CDNs.
- **Plain language.** Text the user reads should make sense to someone who is new to git.
- **Fake data in examples.** `assets/example.json` and the screenshots use the fake "taskboard" app. Never commit real reports or personal data.

## Working on the code

```bash
git clone https://github.com/mbaudran/git-explained.git
cd git-explained

# run the tests (no dependencies)
python3 -m unittest discover -s tests -v

# render the example report somewhere temporary and open it
python3 skills/git-explained/scripts/render_report.py skills/git-explained/assets/example.json --out-dir /tmp/gx --open
```

To try your changes inside Claude Code, link the skill folder (and don't also install the plugin, or it loads twice):

```bash
ln -s "$PWD/skills/git-explained" ~/.claude/skills/git-explained
```

If you have the Claude Code CLI, `claude plugin validate .` checks the plugin manifests.

## Pull requests

1. Keep each pull request to one change.
2. Add or update a test in `tests/` when you change the renderer.
3. Update `CHANGELOG.md` under an "Unreleased" heading.
4. Make sure the tests pass.
