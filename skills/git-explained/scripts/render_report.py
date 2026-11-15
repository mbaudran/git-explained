#!/usr/bin/env python3
"""git-explained report tool.

  render_report.py <data.json> [--out-dir DIR]
      Render a push report (HTML + sidecar JSON) into DIR/<repo>/ (default DIR = ~/git-reports),
      refresh DIR/index.html, print the HTML path.

  render_report.py record <report.html> --picks B,A,C,D [--source terminal|html] [--out-dir DIR]
      Record quiz answers for a report (letters or 0-based numbers), update progress.json,
      re-render the report + index, print the score and the wrong answers as JSON.

  render_report.py weak [--out-dir DIR]
      Print known topics and weak topics (accuracy < 70%, >= 2 answers) as JSON,
      so the next quiz can target them.

  render_report.py config [--language en|fr|es] [--out-dir DIR]
      Show the config (DIR/config.json) as JSON, or change it.

  render_report.py pr-body <data.json | report.html> [--out-dir DIR]
      Print a Markdown pull-request description built from the report data.

  render_report.py digest [--days 7] [--repo NAME] [--out-dir DIR] [--open]
      Build a digest of all pushes in the last N days (HTML + Markdown) into DIR/digests/,
      print both paths. Good for standups, weekly updates and teams.

  render_report.py open <file>
      Open a report in the default browser (macOS, Linux, Windows).

  Rendering commands also accept --open to open the result right away.

Visual design pass guided by "unslop" by Damir Sokolovsky (@heydamir), CC BY 4.0,
https://github.com/heydamir/unslop
"""
import html
import json
import re
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

e = lambda s: html.escape(str(s if s is not None else ""))
slug = lambda s: re.sub(r"[^A-Za-z0-9._-]+", "-", str(s)).strip("-") or "x"


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def out_root():
    return Path(arg("--out-dir", str(Path.home() / "git-reports"))).expanduser().resolve()


# ───────────────────────────── progress ─────────────────────────────

def load_progress(root):
    try:
        return json.loads((root / "progress.json").read_text())
    except Exception:
        return {"attempts": []}


def save_progress(root, prog):
    (root / "progress.json").write_text(json.dumps(prog, indent=2, ensure_ascii=False))


def topic_stats(prog):
    stats = {}
    for a in prog["attempts"]:
        for q in a.get("questions", []):
            t = (q.get("topic") or "general").strip().lower()
            s = stats.setdefault(t, [0, 0])
            s[0] += 1 if q["correct"] else 0
            s[1] += 1
    return stats


def weak_topics(prog):
    weak = [(t, c / n, n) for t, (c, n) in topic_stats(prog).items() if n >= 2 and c / n < 0.7]
    return sorted(weak, key=lambda x: x[1])


def latest_attempt(prog, report_rel):
    hits = [a for a in prog["attempts"] if a.get("report") == report_rel]
    return hits[-1] if hits else None


def tone(p):
    return "pos" if p >= .85 else "warn" if p >= .6 else "neg"


# ───────────────────────────── config + languages ─────────────────────────────

LANGS = ("en", "fr", "es")
LANG = "en"


def load_config(root):
    try:
        return json.loads((root / "config.json").read_text())
    except Exception:
        return {}


def set_lang(root, data=None):
    global LANG
    want = str((data or {}).get("language") or load_config(root).get("language") or "en").lower()[:2]
    LANG = want if want in LANGS else "en"


