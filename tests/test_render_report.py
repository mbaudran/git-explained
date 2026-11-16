"""End-to-end tests for render_report.py. Standard library only: run with `python -m unittest -v`."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "git-explained" / "scripts" / "render_report.py"
EXAMPLE = ROOT / "skills" / "git-explained" / "assets" / "example.json"


def run(*args, check=True):
    p = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8")
    if check and p.returncode != 0:
        raise AssertionError(f"command failed ({p.returncode}): {args}\n{p.stdout}\n{p.stderr}")
    return p


class RendererTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        self.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def tearDown(self):
        self._tmp.cleanup()

    def render(self, data=None):
        src = EXAMPLE
        if data is not None:
            src = self.out / "data.json"
            src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return Path(run(src, "--out-dir", self.out).stdout.strip().splitlines()[-1])

    # ── rendering ──────────────────────────────────────────────

    def test_report_index_and_sidecar(self):
        report = self.render()
        self.assertTrue(report.exists())
        self.assertEqual(report.parent.name, "taskboard")
        self.assertTrue(report.with_suffix(".json").exists())
        html = report.read_text(encoding="utf-8")
        self.assertIn(self.example["headline"], html)
        self.assertIn('lang="en"', html)
        index = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn(report.name, index)

    def test_works_offline(self):
        report = self.render()
        for name in ("InstrumentSans-latin.woff2", "Newsreader-latin.woff2"):
            self.assertTrue((self.out / "_fonts" / name).exists(), name)
        for page in (report, self.out / "index.html"):
            html = page.read_text(encoding="utf-8")
            self.assertNotIn("googleapis", html)
            self.assertNotIn("gstatic", html)
        self.assertIn("url(../_fonts/", report.read_text(encoding="utf-8"))
        self.assertIn("url(_fonts/", (self.out / "index.html").read_text(encoding="utf-8"))

    def test_same_minute_does_not_overwrite(self):
        a, b = self.render(), self.render()
        self.assertNotEqual(a, b)
        self.assertTrue(a.exists() and b.exists())

    def test_unicode_survives(self):
        data = dict(self.example, headline="Réinitialisation — mot de passe ✅ ñ")
        html = self.render(data).read_text(encoding="utf-8")
        self.assertIn("Réinitialisation — mot de passe ✅ ñ", html)

    def test_bad_answer_index_is_rejected(self):
        data = dict(self.example)
        data["quiz"] = [dict(self.example["quiz"][0], answer=9)]
        src = self.out / "bad.json"
        src.write_text(json.dumps(data), encoding="utf-8")
        self.assertNotEqual(run(src, "--out-dir", self.out, check=False).returncode, 0)

    def test_pr_url_is_linked(self):
        html = self.render(dict(self.example, pr_url="https://github.com/o/r/pull/7")).read_text(encoding="utf-8")
        self.assertIn("https://github.com/o/r/pull/7", html)

    # ── quiz + progress ────────────────────────────────────────

    def test_record_scores_and_tracks_weak_topics(self):
        report = self.render()
        answers = [q["answer"] for q in self.example["quiz"]]
        all_right = ",".join("ABCD"[a] for a in answers)
        res = json.loads(run("record", report, "--picks", all_right, "--source", "html", "--out-dir", self.out).stdout)
        self.assertEqual(res["score"], res["total"])
        self.assertEqual(res["wrong"], [])

        all_wrong = ",".join("ABCD"[(a + 1) % 4] for a in answers)
        report2 = self.render()
        res = json.loads(run("record", report2, "--picks", all_wrong, "--out-dir", self.out).stdout)
        self.assertEqual(res["score"], 0)
        self.assertEqual(len(res["wrong"]), len(answers))

        weak = json.loads(run("weak", "--out-dir", self.out).stdout)
        self.assertTrue(set(q["topic"] for q in self.example["quiz"]) <= set(weak["known_topics"]))
        progress = json.loads((self.out / "progress.json").read_text(encoding="utf-8"))
        self.assertTrue(progress)

    def test_record_rejects_wrong_number_of_picks(self):
        report = self.render()
        self.assertNotEqual(run("record", report, "--picks", "A", "--out-dir", self.out, check=False).returncode, 0)

    # ── other commands ─────────────────────────────────────────

    def test_pr_body(self):
        md = run("pr-body", self.render(), "--out-dir", self.out).stdout
        self.assertTrue(md.startswith("## Summary"))
        for item in self.example["done_for_project"]:
            self.assertIn(f"- [x] {item}", md)

    def test_digest(self):
        self.render()
        html, md = (Path(p) for p in run("digest", "--days", "7", "--out-dir", self.out).stdout.split())
        self.assertTrue(html.exists() and md.exists())
        self.assertIn("taskboard", md.read_text(encoding="utf-8"))
        self.assertIn("digests/", (self.out / "index.html").read_text(encoding="utf-8"))

    def test_languages(self):
        for lang in ("fr", "es", "en"):
            cfg = json.loads(run("config", "--language", lang, "--out-dir", self.out).stdout)
            self.assertEqual(cfg["language"], lang)
            self.assertIn(f'lang="{lang}"', self.render().read_text(encoding="utf-8"))

    def test_unknown_language_is_rejected(self):
        self.assertNotEqual(run("config", "--language", "xx", "--out-dir", self.out, check=False).returncode, 0)


class PluginManifestTest(unittest.TestCase):
    def test_manifests_are_consistent(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertRegex(plugin["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual([p["name"] for p in market["plugins"]], [plugin["name"]])
        skill = (ROOT / "skills" / plugin["name"] / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\n"))
        self.assertIn(f"name: {plugin['name']}", skill.split("---")[1])

    def test_changelog_mentions_current_version(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn(f"## [{plugin['version']}]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
