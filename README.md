# git-explained

A [Claude Code](https://claude.com/claude-code) skill that **explains every git commit and push in plain language** and, after each push, builds a local **HTML report with a short quiz** so you can check you really understood what changed.

It's for when Claude writes most of the code and you still want to know what went into your repo, what to report as done, and how git works along the way.

---

## What it does

### On every commit
Before committing, Claude shows a **commit plan**:

```
📦 Commit plan
What:   one sentence, plain language
Why:    problem solved / goal
Files:  each file and what changed in it
Effect: what the app can now do, or what is fixed
Not included: files deliberately left out
```

Then it writes a structured commit message (`type(scope): summary` + *Why* / *What* / *Project status*) and confirms what was saved, reminding you that it's **local until you push**.

It also refuses to commit secrets or junk (`.env`, keys, `node_modules`, build output, `.DS_Store`), and never amends, rebases, resets or force-pushes without asking first.

### On every push
1. **Gathers facts**: branch, remote, commits to send, whether GitHub is ahead of you.
2. **Runs the project's checks** (typecheck, lint, tests, build, plus Python/Rust/Go/Swift equivalents). If one fails, it stops and asks.
3. **Shows a push plan**: where it goes, which commits, which checks passed.
4. **Pushes**, then generates an **HTML report** in `~/git-reports/<repo>/` and opens it.

### The report
Each report contains:
- **TL;DR** of what the push delivers
- **What to mark as done**: outcomes you can tick off in your project tracker or mention in standup
- **Not done yet / risks**: follow-ups, env vars to set, breaking changes
- **Check results**
- **Commit-by-commit breakdown**: files, explanations, key code snippet
- **"Your Mac vs GitHub" diagram** of what moved
- **Git operations performed**, each explained, plus a short glossary of the concepts involved
- **A 5–8 question quiz** on what changed, why, where, the impact, and the git operations

### Progress tracking
Quiz scores are saved in `~/git-reports/progress.json`. The index page (`~/git-reports/index.html`) shows your score trend, accuracy per topic, and **weak topics**. Future quizzes include extra questions on those.

---

## Installation

```bash
git clone https://github.com/mbaudran/git-explained.git ~/.claude/skills/git-explained
```

That's it. Claude Code picks up skills in `~/.claude/skills/` automatically. Requires **Python 3** (standard library only, no dependencies).

Optional, but recommended so it applies even to commits inside bigger tasks: add this to `~/.claude/CLAUDE.md`:

```markdown
## Git commits & pushes
- Every `git commit` and every `git push` → follow the `git-explained` skill.
```

---

## Usage

Just talk to Claude Code normally:

| You say | What happens |
|---|---|
| "commit this" | Commit plan → commit → confirmation |
| "push" | Checks → push plan → push → HTML report |
| "commit and push" | Both, one commit at a time, then one push |
| `/git-explained` | Invokes the skill explicitly |

### Taking the quiz
After a push, Claude asks how you want to take it:
- **In the terminal** (recommended): questions appear as multiple choice and the score is saved automatically.
- **In the HTML page**: when you finish, the page shows a line like
  `git-explained quiz myrepo/2026-11-15_1601_main.html: B,C,A,A,C`. Paste it into any Claude Code session to save the score.
- **Later.**

### Running the renderer by hand

```bash
# Render a report from JSON data (see assets/example.json for the full schema)
python3 scripts/render_report.py data.json

# Record a quiz attempt
python3 scripts/render_report.py record ~/git-reports/myrepo/<report>.html --picks B,C,A,A,C --source html

# Show weak topics (used by Claude to tailor the next quiz)
python3 scripts/render_report.py weak
```

All commands accept `--out-dir <path>` to write somewhere other than `~/git-reports` (useful for testing).

---

## Files

```
SKILL.md                  instructions Claude follows (Part A = commit, Part B = push)
scripts/render_report.py  builds reports + index, records quiz attempts, lists weak topics
assets/example.json       full worked example of the report data schema
```

Reports and scores stay **on your Mac** in `~/git-reports/`. Nothing is uploaded.