# One entry per UI string: (English, French, Spanish). Report *content* is written by Claude in the chosen language.
STR = {
    "nav_done": ("Done", "Fait", "Hecho"),
    "nav_checks": ("Checks", "Vérifs", "Controles"),
    "nav_diagram": ("Mac vs GitHub", "Mac vs GitHub", "Mac vs GitHub"),
    "nav_commits": ("Commits", "Commits", "Commits"),
    "nav_git": ("Git steps", "Étapes Git", "Pasos Git"),
    "nav_quiz": ("Quiz", "Quiz", "Quiz"),
    "reports": ("Reports", "Rapports", "Informes"),
    "pull_request": ("Pull request", "Pull request", "Pull request"),
    "pushed_default": ("Pushed {n} commit(s) to {repo}", "{n} commit(s) envoyé(s) sur {repo}", "{n} commit(s) enviado(s) a {repo}"),
    "checks_failed": ("{n} check(s) failed.", "{n} vérification(s) en échec.", "{n} control(es) fallido(s)."),
    "pushed_anyway": ("You chose to push anyway, the output is below.", "Vous avez choisi de pousser quand même, le détail est ci-dessous.",
                      "Elegiste hacer push de todos modos, el detalle está abajo."),
    "look_first": ("Look at them before relying on this push.", "Regardez-les avant de compter sur ce push.",
                   "Revísalos antes de confiar en este push."),
    "still_to_do": ("Still to do", "Reste à faire", "Pendiente"),
    "watch_out": ("Watch out", "Attention", "Ojo"),
    "c_commits": ("Commits", "Commits", "Commits"),
    "c_files": ("Files changed", "Fichiers modifiés", "Archivos cambiados"),
    "c_lines": ("Lines", "Lignes", "Líneas"),
    "c_checks": ("Checks passed", "Vérifs réussies", "Controles OK"),
    "none": ("none", "aucune", "ninguno"),
    "c_quiz_score": ("Quiz score", "Score du quiz", "Nota del quiz"),
    "c_quiz": ("Quiz", "Quiz", "Quiz"),
    "questions": ("questions", "questions", "preguntas"),
    "s_done": ("What you can mark as done", "Ce que vous pouvez marquer comme fait", "Lo que puedes marcar como hecho"),
    "s_checks": ("Checks before pushing", "Vérifications avant le push", "Controles antes del push"),
    "s_checks_c": ("tests, lint, types, build", "tests, lint, types, build", "tests, lint, tipos, build"),
    "s_diagram": ("Your Mac and GitHub", "Votre Mac et GitHub", "Tu Mac y GitHub"),
    "s_commits": ("Commits explained", "Les commits expliqués", "Commits explicados"),
    "s_git": ("What was done with Git and GitHub", "Ce qui a été fait avec Git et GitHub", "Lo que se hizo con Git y GitHub"),
    "s_terms": ("Terms used in this push", "Termes utilisés dans ce push", "Términos usados en este push"),
    "s_quiz": ("Check your understanding", "Vérifiez votre compréhension", "Comprueba lo que entendiste"),
    "push_report": ("push report", "rapport de push", "informe de push"),
    "your_mac": ("Your Mac", "Votre Mac", "Tu Mac"),
    "shared": ("shared", "commun", "común"),
    "diagram_aria": ("Commits on your Mac and on GitHub, before and after the push", "Commits sur votre Mac et sur GitHub, avant et après le push",
                     "Commits en tu Mac y en GitHub, antes y después del push"),
    "legend_both": ("On both before the push", "Présent des deux côtés avant le push", "En ambos antes del push"),
    "legend_sent": ("Sent by this push", "Envoyé par ce push", "Enviado por este push"),
    "diagram_para": ("Before the push, the blue commits existed only on your Mac. <code>git push</code> copied them to GitHub, so both now hold the same history.",
                     "Avant le push, les commits bleus n'existaient que sur votre Mac. <code>git push</code> les a copiés sur GitHub : les deux ont maintenant le même historique.",
                     "Antes del push, los commits azules solo existían en tu Mac. <code>git push</code> los copió a GitHub, así que ahora ambos tienen el mismo historial."),
    "new_branch_para": ("This branch didn't exist on GitHub yet, so the push created it. <code>-u</code> links your local branch to it, so later pushes know where to go.",
                        "Cette branche n'existait pas encore sur GitHub, le push l'a créée. <code>-u</code> y relie votre branche locale pour que les prochains push sachent où aller.",
                        "Esta rama aún no existía en GitHub, así que el push la creó. <code>-u</code> enlaza tu rama local con ella para que los próximos push sepan adónde ir."),
    "ahead_para": ("GitHub had {n} commit(s) you didn't have yet. They were pulled in first so both histories matched before pushing.",
                   "GitHub avait {n} commit(s) que vous n'aviez pas encore. Ils ont été récupérés d'abord pour que les deux historiques correspondent avant le push.",
                   "GitHub tenía {n} commit(s) que aún no tenías. Se trajeron primero para que ambos historiales coincidieran antes del push."),
    "more": ("+{n} more", "+{n} autres", "+{n} más"),
    "no_checks": ("No automated checks (tests, lint, type check, build) were found in this project. Even a build check catches broken code before it reaches GitHub.",
                  "Aucune vérification automatique (tests, lint, types, build) trouvée dans ce projet. Même un simple build détecte du code cassé avant qu'il n'arrive sur GitHub.",
                  "No se encontraron controles automáticos (tests, lint, tipos, build) en este proyecto. Incluso un build detecta código roto antes de que llegue a GitHub."),
    "show_output": ("Show output", "Voir la sortie", "Ver la salida"),
    "key_code": ("Key code", "Code clé", "Código clave"),
    "why": ("Why", "Pourquoi", "Por qué"),
    "what_changed": ("What changed", "Ce qui a changé", "Qué cambió"),
    "files": ("Files", "Fichiers", "Archivos"),
    "st_added": ("new", "nouveau", "nuevo"),
    "st_modified": ("edit", "modif", "edición"),
    "st_deleted": ("removed", "supprimé", "eliminado"),
    "st_renamed": ("renamed", "renommé", "renombrado"),
    "no_quiz": ("No quiz for this push", "Pas de quiz pour ce push", "No hay quiz para este push"),
    "recorded": ("Recorded score {score} on {date}, counted in your progress", "Score enregistré {score} le {date}, compté dans votre progression",
                 "Nota registrada {score} el {date}, contada en tu progreso"),
    "copy": ("Copy", "Copier", "Copiar"),
    "copied": ("Copied", "Copié", "Copiado"),
    "paste_hint": ("Paste this line to Claude to save the score in your progress", "Collez cette ligne à Claude pour enregistrer le score",
                   "Pega esta línea a Claude para guardar la nota en tu progreso"),
    "paste_aria": ("Answers to paste to Claude", "Réponses à coller à Claude", "Respuestas para pegar a Claude"),
    "try_again": ("Try again", "Réessayer", "Intentar de nuevo"),
    "js_correct": ("Correct. ", "Correct. ", "Correcto. "),
    "js_wrong": ("Not quite. The answer is {L}. ", "Pas tout à fait. La réponse est {L}. ", "No exactamente. La respuesta es la {L}. "),
    "js_of": ("{n} of {m}", "{n} sur {m}", "{n} de {m}"),
    "js_t_full": ("You understand this push", "Vous comprenez ce push", "Entiendes este push"),
    "js_t_good": ("A solid read of this push", "Une bonne lecture de ce push", "Buena lectura de este push"),
    "js_t_low": ("Worth a second read", "Ça vaut une deuxième lecture", "Vale la pena releerlo"),
    "js_x_full": ("Every answer right. You could explain these changes to anyone.", "Tout juste. Vous pourriez expliquer ces changements à n'importe qui.",
                  "Todo correcto. Podrías explicar estos cambios a cualquiera."),
    "js_x_other": ("Go back to the commits behind the questions you missed, then try again.", "Relisez les commits liés aux questions ratées, puis réessayez.",
                   "Vuelve a los commits de las preguntas que fallaste y vuelve a intentarlo."),
    "theme_aria": ("Change theme", "Changer de thème", "Cambiar tema"),
    "th_auto": ("Auto", "Auto", "Auto"),
    "th_light": ("Light", "Clair", "Claro"),
    "th_dark": ("Dark", "Sombre", "Oscuro"),
    "no_scores": ("Your scores show up here once you record a quiz", "Vos scores apparaîtront ici après votre premier quiz enregistré",
                  "Tus notas aparecerán aquí cuando registres un quiz"),
    "goal": ("70% goal", "objectif 70 %", "meta 70 %"),
    "scores_aria": ("Quiz scores over time", "Scores des quiz dans le temps", "Notas de los quiz en el tiempo"),
    "idx_title": ("Push reports and progress", "Rapports de push et progression", "Informes de push y progreso"),
    "idx_lede": ("Every push made with Claude, what it delivered, and how well you understood it",
                 "Chaque push fait avec Claude, ce qu'il a apporté, et à quel point vous l'avez compris",
                 "Cada push hecho con Claude, lo que aportó y cuánto lo entendiste"),
    "i_pushes": ("Pushes", "Push", "Pushes"),
    "i_quizzes": ("Quizzes recorded", "Quiz enregistrés", "Quiz registrados"),
    "i_avg": ("Average score", "Score moyen", "Nota media"),
    "none_yet": ("none yet", "pas encore", "aún no"),
    "i_repos": ("Repos", "Dépôts", "Repos"),
    "progress": ("Progress", "Progression", "Progreso"),
    "scores_sub": ("Quiz scores, latest in blue", "Scores des quiz, le dernier en bleu", "Notas de los quiz, la última en azul"),
    "by_topic": ("By topic", "Par thème", "Por tema"),
    "no_topics": ("Topics appear after your first recorded quiz", "Les thèmes apparaissent après votre premier quiz enregistré",
                  "Los temas aparecen tras tu primer quiz registrado"),
    "focus_hint": ("Topics marked focus come up more in your next quizzes", "Les thèmes marqués « focus » reviendront plus souvent",
                   "Los temas marcados como foco saldrán más en los próximos quiz"),
    "focus": ("focus", "focus", "foco"),
    "no_reports": ("No reports yet", "Aucun rapport pour l'instant", "Aún no hay informes"),
    "no_score": ("no score yet", "pas encore de score", "sin nota aún"),
    "digests": ("Digests", "Résumés", "Resúmenes"),
    "dg_title": ("{days}-day digest", "Résumé sur {days} jours", "Resumen de {days} días"),
    "dg_lede": ("What was delivered from {start} to {end}, across {n} repo(s)", "Ce qui a été livré du {start} au {end}, sur {n} dépôt(s)",
                "Lo que se entregó del {start} al {end}, en {n} repo(s)"),
    "dg_quiz": ("Quiz average", "Moyenne quiz", "Media quiz"),
    "dg_done": ("Delivered", "Livré", "Entregado"),
    "dg_pushlist": ("Pushes in this period", "Push de la période", "Pushes del periodo"),
    "dg_empty": ("No pushes in this period", "Aucun push sur cette période", "No hubo pushes en este periodo"),
    "dg_md": ("Markdown version, ready to paste", "Version Markdown, prête à coller", "Versión Markdown, lista para pegar"),
    "pr_summary": ("Summary", "Résumé", "Resumen"),
    "pr_done": ("What this delivers", "Ce que ça apporte", "Qué aporta"),
    "pr_risks": ("Reviewer notes / risks", "Notes pour la revue / risques", "Notas para revisión / riesgos"),
    "pr_checks": ("Checks", "Vérifications", "Controles"),
    "pr_footer": ("Explained with [git-explained](https://github.com/mbaudran/git-explained)",
                  "Expliqué avec [git-explained](https://github.com/mbaudran/git-explained)",
                  "Explicado con [git-explained](https://github.com/mbaudran/git-explained)"),
}


def tr(key, **kw):
    s = STR[key][LANGS.index(LANG)]
    return s.format(**kw) if kw else s


# ───────────────────────────── icons (lucide, 1.5 stroke) ─────────────────────────────

_P = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "circle": '<circle cx="12" cy="12" r="9" stroke-dasharray="2.5 3"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "minus": '<path d="M5 12h14"/>',
    "branch": '<line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
    "out": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "chev-r": '<path d="m9 18 6-6-6-6"/>',
    "chev-l": '<path d="m15 18-6-6 6-6"/>',
    "copy": '<rect width="13" height="13" x="9" y="9" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "rotate": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
}


def icon(name, size=16, cls="i"):
    return (f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_P[name]}</svg>')


# ───────────────────────────── styles ─────────────────────────────

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500'
         '&display=swap" rel="stylesheet">')

LIGHT = ("--bg:#f7f4ee;--surface:#fdfbf7;--raised:#efe9df;--ink:#1f1b16;--ink-2:#5e554a;--muted:#7b7266;"
         "--line:rgba(31,27,22,.08);--line-2:rgba(31,27,22,.16);--accent:#2f56c4;--pos:#15803d;--neg:#c62828;--warn:#a85d06;"
         "--shadow:0 1px 2px rgba(0,0,0,.05)")
DARK = ("--bg:#161513;--surface:#1c1a18;--raised:#262421;--ink:#efe9de;--ink-2:#aaa398;--muted:#8a847a;"
        "--line:rgba(239,233,222,.08);--line-2:rgba(239,233,222,.16);--accent:#8eaaff;--pos:#4cc38a;--neg:#e5484d;--warn:#e0a43a;"
        "--shadow:none")

