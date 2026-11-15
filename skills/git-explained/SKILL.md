---
name: git-explained
description: MUST USE every time you create a git commit, push to GitHub/any remote, or open a pull request ("commit this", "push", "send to GitHub", "save my changes", "open a PR", or a commit/push as a step inside a bigger task). Explains every commit and push in plain language; each push also produces a local HTML report (what was done, what to mark as done in the project, git operations performed) with a multiple-choice quiz to check the user understood the changes. Also writes PR descriptions, and builds weekly digests when the user asks what they shipped ("what did I do this week", "standup summary", "weekly update").
---

# Git — Explained (commits, pushes, PRs, digests)

The user wants to **understand every commit and push**: what changed, why, what it means for the
project, and what they can report as done. Never commit or push silently.

**Which part to follow:**
- Commit only → **Part A**
- Push only (commits already exist) → **Part B**
- "Commit and push" → Part A for each commit, then Part B once
- Open a pull request → **Part C** (runs Part B first if the branch has unpushed commits)
- "What did I ship this week / standup / weekly update" → **Part D**

**The script.** All commands below call `render_report.py` in this skill's `scripts/` folder. Build its absolute
path from the skill's base directory (shown when the skill loads), e.g.
`GX="<base dir>/scripts/render_report.py"`, then run `python3 "$GX" …`. It needs Python 3.8+ and nothing else.
Reports live in `~/git-reports/` (all commands accept `--out-dir DIR`).

## Language
At the start, read the user's setting: `python3 "$GX" config` → `{"language": "en" | "fr" | "es"}`.
- Write **everything the user reads** in that language: commit/push plans, the chat summary, and all report
  content (`headline`, `tldr`, `done_for_project`, `why`, explanations, `concepts`, quiz questions and answers).
  The report's interface text is translated automatically.
- **Commit messages stay in English** (the usual convention) unless the repo's history is clearly in another language.
- If the user writes to you in French or Spanish and the setting is still `en`, offer once to switch:
  `python3 "$GX" config --language fr`. They can change it any time the same way.

## Shared rules
- Read the real diff. Don't guess what a change does from the file names.
- Plain language first. Explain jargon the first time it comes up, and keep sentences short.
- Never commit secrets or junk (`.env`, keys/tokens, `node_modules`, build output, big binaries,
  `.DS_Store`). Warn the user, leave them out, and suggest adding them to `.gitignore`.
- Never `--amend`, `reset`, `rebase`, force-push or skip hooks (`--no-verify`) without first explaining
  what it does and asking.
- If the user didn't explicitly ask to commit/push, show the plan and ask before doing it.
- Be honest: if something wasn't tested, say so.

---

## Part A — Commit