CSS = """
:root{LIGHT;--ease:cubic-bezier(.22,1,.36,1);--sans:"Instrument Sans",ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
--serif:"Newsreader",ui-serif,Georgia,serif;--mono:ui-monospace,"SF Mono",Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){DARK}}
:root[data-theme=dark]{DARK}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:72px}
body{margin:0;background:var(--bg);color:var(--ink);font:400 15px/1.6 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline;text-underline-offset:3px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.i{flex:none;display:inline-block;vertical-align:-3px}
.mono,code,pre{font-family:var(--mono);font-size:12.5px}
.num{font-variant-numeric:tabular-nums}
.pos{color:var(--pos)}.neg{color:var(--neg)}.warn{color:var(--warn)}.muted{color:var(--muted)}.ink2{color:var(--ink-2)}

/* top bar */
.bar{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);
backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.bar .in{max-width:880px;margin:0 auto;padding:0 16px;height:56px;display:flex;gap:4px;align-items:center;overflow-x:auto;scrollbar-width:none}
.bar a{display:inline-flex;align-items:center;gap:4px;color:var(--ink-2);font-size:13px;font-weight:500;height:32px;padding:0 8px;border-radius:8px;white-space:nowrap;
transition:background-color .15s var(--ease),color .15s var(--ease)}
.bar a:hover{background:var(--raised);color:var(--ink);text-decoration:none}
.bar .home{color:var(--ink);margin-right:auto;padding-left:4px}
.theme{display:inline-flex;align-items:center;gap:6px;font:500 13px var(--sans);color:var(--ink-2);background:var(--surface);
border:1px solid var(--line-2);border-radius:8px;height:32px;padding:0 12px;cursor:pointer;margin-left:8px;white-space:nowrap;
transition:border-color .15s var(--ease),color .15s var(--ease)}
.theme:hover{color:var(--ink);border-color:var(--muted)}.theme:active{transform:scale(.97)}

main{max-width:880px;margin:0 auto;padding:48px 16px 128px}
.meta{display:flex;gap:8px 16px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:13px}
.meta span,.meta a{display:inline-flex;align-items:center;gap:6px}
h1{font:400 40px/1.1 var(--serif);letter-spacing:-.02em;margin:16px 0 12px;text-wrap:balance}
.lede{font-size:18px;line-height:1.55;color:var(--ink-2);max-width:36rem;margin:0}
@media(max-width:600px){h1{font-size:32px}.lede{font-size:16px}main{padding-top:32px}}

/* stat strip */
.strip{display:flex;flex-wrap:wrap;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:16px;overflow:hidden;margin-top:32px;box-shadow:var(--shadow)}
.strip>div{flex:1 1 132px;background:var(--surface);padding:16px 20px}
.strip .l{color:var(--ink-2);font-size:13px}
.strip .v{font-size:28px;line-height:1.2;font-weight:500;font-variant-numeric:tabular-nums;margin-top:4px}
.strip .v small{font-size:16px;color:var(--muted);font-weight:400}

section{margin-top:56px}
.sh{display:flex;align-items:baseline;gap:12px;margin-bottom:16px}
.sh h2{font-size:18px;line-height:1.3;font-weight:500;margin:0}
.sh .c{color:var(--muted);font:12.5px var(--mono)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:24px;box-shadow:var(--shadow)}
.card+.card,.card+.note-box,.note-box+.card{margin-top:12px}
@media(max-width:600px){.card{padding:20px}}
.sub{color:var(--ink-2);font-size:13px;font-weight:500;margin:0 0 12px}

/* lists */
.list{list-style:none;margin:0;padding:0}
.list li{display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line)}
.list li:first-child{border-top:0;padding-top:0}.list li:last-child{padding-bottom:0}
.list .i{margin-top:3px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.two>.card{margin:0}
@media(max-width:640px){.two{grid-template-columns:1fr}}

/* checks */
.chk{display:grid;grid-template-columns:20px minmax(0,1fr) auto;gap:4px 12px;align-items:baseline;padding:12px 0;border-top:1px solid var(--line)}
.chk:first-child{border-top:0;padding-top:0}.chk:last-child{padding-bottom:0}.chk .i{align-self:center}
.chk .n{font-weight:500}.chk .cmd{color:var(--muted);margin-left:8px}
.chk .d{color:var(--muted);font:12.5px var(--mono)}
.chk .x{grid-column:2/4;color:var(--ink-2);font-size:14px}
.chk details{grid-column:2/4}.chk summary{cursor:pointer;color:var(--muted);font-size:13px}
.chk pre{margin-top:8px;max-height:280px}
.banner{display:flex;gap:12px;align-items:flex-start;border:1px solid var(--line-2);border-radius:12px;padding:12px 16px;margin-bottom:12px;background:var(--surface)}
.banner .i{margin-top:3px}

/* diagram — the main moment */
.diagram svg{width:100%;height:auto;display:block}
.legend{display:flex;gap:20px;flex-wrap:wrap;color:var(--muted);font-size:13px;margin-top:8px}
.legend span{display:inline-flex;align-items:center;gap:8px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.para{color:var(--ink-2);margin:12px 0 0;font-size:14px;max-width:62ch}

/* git log rail — signature */
.rail{position:relative;padding-left:32px}
.rail:before{content:"";position:absolute;left:7px;top:24px;bottom:24px;width:2px;background:var(--line-2);border-radius:2px}
.node{position:absolute;left:-32px;width:16px;height:16px;border-radius:50%;background:var(--surface);border:2px solid var(--accent)}
.rail .item{position:relative}.rail .item+.item{margin-top:12px}
.rail .item>.node{top:22px}
details.cm{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}
details.cm summary{list-style:none;cursor:pointer;padding:16px 20px;display:flex;gap:12px;align-items:center;border-radius:16px;
transition:background-color .15s var(--ease)}
details.cm summary::-webkit-details-marker{display:none}
details.cm summary:hover{background:color-mix(in srgb,var(--raised) 50%,transparent)}
details.cm[open] summary{border-radius:16px 16px 0 0}
details.cm .t{flex:1;min-width:0;font-weight:500}
details.cm .r{display:flex;gap:12px;align-items:center;color:var(--muted);white-space:nowrap}
details.cm .chev{color:var(--muted);transition:transform .2s var(--ease)}details.cm[open] .chev{transform:rotate(90deg)}
details.cm .body{padding:4px 20px 24px;border-top:1px solid var(--line)}
@media(max-width:560px){details.cm summary{flex-wrap:wrap}details.cm .r{width:100%}}
.tag{display:inline-block;font:500 12px/20px var(--mono);padding:0 6px;border-radius:6px;background:var(--raised);color:var(--ink-2);white-space:nowrap}
.k{font-size:13px;color:var(--ink-2);font-weight:500;margin:20px 0 8px}
.body ul{margin:0;padding-left:20px}.body li{margin:4px 0}
.files{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.file{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 12px;padding:12px 16px;border-top:1px solid var(--line)}
.file:first-child{border-top:0}.file .p{word-break:break-all;color:var(--ink)}.file .x{grid-column:1/3;color:var(--ink-2);font-size:14px}
.file .s{color:var(--muted);margin-right:8px}
pre{background:var(--raised);border-radius:12px;padding:12px 16px;overflow-x:auto;margin:0;line-height:1.6;color:var(--ink)}
pre .a{display:block;color:var(--pos);background:color-mix(in srgb,var(--pos) 8%,transparent);margin:0 -16px;padding:0 16px}
pre .d{display:block;color:var(--neg);background:color-mix(in srgb,var(--neg) 8%,transparent);margin:0 -16px;padding:0 16px}
.cap{color:var(--ink-2);font-size:14px;margin:8px 0 0}
.steps .item>.node{top:3px;width:12px;height:12px;left:-30px}
.steps.rail:before{top:8px;bottom:8px}
.steps .item+.item{margin-top:20px}
.steps code{color:var(--ink);background:var(--raised);padding:2px 8px;border-radius:6px}
.steps p{margin:8px 0 0;color:var(--ink-2);font-size:14px}.steps pre{margin-top:8px}
dl.terms{margin:0;display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:12px 24px}
dl.terms dt{font-weight:500}dl.terms dd{margin:0;color:var(--ink-2);font-size:14px}
@media(max-width:560px){dl.terms{grid-template-columns:1fr;gap:4px}dl.terms dd{margin-bottom:12px}}

/* quiz */
.qhead{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.track{flex:1;height:4px;background:var(--raised);border-radius:4px;overflow:hidden}
.track div{height:100%;width:0;background:var(--accent);transition:width .3s var(--ease)}
.q+.q{margin-top:12px}
.qq{display:flex;gap:12px;align-items:flex-start;margin:0 0 16px;font-size:16px;font-weight:500;line-height:1.45}
.qq .n{color:var(--muted);font:500 13px/24px var(--mono);min-width:20px}.qq .tag{margin-left:auto;margin-top:2px}
.opt{display:flex;gap:12px;align-items:center;width:100%;text-align:left;font:400 15px/1.45 var(--sans);color:var(--ink);
background:var(--surface);border:1px solid var(--line-2);border-radius:10px;padding:10px 12px;margin-top:8px;cursor:pointer;
transition:border-color .15s var(--ease),background-color .15s var(--ease)}
.opt .key{flex:none;width:24px;height:24px;border-radius:6px;border:1px solid var(--line-2);border-bottom-width:2px;display:grid;place-items:center;
font:500 12px var(--mono);color:var(--ink-2);background:var(--bg)}
.opt:hover:not(:disabled){border-color:var(--muted);background:var(--raised)}.opt:active:not(:disabled){transform:scale(.99)}
.opt:disabled{cursor:default}.q.done .opt:not(.ok):not(.no){opacity:.5}
.opt.ok{border-color:color-mix(in srgb,var(--pos) 55%,transparent);background:color-mix(in srgb,var(--pos) 8%,var(--surface))}
.opt.ok .key{color:var(--pos);border-color:color-mix(in srgb,var(--pos) 55%,transparent)}
.opt.no{border-color:color-mix(in srgb,var(--neg) 55%,transparent);background:color-mix(in srgb,var(--neg) 7%,var(--surface))}
.opt.no .key{color:var(--neg);border-color:color-mix(in srgb,var(--neg) 55%,transparent)}
.why{display:none;margin-top:16px;padding:12px 16px;border-radius:10px;background:var(--raised);color:var(--ink-2);font-size:14px}
.q.done .why{display:block}.why b{font-weight:500}
.result{display:none;text-align:center;padding:32px 24px;margin-top:12px}.result.show{display:block}
.ring{width:120px;height:120px;margin:0 auto 12px;display:block}
.result h3{font:400 26px/1.2 var(--serif);margin:0 0 8px}.result p{color:var(--ink-2);margin:0 auto 20px;max-width:46ch}
.copy{display:flex;gap:8px;max-width:520px;margin:0 auto}
.copy input{flex:1;min-width:0;font:12.5px var(--mono);color:var(--ink);background:var(--raised);border:1px solid var(--line);border-radius:10px;padding:0 12px;height:40px}
.btn{display:inline-flex;align-items:center;gap:8px;font:500 14px var(--sans);height:40px;padding:0 16px;border-radius:10px;cursor:pointer;
border:0;background:var(--ink);color:var(--bg);transition:opacity .15s var(--ease)}.btn:hover{opacity:.88}.btn:active{transform:scale(.97)}
.btn.ghost{background:transparent;color:var(--ink-2);border:1px solid var(--line-2)}.btn.ghost:hover{color:var(--ink);opacity:1}
.hint{color:var(--muted);font-size:13px;margin:12px 0 0}
.recorded{display:flex;gap:12px;align-items:center;margin-bottom:12px;color:var(--ink-2);font-size:14px}

/* index */
.chart svg{width:100%;height:auto;display:block}
.prog{display:grid;grid-template-columns:1.6fr 1fr;gap:12px;align-items:start}.prog>.card{margin:0}
@media(max-width:720px){.prog{grid-template-columns:1fr}}
.topic{display:grid;grid-template-columns:minmax(0,1fr) max-content;gap:4px 12px;padding:8px 0;align-items:center}
.topic .nm{font-size:14px;display:flex;gap:8px;align-items:center}.topic .pc{white-space:nowrap;text-align:right;color:var(--muted);font:12.5px var(--mono)}
.topic .tr{grid-column:1/3;height:4px;background:var(--raised);border-radius:4px;overflow:hidden}
.topic .tr div{height:100%;border-radius:4px;background:var(--ink-2)}.topic.weak .tr div{background:var(--warn)}
.group{margin-top:24px}.group .gl{color:var(--ink-2);font-size:13px;font-weight:500;margin:0 0 8px}
.rows{padding:0;overflow:hidden}
.row{display:flex;gap:16px;align-items:center;padding:16px 20px;border-top:1px solid var(--line);color:inherit;transition:background-color .15s var(--ease)}
.row:first-child{border-top:0}.row:hover{background:color-mix(in srgb,var(--raised) 50%,transparent);text-decoration:none}
.row .w{flex:1;min-width:0}.row .w b{font-weight:500;display:block}
.row .w div{color:var(--muted);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .sc{font:500 13px var(--mono);white-space:nowrap}
.empty{color:var(--muted);text-align:center}
""".replace("LIGHT", LIGHT).replace("DARK", DARK)

# Theme applied in <head> to avoid a flash; the button cycles Auto → Light → Dark and is remembered.
THEME_HEAD = """<script>(function(){var t;try{t=localStorage.getItem('gx-theme')}catch(_){}
if(t==='light'||t==='dark')document.documentElement.dataset.theme=t})();</script>"""
def theme_btn():
    return f'<button class="theme" id="theme" type="button" aria-label="{e(tr("theme_aria"))}">{e(tr("th_auto"))}</button>'


_SVG = lambda p: ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" '
                  'stroke-linecap="round" stroke-linejoin="round">' + p + '</svg>')


def theme_js():
    js = lambda k: json.dumps(" " + tr(k))[1:-1].replace("'", "\\'")
    return ("<script>(function(){var b=document.getElementById('theme'),R=document.documentElement,O=['auto','light','dark'],"
            "I={auto:'" + _SVG('<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>') + js("th_auto") + "',"
            "light:'" + _SVG('<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/>'
                             '<path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/>'
                             '<path d="m19.07 4.93-1.41 1.41"/>') + js("th_light") + "',"
            "dark:'" + _SVG('<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>') + js("th_dark") + "'},c=R.dataset.theme||'auto';b.innerHTML=I[c];"
            "b.onclick=function(){c=O[(O.indexOf(c)+1)%3];if(c==='auto')delete R.dataset.theme;else R.dataset.theme=c;"
            "try{c==='auto'?localStorage.removeItem('gx-theme'):localStorage.setItem('gx-theme',c)}catch(_){}b.innerHTML=I[c]}})();</script>")


def quiz_strings():
    keys = ["js_correct", "js_wrong", "js_of", "js_t_full", "js_t_good", "js_t_low", "js_x_full", "js_x_other", "copied"]
    return "const T=" + json.dumps({k: STR[k][LANGS.index(LANG)] for k in keys}, ensure_ascii=False).replace("</", "<\\/") + ";"


QUIZ_JS = """
const B=document.body,KEY='gx-quiz:'+B.dataset.key,qs=[...document.querySelectorAll('.q')];
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(_){}
const L=i=>String.fromCharCode(65+i),$=id=>document.getElementById(id);
function show(q,pick){const a=+q.dataset.answer;q.classList.add('done');
 const w=q.querySelector('.why b');w.textContent=pick===a?T.js_correct:T.js_wrong.replace('{L}',L(a));w.className=pick===a?'pos':'neg';
 q.querySelectorAll('.opt').forEach((b,i)=>{b.disabled=true;if(i===a)b.classList.add('ok');else if(i===pick)b.classList.add('no')})}
function upd(){if(!qs.length)return;const n=Object.keys(st).length,ok=qs.filter((q,i)=>st[i]===+q.dataset.answer).length;
 $('qtrack').style.width=(n/qs.length*100)+'%';$('qcount').textContent=T.js_of.replace('{n}',n).replace('{m}',qs.length);
 const r=$('result');if(n<qs.length){r.classList.remove('show');return}
 r.classList.add('show');const p=ok/qs.length,c=2*Math.PI*50;
 $('arc').setAttribute('stroke-dasharray',(p*c)+' '+c);
 $('arc').setAttribute('stroke',p>=.85?'var(--pos)':p>=.6?'var(--warn)':'var(--neg)');
 $('rnum').textContent=ok+'/'+qs.length;
 $('rtitle').textContent=p===1?T.js_t_full:p>=.7?T.js_t_good:T.js_t_low;
 $('rtext').textContent=p===1?T.js_x_full:T.js_x_other;
 $('cline').value='git-explained quiz '+B.dataset.report+': '+qs.map((q,i)=>L(st[i])).join(',')}
qs.forEach((q,i)=>{if(st[i]!==undefined)show(q,st[i]);
 q.querySelectorAll('.opt').forEach((b,j)=>b.onclick=()=>{st[i]=j;try{localStorage.setItem(KEY,JSON.stringify(st))}catch(_){};show(q,j);upd()})});
if($('retry'))$('retry').onclick=()=>{st={};try{localStorage.removeItem(KEY)}catch(_){};location.reload()};
if($('cbtn'))$('cbtn').onclick=async()=>{const i=$('cline');i.select();
 try{await navigator.clipboard.writeText(i.value)}catch(_){document.execCommand('copy')}$('cbtn').lastChild.textContent=' '+T.copied};
upd();
"""