### A1. Inspect
Run these in parallel: `git status --short`, `git diff --stat`, `git diff --cached --stat`, `git diff`,
`git diff --cached`, `git log --oneline -5` (to match the repo's message style).
If the changes mix unrelated work, propose splitting them into several commits, one logical change each.

### A2. Explain before committing
```
📦 Commit plan
What:   <one sentence, plain language>
Why:    <problem solved / goal>
Files:  <path> — <what changed in it>   (one line per file; group trivial ones)
Effect: <what the user/app can now do, or what is fixed>
Not included: <files deliberately left out, if any>
```

### A3. Message
```
<type>(<scope>): <short summary, imperative, ≤ 72 chars>

Why: <1–3 lines of motivation>

What:
- <change 1>
- <change 2>

Project status: <what can be marked as done / what remains>
```
Types: `feat` (new feature), `fix` (bug fix), `refactor` (same behaviour, cleaner code), `docs`, `style`, `test`,
`chore` (tooling/dependencies), `perf`. This body matters: Part B reads it later to build the report.
Stage specific paths (`git add <paths>`). Use a HEREDOC for the message and add any attribution lines the system asks for.

### A4. Explain after committing
```
✅ Committed <short-sha> on <branch> — <summary>
Saved LOCALLY only — GitHub doesn't have it until you push.
Commits waiting to be pushed: <n>   (git rev-list --count @{u}..HEAD, if an upstream exists)
```
Add one short git-concept line when useful (staging, commit hash, branch…).

---

## Part B — Push

### B1. Gather facts
Run these in parallel: `git branch --show-current`, `git remote -v`, `git status --short`,
`git rev-parse --abbrev-ref @{u}` (is there an upstream?),
`git log @{u}..HEAD --format='%H%n%h%n%s%n%b%n---END---'` (if there's no upstream, use
`origin/<default-branch>..HEAD`), `git diff --stat @{u}..HEAD`, and read `git diff @{u}..HEAD`.
Run `git fetch` and check whether the remote is ahead (`git rev-list --count HEAD..@{u}`). If it is, explain
what that means and ask before pulling or rebasing.
If there is uncommitted work, point out that it won't be pushed, and offer to commit it first (Part A).

Also note for the report: the commit the push starts from (`git rev-parse @{u}` → `base_sha`), whether the
branch is new on GitHub (`new_branch`), and how many remote commits had to be pulled first (`remote_ahead_before`).

### B1b. Run checks before pushing
Find what the project can verify, and run every check that applies (run them in parallel when that's safe):
- `package.json` scripts: `typecheck`/`tsc`, `lint`, `test` (non-watch: `CI=1 npm test`), `build`. Use the
  repo's package manager (look for the `pnpm-lock`/`yarn.lock`/`bun.lockb` file).
- Python: `pytest`, `ruff check`/`flake8`, `mypy` if configured. Rust: `cargo check`/`cargo test`.
  Go: `go build ./...`/`go test ./...`. Swift/Xcode: `swift build` or `xcodebuild … build` if quick.
- Use a 5-minute timeout per check. Skip a check (mark it `skipped`, with a `note`) if it needs secrets or
  services you don't have.

Record each check as `{name, command, status: pass|fail|skipped, duration, note?, output?}`. Keep `output`
to the last ~40 lines, and only include it for failures.

**If any check fails, STOP.** Explain the failure in plain language and offer: fix it first (recommended) /
push anyway / cancel. If the user pushes anyway, set `"pushed_despite_failures": true`.
If the project has no checks at all, say so (the report suggests adding at least a build check).

### B2. Explain before pushing
```
🚀 Push plan
Where:   <remote>/<branch>  (<GitHub URL>)
Commits: <n>
  <sha> <summary> — <plain-language one-liner>
Checks:  ✓ typecheck  ✓ lint  ✓ build  – tests (none)
Result:  after this push, GitHub will have <what>.
```
Before a force push, or a push to `main`/`master` of a shared repo, explain the risk and ask first.

### B3. Push
`git push`, or `git push -u origin <branch>` the first time (explain what `-u` does). Capture the output.
If the push fails, explain the error in plain language and how to fix it. Then get `git log -1 --format=%H`
and the GitHub URLs (turn `git remote get-url origin` into `https://github.com/<owner>/<repo>`).

### B4. Generate the HTML report
First get the user's weak topics, so the quiz can lean on them:
```bash
python3 "$GX" weak
```
Reuse names from `known_topics` when they fit, so progress adds up across pushes. Include at least one
question on each weak topic that this push touches.

Write a JSON file to the scratchpad (or a temp folder) using the schema below, then run:
```bash
python3 "$GX" <data.json> --open
```
The script writes `~/git-reports/<repo>/<YYYY-MM-DD_HHMM>_<branch>.html`, updates `~/git-reports/index.html`
(the list of all reports), prints the path, and `--open` opens it in the browser (macOS, Linux and Windows).

**JSON schema.** Full worked example: `assets/example.json` in this skill's folder.
```json
{
  "repo": "taskboard", "repo_url": "https://github.com/owner/taskboard", "branch": "main", "remote": "origin",
  "pushed_at": "2026-11-13 14:05", "head_sha": "full sha", "language": "en",
  "headline": "Short title of what this push delivers (≤ 60 chars)",
  "base_sha": "commit GitHub was at before the push", "new_branch": false, "remote_ahead_before": 0,
  "checks": [{"name": "Build", "command": "npm run build", "status": "pass", "duration": "41s",
              "note": "optional", "output": "only on failure, last ~40 lines"}],
  "pushed_despite_failures": false,
  "compare_url": "https://github.com/owner/taskboard/compare/<old>...<new>",
  "pr_url": "optional: link to the pull request (Part C)",
  "tldr": "2–3 plain sentences: what this push delivers.",
  "done_for_project": ["Outcome phrased as a task to tick off / report in standup or a tracker card"],
  "not_done_yet": ["Follow-ups, TODOs, things to test manually"],
  "risks": ["Breaking changes, migrations, env vars needed in production, etc."],
  "commits": [{
    "sha": "abc1234", "type": "feat", "title": "summary line",
    "why": "plain-language motivation", "what": ["concrete change"],
    "files": [{"path": "src/x.ts", "status": "modified", "added": 12, "removed": 3, "explanation": "what/why"}],
    "snippet": {"file": "src/x.ts", "code": "≤15 key diff lines with +/- prefixes", "explanation": "what it does"}
  }],
  "git_operations": [{"command": "git push", "explanation": "what it did", "output": "optional short output"}],
  "concepts": [{"term": "upstream", "explanation": "friendly definition tied to this push"}],
  "quiz": [{"question": "...", "options": ["A","B","C","D"], "answer": 1, "explanation": "why",
            "topic": "database"}]
}
```
`snippet`, `output`, `note`, `risks`, `concepts`, `not_done_yet`, `pr_url` and `language` are optional
(`language` defaults to the config). `answer` is a 0-based index.
Every quiz question needs a `topic`: a short, reusable, lowercase tag in English (`database`, `auth`, `ui`, `configuration`,
`code structure`, `git basics`, `branches`, `deployment`…), so progress adds up whatever the language. The report
automatically draws the "Your Mac vs GitHub" diagram from `commits` + `base_sha`.

**Content guidelines**
- `done_for_project` = outcomes, not code ("Users can reset their password by email").
- **Quiz: 5–8 questions** that mix *what* changed, *why*, *where* in the code, *impact* (users, what could
  break, what must be configured) and 1–2 questions on the *git/GitHub operations* performed. Use plausible
  distractors taken from the real codebase, no joke answers, and vary which option is correct.

### B5. After pushing
```
✅ Pushed <n> commit(s) to <remote>/<branch>
<GitHub URL>
📄 Report + quiz: <absolute path to html>
```
Also list the `done_for_project` bullets in the chat. Then ask how they want to take the quiz
(AskUserQuestion): **here in the terminal** (recommended, since the score is saved automatically) / **in the HTML page** / **later**.

### B6. Quiz + progress tracking
- **Terminal:** ask the quiz questions with AskUserQuestion, up to 4 per call (so 2 calls for 5–8 questions).
  Each question's text is the question; the options are the answers prefixed with `A.`/`B.`/…; the header is
  `Q1`, `Q2`… Never reveal the answers. If the user picks "Other", count it as wrong.
- **HTML:** the finished quiz shows a line like `git-explained quiz taskboard/2026-11-13_1942_main.html: B,C,A,A,C`.
  Whenever the user pastes a line like that (in any session), record it.
- **Record** (in both cases):
  ```bash
  python3 "$GX" record <report path> --picks B,C,A,A,C --source terminal|html
  ```
  This saves the attempt to `~/git-reports/progress.json` and re-renders the report (with the score) and the
  index (score trend + accuracy per topic + focus areas). It prints the score, the wrong answers and the weak topics.
- Then reply with the score. For each wrong answer, give a short plain-language explanation tied to the actual code.
  If a topic is weak, say it will come up more in the next quizzes.

---

## Part C — Pull request

1. **Push first.** If the branch has unpushed commits, run Part B (checks, push, report). If everything is
   already pushed, still build a report for the whole PR: same JSON, but cover every commit in
   `origin/<base>..HEAD` (base = the branch the PR merges into, usually the default branch), with
   `base_sha = git merge-base origin/<base> HEAD`.
2. **Explain before opening:**
   ```
   🔀 PR plan
   From → into: <branch> → <base>
   Title:       <short title, ≤ 72 chars>
   Commits:     <n> — <one line on what the PR delivers>
   Reviewers will see: summary, what it delivers, what's left, risks, checks, commits
   ```
   Opening a PR is visible to everyone on the repo. Unless the user asked for it, ask first.
3. **Generate the description** from the report data and open the PR:
   ```bash
   python3 "$GX" pr-body <data.json | report.html> > <scratchpad>/pr.md
   gh pr create --base <base> --title "<title>" --body-file <scratchpad>/pr.md
   ```
   (Add `--draft` if the user wants a draft, or if checks failed.) The description has the summary, a ✅ checklist
   of what it delivers, ⬜ what's left, ⚠️ reviewer notes, a checks table, and the commits.
4. **Link it back:** add `"pr_url": "<url from gh>"` to the JSON and re-run `python3 "$GX" <data.json>`, so the
   report links to the PR.
5. **After:** `🔀 Opened PR #<n>: <url>`, plus one line explaining what a PR is for (review before merging),
   and what happens next (review, CI, merge).

---

## Part D — Digest (standup, weekly update, team)

When the user asks what they shipped ("what did I do this week", "standup", "weekly update for my client/manager"):
```bash
python3 "$GX" digest --days 7 [--repo <name>] --open
```
- `--days` matches the period they asked for (1 for a standup, 7 for a week, 14 for a sprint…).
- It reads every report in the period and writes `~/git-reports/digests/<date>_<N>d.html` (pushes, commits,
  lines changed, quiz average, and per repo: what was delivered, what's still to do, risks, links to each report)
  plus a `.md` version.
- Print the Markdown in the chat, ready to paste into Slack, an email or a standup, and give the HTML path.
- Teams: each person can run it and share the Markdown. It reads only local reports, so nothing is uploaded.