def page(title, body, scripts=""):
    return (f'<!doctype html><html lang="{LANG}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title>{FONTS}<style>{CSS}</style>{THEME_HEAD}</head>{body}{scripts}{theme_js()}</body></html>')


# ───────────────────────────── components ─────────────────────────────

def bullet_list(items, ic, cls):
    return '<ul class="list">' + "".join(f'<li><span class="{cls}">{icon(ic)}</span><span>{e(i)}</span></li>' for i in items) + "</ul>"


def diagram(d):
    """GitHub lane over the Mac lane: shared base node, the pushed commits on both, push arrows between."""
    commits = d.get("commits", [])
    shown, extra = commits[:6], max(len(commits) - 6, 0)
    W, x0, yG, yM = 760, 176, 64, 196
    gap = min(112, (W - x0 - 72) / max(len(shown), 1))
    xs = [x0 + gap * (i + 1) for i in range(len(shown))]
    xe = (xs[-1] if xs else x0) + 28
    mono = 'font-family="ui-monospace,SF Mono,Menlo,monospace"'
    o = [f'<svg viewBox="0 0 {W} 248" role="img" aria-label="{e(tr("diagram_aria"))}">']
    for y, name, sub in [(yG, "GitHub", f'{d.get("remote", "origin")}/{d.get("branch", "")}'), (yM, tr("your_mac"), d.get("branch", ""))]:
        o.append(f'<text x="0" y="{y-2}" font-size="15" font-weight="500" fill="var(--ink)" font-family="Instrument Sans,ui-sans-serif,sans-serif">{e(name)}</text>'
                 f'<text x="0" y="{y+16}" font-size="11.5" fill="var(--muted)" {mono}>{e(sub)}</text>')
        o.append(f'<line x1="{x0-28}" y1="{y}" x2="{xe}" y2="{y}" stroke="var(--line-2)" stroke-width="2" stroke-linecap="round"/>')
    for x in xs:
        o.append(f'<path d="M{x} {yM-14} V{yG+16}" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="2 4" stroke-linecap="round" opacity=".7"/>'
                 f'<path d="M{x-4.5} {yG+23} L{x} {yG+17} L{x+4.5} {yG+23}" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>')
    if xs:
        mx, my = (xs[0] + xs[-1]) / 2, (yG + yM) / 2
        o.append(f'<rect x="{mx-38}" y="{my-12}" width="76" height="24" rx="6" fill="var(--surface)" stroke="var(--line-2)"/>'
                 f'<rect x="{mx-38}" y="{my+10}" width="76" height="2" rx="1" fill="var(--line-2)"/>'
                 f'<text x="{mx}" y="{my+4}" text-anchor="middle" font-size="11.5" fill="var(--ink)" {mono}>git push</text>')
    for y in (yG, yM):
        o.append(f'<circle cx="{x0}" cy="{y}" r="7" fill="var(--surface)" stroke="var(--muted)" stroke-width="2"/>')
    o.append(f'<text x="{x0}" y="{yM+32}" text-anchor="middle" font-size="11" fill="var(--muted)" {mono}>{e(str(d.get("base_sha") or "base")[:7])}</text>'
             f'<text x="{x0}" y="{yG-20}" text-anchor="middle" font-size="11" fill="var(--muted)" {mono}>{e(tr("shared"))}</text>')
    for x, c in zip(xs, shown):
        for y in (yG, yM):
            o.append(f'<circle cx="{x}" cy="{y}" r="8" fill="var(--accent)" stroke="var(--surface)" stroke-width="3"/>')
        o.append(f'<text x="{x}" y="{yM+32}" text-anchor="middle" font-size="11" fill="var(--ink-2)" {mono}>{e(str(c.get("sha", ""))[:7])}</text>'
                 f'<text x="{x}" y="{yG-20}" text-anchor="middle" font-size="11" fill="var(--accent)" {mono}>{e(c.get("type", "new"))}</text>')
    if extra:
        o.append(f'<text x="{xe+12}" y="{(yG+yM)/2+4}" font-size="12" fill="var(--muted)" {mono}>{e(tr("more", n=extra))}</text>')
    o.append("</svg>")
    ahead = int(d.get("remote_ahead_before") or 0)
    extra_p = ""
    if d.get("new_branch"):
        extra_p += f'<p class="para">{tr("new_branch_para")}</p>'
    if ahead:
        extra_p += f'<p class="para">{e(tr("ahead_para", n=ahead))}</p>'
    return (f'<div class="card diagram">{"".join(o)}<div class="legend">'
            f'<span><i class="dot" style="border:2px solid var(--muted)"></i>{e(tr("legend_both"))}</span>'
            f'<span><i class="dot" style="background:var(--accent)"></i>{e(tr("legend_sent"))}</span></div>'
            f'<p class="para">{tr("diagram_para")}</p>{extra_p}</div>')


def checks_html(checks):
    if not checks:
        return ('<div class="card"><ul class="list"><li><span class="muted">' + icon("circle") + '</span><span>'
                + e(tr("no_checks")) + '</span></li></ul></div>')
    ic = {"pass": ("check", "pos"), "fail": ("x", "neg"), "skipped": ("minus", "muted")}
    rows = []
    for c in checks:
        n, cls = ic.get(c.get("status"), ("minus", "muted"))
        out = f'<details><summary>{e(tr("show_output"))}</summary><pre>{e(c["output"])}</pre></details>' if c.get("output") else ""
        note = f'<div class="x">{e(c["note"])}</div>' if c.get("note") else ""
        rows.append(f'<div class="chk"><span class="{cls}" title="{e(c.get("status"))}">{icon(n)}</span>'
                    f'<div><span class="n">{e(c.get("name"))}</span><span class="cmd mono">{e(c.get("command", ""))}</span></div>'
                    f'<span class="d">{e(c.get("duration", "") or c.get("status", ""))}</span>{note}{out}</div>')
    return '<div class="card">' + "".join(rows) + "</div>"


def snippet_html(sn):
    if not sn or not sn.get("code"):
        return ""
    lines = []
    for ln in str(sn["code"]).splitlines():
        cls = "a" if ln.startswith("+") else "d" if ln.startswith("-") else ""
        lines.append(f'<span class="{cls}">{e(ln)}</span>' if cls else e(ln) + "\n")
    return (f'<div class="k">{e(tr("key_code"))} <span class="mono muted" style="margin-left:8px">{e(sn.get("file", ""))}</span></div>'
            f'<pre>{"".join(lines)}</pre><p class="cap">{e(sn.get("explanation", ""))}</p>')


def commit_html(c, open_):
    status = {k: tr("st_" + k) for k in ("added", "modified", "deleted", "renamed")}
    fl = c.get("files", [])
    files = "".join(
        f'<div class="file"><span class="p mono"><span class="s">{e(status.get(f.get("status"), status["modified"]))}</span>{e(f.get("path"))}</span>'
        f'<span class="mono num"><span class="pos">+{e(f.get("added", 0))}</span> <span class="neg">−{e(f.get("removed", 0))}</span></span>'
        f'<div class="x">{e(f.get("explanation", ""))}</div></div>' for f in fl)
    add = sum(int(f.get("added", 0) or 0) for f in fl)
    rem = sum(int(f.get("removed", 0) or 0) for f in fl)
    what = "".join(f"<li>{e(w)}</li>" for w in c.get("what", []))
    title = re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", str(c.get("title", "")))  # type is shown as a tag already
    return (f'<div class="item"><span class="node"></span><details class="cm"{" open" if open_ else ""}><summary>'
            f'<span class="tag">{e(c.get("type", "change"))}</span><span class="t">{e(title)}</span>'
            f'<span class="r mono num"><span><span class="pos">+{add}</span> <span class="neg">−{rem}</span></span>'
            f'<span>{e(str(c.get("sha", ""))[:7])}</span>{icon("chev-r", 16, "i chev")}</span></summary>'
            f'<div class="body"><div class="k">{e(tr("why"))}</div><div>{e(c.get("why", ""))}</div>'
            + (f'<div class="k">{e(tr("what_changed"))}</div><ul>{what}</ul>' if what else "")
            + (f'<div class="k">{e(tr("files"))}</div><div class="files">{files}</div>' if files else "")
            + snippet_html(c.get("snippet")) + "</div></details></div>")


def quiz_html(quiz, attempt):
    if not quiz:
        return f'<div class="card empty">{e(tr("no_quiz"))}</div>'
    qs = []
    for i, q in enumerate(quiz):
        opts = "".join(f'<button class="opt" type="button"><span class="key">{chr(65+j)}</span><span>{e(o)}</span></button>'
                       for j, o in enumerate(q["options"]))
        tag = f'<span class="tag">{e(q["topic"])}</span>' if q.get("topic") else ""
        qs.append(f'<div class="card q" data-answer="{int(q["answer"])}"><p class="qq"><span class="n">{i+1:02d}</span>'
                  f'<span>{e(q["question"])}</span>{tag}</p>{opts}<div class="why"><b></b>{e(q.get("explanation", ""))}</div></div>')
    rec = ""
    if attempt:
        p = attempt["score"] / max(attempt["total"], 1)
        score = f'<b class="mono num {tone(p)}">{attempt["score"]}/{attempt["total"]}</b>'
        rec = (f'<div class="recorded"><span class="{tone(p)}">{icon("check-circle")}</span>'
               f'<span>{e(tr("recorded", score="@@S@@", date=attempt["date"])).replace("@@S@@", score)}</span></div>')
    return (f'{rec}<div class="qhead"><div class="track"><div id="qtrack"></div></div><span class="mono muted" id="qcount"></span></div>'
            f'{"".join(qs)}'
            '<div class="card result" id="result"><svg class="ring" viewBox="0 0 120 120">'
            '<circle cx="60" cy="60" r="50" fill="none" stroke="var(--raised)" stroke-width="8"/>'
            '<circle id="arc" cx="60" cy="60" r="50" fill="none" stroke-width="8" stroke-linecap="round" transform="rotate(-90 60 60)" stroke-dasharray="0 999"/>'
            '<text id="rnum" x="60" y="68" text-anchor="middle" font-size="24" font-weight="500" fill="var(--ink)" font-family="ui-monospace,SF Mono,Menlo,monospace"></text></svg>'
            '<h3 id="rtitle"></h3><p id="rtext"></p>'
            f'<div class="copy"><input id="cline" readonly aria-label="{e(tr("paste_aria"))}"><button class="btn" id="cbtn" type="button">{icon("copy")} {e(tr("copy"))}</button></div>'
            f'<p class="hint">{e(tr("paste_hint"))}</p>'
            f'<p style="margin:20px 0 0"><button class="btn ghost" id="retry" type="button">{icon("rotate")} {e(tr("try_again"))}</button></p></div>')


# ───────────────────────────── pages ─────────────────────────────

def render(d, report_rel, attempt):
    repo, branch = d.get("repo", "repo"), d.get("branch", "")
    commits = d.get("commits", [])
    allf = [f for c in commits for f in c.get("files", [])]
    add = sum(int(f.get("added", 0) or 0) for f in allf)
    rem = sum(int(f.get("removed", 0) or 0) for f in allf)
    checks = d.get("checks", [])
    ran = [c for c in checks if c.get("status") != "skipped"]
    passed = sum(c.get("status") == "pass" for c in checks)
    failed = sum(c.get("status") == "fail" for c in checks)
    quiz = d.get("quiz", [])
    links = "".join(x for x in [
        f'<a href="{e(d["repo_url"])}">GitHub {icon("out", 14)}</a>' if d.get("repo_url") else "",
        f'<a href="{e(d["compare_url"])}">Diff {icon("out", 14)}</a>' if d.get("compare_url") else "",
        f'<a href="{e(d["pr_url"])}">{e(tr("pull_request"))} {icon("out", 14)}</a>' if d.get("pr_url") else ""] if x)
    steps = "".join(f'<div class="item"><span class="node"></span><code>{e(o.get("command"))}</code><p>{e(o.get("explanation"))}</p>'
                    + (f'<pre>{e(o["output"])}</pre>' if o.get("output") else "") + "</div>" for o in d.get("git_operations", []))
    terms = "".join(f'<dt>{e(c.get("term"))}</dt><dd>{e(c.get("explanation"))}</dd>' for c in d.get("concepts", []))
    nav = [(k, tr("nav_" + k)) for k in ("done", "checks", "diagram", "commits", "git", "quiz")]
    headline = d.get("headline") or tr("pushed_default", n=len(commits), repo=repo)
    banner = ""
    if failed:
        banner = (f'<div class="banner"><span class="neg">{icon("alert")}</span><span>{e(tr("checks_failed", n=failed))} '
                  + e(tr("pushed_anyway") if d.get("pushed_despite_failures") else tr("look_first")) + "</span></div>")
    nd, rk = d.get("not_done_yet"), d.get("risks")
    side = ""
    if nd or rk:
        blocks = []
        if nd:
            blocks.append(f'<div class="card"><p class="sub">{e(tr("still_to_do"))}</p>{bullet_list(nd, "circle", "muted")}</div>')
        if rk:
            blocks.append(f'<div class="card"><p class="sub">{e(tr("watch_out"))}</p>{bullet_list(rk, "alert", "warn")}</div>')
        side = f'<div class="{"two" if len(blocks) == 2 else ""}" style="margin-top:12px">{"".join(blocks)}</div>'
    cell = lambda l, v, cls="": f'<div><div class="l">{l}</div><div class="v {cls}">{v}</div></div>'
    body = f"""<body data-key="{e(report_rel)}:{e(d.get("head_sha", ""))}" data-report="{e(report_rel)}">
<nav class="bar"><div class="in"><a class="home" href="../index.html">{icon("chev-l")} {e(tr("reports"))}</a>{"".join(f'<a href="#{i}">{e(t)}</a>' for i, t in nav)}{theme_btn()}</div></nav>
<main><header>
<div class="meta"><span class="mono" style="color:var(--ink-2)">{e(repo)}</span><span class="mono">{icon("branch", 14)}{e(branch)}</span>
<span class="mono">{e(d.get("pushed_at", ""))}</span>{links}</div>
<h1>{e(headline)}</h1><p class="lede">{e(d.get("tldr", ""))}</p>
<div class="strip">{cell(tr("c_commits"), len(commits))}{cell(tr("c_files"), len({f.get("path") for f in allf}))}
{cell(tr("c_lines"), f'<span class="pos">+{add}</span> <small>−{rem}</small>')}
{cell(tr("c_checks"), f"{passed}<small>/{len(ran)}</small>" if ran else f"<small>{e(tr('none'))}</small>", "neg" if failed else "")}
{cell(tr("c_quiz_score") if attempt else tr("c_quiz"), f'{attempt["score"]}<small>/{attempt["total"]}</small>' if attempt else f"{len(quiz)}<small> {e(tr('questions'))}</small>")}</div>
</header>

<section id="done"><div class="sh"><h2>{e(tr("s_done"))}</h2></div>
<div class="card">{bullet_list(d.get("done_for_project", []), "check-circle", "pos")}</div>{side}</section>

<section id="checks"><div class="sh"><h2>{e(tr("s_checks"))}</h2><span class="c">{e(tr("s_checks_c"))}</span></div>{banner}{checks_html(checks)}</section>

<section id="diagram"><div class="sh"><h2>{e(tr("s_diagram"))}</h2></div>{diagram(d)}</section>

<section id="commits"><div class="sh"><h2>{e(tr("s_commits"))}</h2><span class="c">{len(commits)}</span></div>
<div class="rail">{"".join(commit_html(c, len(commits) <= 3) for c in commits)}</div></section>

<section id="git"><div class="sh"><h2>{e(tr("s_git"))}</h2></div>
<div class="card"><div class="rail steps">{steps}</div></div>
{(f'<div class="card"><p class="sub">{e(tr("s_terms"))}</p><dl class="terms">' + terms + '</dl></div>') if terms else ""}</section>

<section id="quiz"><div class="sh"><h2>{e(tr("s_quiz"))}</h2></div>{quiz_html(quiz, attempt)}</section>
</main>"""
    return page(f"{repo} · {branch} · {tr('push_report')}", body, f"<script>{quiz_strings()}{QUIZ_JS}</script>")


def trend_chart(attempts):
    last = attempts[-16:]
    if not last:
        return f'<p class="muted" style="margin:0">{e(tr("no_scores"))}</p>'
    W, H, L, T, B = 520, 200, 36, 12, 28
    n = len(last)
    step = (W - L) / max(n, 1)
    bw = min(24, step * .55)
    r = lambda a: a["score"] / max(a["total"], 1)
    y = lambda p: T + (H - T - B) * (1 - p)
    mono = 'font-family="ui-monospace,SF Mono,Menlo,monospace"'
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(tr("scores_aria"))}">']
    for p in (0, .5, 1):
        o.append(f'<line x1="{L}" x2="{W}" y1="{y(p)}" y2="{y(p)}" stroke="var(--line)" />'
                 f'<text x="{L-8}" y="{y(p)+4}" text-anchor="end" font-size="11" fill="var(--muted)" {mono}>{int(p*100)}%</text>')
    o.append(f'<line x1="{L}" x2="{W}" y1="{y(.7)}" y2="{y(.7)}" stroke="var(--muted)" stroke-dasharray="3 4" opacity=".6"/>'
             f'<text x="{W}" y="{y(.7)-6}" text-anchor="end" font-size="11" fill="var(--muted)" {mono}>{e(tr("goal"))}</text>')
    for i, a in enumerate(last):
        x = L + step * i + (step - bw) / 2
        h = max((H - T - B) * r(a), 2)
        fill = "var(--accent)" if i == n - 1 else "var(--line-2)"
        o.append(f'<rect x="{x:.1f}" y="{y(r(a)):.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="{fill}">'
                 f'<title>{e(a.get("repo"))} · {e(a["date"])}: {a["score"]}/{a["total"]}</title></rect>')
        if i in (0, n - 1):
            o.append(f'<text x="{x+bw/2:.1f}" y="{H-8}" text-anchor="middle" font-size="11" fill="var(--muted)" {mono}>{e(a["date"][5:10])}</text>')
    o.append("</svg>")
    return "".join(o)


def render_index(root):
    prog = load_progress(root)
    reports = sorted((p for p in root.glob("*/*.html") if p.parent.name != "digests"), key=lambda p: p.stat().st_mtime, reverse=True)
    digests = sorted((root / "digests").glob("*.html"), reverse=True)[:12]
    by_repo = {}
    for p in reports:
        by_repo.setdefault(p.parent.name, []).append(p)
    attempts = prog["attempts"]
    ratio = lambda a: a["score"] / max(a["total"], 1)
    avg = sum(map(ratio, attempts)) / len(attempts) if attempts else None
    weak = {t for t, _, _ in weak_topics(prog)}
    topics = sorted(topic_stats(prog).items(), key=lambda kv: kv[1][0] / kv[1][1])
    focus_tag = f'<span class="tag">{e(tr("focus"))}</span>'
    topic_rows = "".join(
        f'<div class="topic{" weak" if t in weak else ""}"><span class="nm">{e(t)}'
        f'{focus_tag if t in weak else ""}</span><span class="pc">{c}/{n} · {c/n*100:.0f}%</span>'
        f'<div class="tr"><div style="width:{c/n*100:.0f}%"></div></div></div>' for t, (c, n) in topics)
    groups = []
    for repo, ps in by_repo.items():
        rows = []
        for p in ps:
            rel = p.relative_to(root).as_posix()
            a = latest_attempt(prog, rel)
            try:
                meta = json.loads(p.with_suffix(".json").read_text())
            except Exception:
                meta = {}
            sc = (f'<span class="sc num {tone(ratio(a))}">{a["score"]}/{a["total"]}</span>' if a
                  else f'<span class="sc muted">{e(tr("no_score"))}</span>')
            rows.append(f'<a class="row" href="{e(rel)}"><div class="w"><b>{e(meta.get("headline") or p.stem)}</b>'
                        f'<div class="mono">{e(meta.get("pushed_at") or p.stem)} · {e(meta.get("branch", ""))}</div></div>{sc}{icon("chev-r", 16, "i muted")}</a>')
        groups.append(f'<div class="group"><p class="gl">{e(repo)}</p><div class="card rows">{"".join(rows)}</div></div>')
    cell = lambda l, v: f'<div><div class="l">{l}</div><div class="v">{v}</div></div>'
    digest_rows = "".join(
        f'<a class="row" href="digests/{e(p.name)}"><div class="w"><b>{e(p.stem.replace("_", " · "))}</b></div>{icon("chev-r", 16, "i muted")}</a>'
        for p in digests)
    digest_sec = (f'<section><div class="sh"><h2>{e(tr("digests"))}</h2></div><div class="card rows">{digest_rows}</div></section>'
                  if digest_rows else "")
    no_topics = f'<p class="muted" style="margin:0">{e(tr("no_topics"))}</p>'
    body = f"""<body>
<nav class="bar"><div class="in"><a class="home" href="#">git-explained</a>{theme_btn()}</div></nav>
<main><h1 style="margin-top:0">{e(tr("idx_title"))}</h1>
<p class="lede">{e(tr("idx_lede"))}</p>
<div class="strip">{cell(tr("i_pushes"), len(reports))}{cell(tr("i_quizzes"), len(attempts))}
{cell(tr("i_avg"), f"{avg*100:.0f}<small>%</small>" if avg is not None else f"<small>{e(tr('none_yet'))}</small>")}{cell(tr("i_repos"), len(by_repo))}</div>
<section><div class="sh"><h2>{e(tr("progress"))}</h2></div><div class="prog">
<div class="card chart"><p class="sub">{e(tr("scores_sub"))}</p>{trend_chart(attempts)}</div>
<div class="card"><p class="sub">{e(tr("by_topic"))}</p>{topic_rows or no_topics}
{(f'<p class="cap" style="margin-top:12px">{e(tr("focus_hint"))}</p>') if weak else ""}</div></div></section>
{digest_sec}
<section><div class="sh"><h2>{e(tr("reports"))}</h2></div>{"".join(groups) or f'<div class="card empty">{e(tr("no_reports"))}</div>'}</section>
</main>"""
    (root / "index.html").write_text(page(tr("idx_title"), body))


# ───────────────────────────── commands ─────────────────────────────

def open_file(path):
    """Open a local file in the default browser: macOS, Linux and Windows."""
    webbrowser.open(Path(path).resolve().as_uri())


def write_report(root, data, html_path):
    rel = html_path.relative_to(root).as_posix()
    set_lang(root, data)
    html_path.write_text(render(data, rel, latest_attempt(load_progress(root), rel)))


def cmd_render():
    root = out_root()
    data = json.loads(Path(sys.argv[1]).read_text())
    if not data.get("language"):
        data["language"] = load_config(root).get("language", "en")
    for q in data.get("quiz", []):
        assert 0 <= int(q["answer"]) < len(q["options"]), f"bad answer index in: {q['question']}"
    folder = root / slug(data.get("repo", "repo"))
    folder.mkdir(parents=True, exist_ok=True)
    stem = f'{datetime.now():%Y-%m-%d_%H%M}_{slug(data.get("branch", "branch"))}'
    out, k = folder / f"{stem}.html", 2
    while out.exists():  # two pushes in the same minute must not overwrite each other
        out, k = folder / f"{stem}-{k}.html", k + 1
    out.with_suffix(".json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    write_report(root, data, out)
    set_lang(root)
    render_index(root)
    print(out)
    if "--open" in sys.argv:
        open_file(out)


def cmd_record():
    root = out_root()
    target = Path(sys.argv[2]).expanduser()
    if not target.exists():
        target = root / sys.argv[2]
    target = target.with_suffix(".html").resolve()
    data = json.loads(target.with_suffix(".json").read_text())
    quiz = data["quiz"]
    raw = [p for p in re.split(r"[,\s]+", arg("--picks", "")) if p]
    picks = [ord(p.upper()) - 65 if p.isalpha() else int(p) for p in raw]
    if len(picks) != len(quiz):
        sys.exit(f"expected {len(quiz)} picks, got {len(picks)}")
    qs = [{"topic": q.get("topic", "general"), "correct": p == int(q["answer"]), "picked": p, "answer": int(q["answer"])}
          for q, p in zip(quiz, picks)]
    rel = target.relative_to(root).as_posix()
    attempt = {"date": f"{datetime.now():%Y-%m-%d %H:%M}", "repo": data.get("repo"), "branch": data.get("branch"),
               "report": rel, "score": sum(q["correct"] for q in qs), "total": len(qs),
               "source": arg("--source", "terminal"), "questions": qs}
    prog = load_progress(root)
    prog["attempts"].append(attempt)
    save_progress(root, prog)
    write_report(root, data, target)
    set_lang(root)
    render_index(root)
    print(json.dumps({"score": attempt["score"], "total": attempt["total"],
                      "wrong": [{"question": i + 1, "topic": q["topic"], "picked": chr(65 + q["picked"]), "answer": chr(65 + q["answer"])}
                                for i, q in enumerate(qs) if not q["correct"]],
                      "weak_topics": [t for t, _, _ in weak_topics(prog)]}, indent=2))


def cmd_weak():
    prog = load_progress(out_root())
    print(json.dumps({"known_topics": sorted(topic_stats(prog)),
                      "weak_topics": [{"topic": t, "accuracy": round(a, 2), "answers": n} for t, a, n in weak_topics(prog)]}, indent=2))


def cmd_config():
    root = out_root()
    cfg = load_config(root)
    lang = arg("--language")
    if lang:
        lang = lang.lower()[:2]
        if lang not in LANGS:
            sys.exit(f"language must be one of {', '.join(LANGS)}")
        cfg["language"] = lang
        root.mkdir(parents=True, exist_ok=True)
        (root / "config.json").write_text(json.dumps(cfg, indent=2))
        set_lang(root)
        render_index(root)
    cfg.setdefault("language", "en")
    print(json.dumps(cfg, indent=2))


def load_data(root, target):
    """Accept a data .json or a report .html (its sidecar .json is used)."""
    p = Path(target).expanduser()
    if not p.exists():
        p = root / target
    if p.suffix == ".html":
        p = p.with_suffix(".json")
    return json.loads(p.read_text())


def cmd_pr_body():
    root = out_root()
    d = load_data(root, sys.argv[2])
    set_lang(root, d)
    md = []
    if d.get("tldr"):
        md += [f"## {tr('pr_summary')}", "", d["tldr"], ""]
    if d.get("done_for_project"):
        md += [f"## {tr('pr_done')}", ""] + [f"- [x] {x}" for x in d["done_for_project"]] + [""]
    if d.get("not_done_yet"):
        md += [f"## {tr('still_to_do')}", ""] + [f"- [ ] {x}" for x in d["not_done_yet"]] + [""]
    if d.get("risks"):
        md += [f"## {tr('pr_risks')}", ""] + [f"- ⚠️ {x}" for x in d["risks"]] + [""]
    if d.get("checks"):
        mark = {"pass": "✅", "fail": "❌", "skipped": "➖"}
        md += [f"## {tr('pr_checks')}", "", "| | Check | Command | |", "|---|---|---|---|"]
        md += [f"| {mark.get(c.get('status'), '➖')} | {c.get('name', '')} | `{c.get('command', '')}` | {c.get('duration') or c.get('status', '')} |"
               for c in d["checks"]] + [""]
    if d.get("commits"):
        md += [f"## {tr('nav_commits')}", ""]
        for c in d["commits"]:
            md.append(f"- `{str(c.get('sha', ''))[:7]}` **{c.get('title', '')}**" + (f": {c['why']}" if c.get("why") else ""))
        md.append("")
    md += ["---", f"<sub>{tr('pr_footer')}</sub>"]
    print("\n".join(md))


def parse_when(s):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s)[:19], fmt)
        except ValueError:
            continue
    return None


def cmd_digest():
    root = out_root()
    set_lang(root)
    days = int(arg("--days", "7"))
    only = arg("--repo")
    end = datetime.now()
    start = end - timedelta(days=days)
    prog = load_progress(root)
    items = []
    for j in root.glob("*/*.json"):
        if j.parent.name == "digests" or (only and j.parent.name != slug(only)):
            continue
        try:
            d = json.loads(j.read_text())
        except Exception:
            continue
        when = parse_when(d.get("pushed_at")) or datetime.fromtimestamp(j.stat().st_mtime)
        if when >= start:
            items.append((when, j, d))
    items.sort(key=lambda x: x[0])
    repos = {}
    for when, j, d in items:
        repos.setdefault(d.get("repo") or j.parent.name, []).append((when, j, d))

    def dedup(seq):
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    n_commits = sum(len(d.get("commits", [])) for _, _, d in items)
    lines = sum(int(f.get("added", 0) or 0) + int(f.get("removed", 0) or 0)
                for _, _, d in items for c in d.get("commits", []) for f in c.get("files", []))
    rels = {j.with_suffix(".html").relative_to(root).as_posix() for _, j, _ in items}
    att = [a for a in prog["attempts"] if a.get("report") in rels]
    avg = sum(a["score"] / max(a["total"], 1) for a in att) / len(att) if att else None
    title = tr("dg_title", days=days)
    lede = tr("dg_lede", start=f"{start:%Y-%m-%d}", end=f"{end:%Y-%m-%d}", n=len(repos))

    # Markdown (standup / Slack / weekly update)
    md = [f"# {title}", "", lede, "",
          f"**{tr('i_pushes')}:** {len(items)} · **{tr('c_commits')}:** {n_commits} · **{tr('c_lines')}:** {lines}"
          + (f" · **{tr('dg_quiz')}:** {avg*100:.0f}%" if avg is not None else ""), ""]
    for repo, its in repos.items():
        done = dedup(x for _, _, d in its for x in d.get("done_for_project", []))
        todo = dedup(x for _, _, d in its[-1:] for x in d.get("not_done_yet", []))  # latest push = current state
        risks = dedup(x for _, _, d in its for x in d.get("risks", []))
        md += [f"## {repo}", ""] + [f"- ✅ {x}" for x in done]
        md += [f"- ⏳ {x}" for x in todo] + [f"- ⚠️ {x}" for x in risks] + [""]
    if not items:
        md += [tr("dg_empty"), ""]
    md_text = "\n".join(md)

    # HTML
    blocks = []
    for repo, its in repos.items():
        done = dedup(x for _, _, d in its for x in d.get("done_for_project", []))
        todo = dedup(x for _, _, d in its[-1:] for x in d.get("not_done_yet", []))
        risks = dedup(x for _, _, d in its for x in d.get("risks", []))
        side = []
        if todo:
            side.append(f'<div class="card"><p class="sub">{e(tr("still_to_do"))}</p>{bullet_list(todo, "circle", "muted")}</div>')
        if risks:
            side.append(f'<div class="card"><p class="sub">{e(tr("watch_out"))}</p>{bullet_list(risks, "alert", "warn")}</div>')
        rows = "".join(
            f'<a class="row" href="../{e(j.with_suffix(".html").relative_to(root).as_posix())}"><div class="w"><b>{e(d.get("headline") or j.stem)}</b>'
            f'<div class="mono">{e(d.get("pushed_at") or "")} · {e(d.get("branch", ""))} · {len(d.get("commits", []))} commits</div></div>'
            f'{icon("chev-r", 16, "i muted")}</a>' for _, j, d in reversed(its))
        blocks.append(f'<section><div class="sh"><h2>{e(repo)}</h2><span class="c">{len(its)} push</span></div>'
                      f'<div class="card"><p class="sub">{e(tr("dg_done"))}</p>{bullet_list(done, "check-circle", "pos")}</div>'
                      + (f'<div class="{"two" if len(side) == 2 else ""}" style="margin-top:12px">{"".join(side)}</div>' if side else "")
                      + f'<div class="group"><p class="gl">{e(tr("dg_pushlist"))}</p><div class="card rows">{rows}</div></div></section>')
    cell = lambda l, v: f'<div><div class="l">{e(l)}</div><div class="v">{v}</div></div>'
    body = f"""<body>
<nav class="bar"><div class="in"><a class="home" href="../index.html">{icon("chev-l")} {e(tr("reports"))}</a>{theme_btn()}</div></nav>
<main><h1 style="margin-top:0">{e(title)}</h1><p class="lede">{e(lede)}</p>
<div class="strip">{cell(tr("i_pushes"), len(items))}{cell(tr("c_commits"), n_commits)}{cell(tr("c_lines"), lines)}
{cell(tr("dg_quiz"), f"{avg*100:.0f}<small>%</small>" if avg is not None else f"<small>{e(tr('none_yet'))}</small>")}</div>
{"".join(blocks) or f'<section><div class="card empty">{e(tr("dg_empty"))}</div></section>'}
<section><div class="sh"><h2>{e(tr("dg_md"))}</h2></div><div class="card"><pre style="white-space:pre-wrap">{e(md_text)}</pre></div></section>
</main>"""
    folder = root / "digests"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{end:%Y-%m-%d}_{days}d" + (f"_{slug(only)}" if only else "")
    (folder / f"{name}.md").write_text(md_text)
    (folder / f"{name}.html").write_text(page(title, body))
    render_index(root)
    print(folder / f"{name}.html")
    print(folder / f"{name}.md")
    if "--open" in sys.argv:
        open_file(folder / f"{name}.html")


def cmd_open():
    open_file(sys.argv[2])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    {"record": cmd_record, "weak": cmd_weak, "config": cmd_config, "pr-body": cmd_pr_body,
     "digest": cmd_digest, "open": cmd_open}.get(sys.argv[1], cmd_render)()
