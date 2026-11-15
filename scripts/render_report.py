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

Visual design pass guided by "unslop" by Damir Sokolovsky (@heydamir), CC BY 4.0,
https://github.com/heydamir/unslop
"""
import html
import json
import re
import sys
from datetime import datetime
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
THEME_BTN = '<button class="theme" id="theme" type="button" aria-label="Change theme">Auto</button>'
_SVG = lambda p: ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" '
                  'stroke-linecap="round" stroke-linejoin="round">' + p + '</svg>')
THEME_JS = ("<script>(function(){var b=document.getElementById('theme'),R=document.documentElement,O=['auto','light','dark'],"
            "I={auto:'" + _SVG('<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>') + " Auto',"
            "light:'" + _SVG('<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/>'
                             '<path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/>'
                             '<path d="m19.07 4.93-1.41 1.41"/>') + " Light',"
            "dark:'" + _SVG('<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>') + " Dark'},c=R.dataset.theme||'auto';b.innerHTML=I[c];"
            "b.onclick=function(){c=O[(O.indexOf(c)+1)%3];if(c==='auto')delete R.dataset.theme;else R.dataset.theme=c;"
            "try{c==='auto'?localStorage.removeItem('gx-theme'):localStorage.setItem('gx-theme',c)}catch(_){}b.innerHTML=I[c]}})();</script>")

QUIZ_JS = """
const B=document.body,KEY='gx-quiz:'+B.dataset.key,qs=[...document.querySelectorAll('.q')];
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(_){}
const L=i=>String.fromCharCode(65+i),$=id=>document.getElementById(id);
function show(q,pick){const a=+q.dataset.answer;q.classList.add('done');
 const w=q.querySelector('.why b');w.textContent=pick===a?'Correct. ':'Not quite. The answer is '+L(a)+'. ';w.className=pick===a?'pos':'neg';
 q.querySelectorAll('.opt').forEach((b,i)=>{b.disabled=true;if(i===a)b.classList.add('ok');else if(i===pick)b.classList.add('no')})}
function upd(){if(!qs.length)return;const n=Object.keys(st).length,ok=qs.filter((q,i)=>st[i]===+q.dataset.answer).length;
 $('qtrack').style.width=(n/qs.length*100)+'%';$('qcount').textContent=n+' of '+qs.length;
 const r=$('result');if(n<qs.length){r.classList.remove('show');return}
 r.classList.add('show');const p=ok/qs.length,c=2*Math.PI*50;
 $('arc').setAttribute('stroke-dasharray',(p*c)+' '+c);
 $('arc').setAttribute('stroke',p>=.85?'var(--pos)':p>=.6?'var(--warn)':'var(--neg)');
 $('rnum').textContent=ok+'/'+qs.length;
 $('rtitle').textContent=p===1?'You understand this push':p>=.7?'A solid read of this push':'Worth a second read';
 $('rtext').textContent=p===1?'Every answer right. You could explain these changes to anyone.':
  'Go back to the commits behind the questions you missed, then try again.';
 $('cline').value='git-explained quiz '+B.dataset.report+': '+qs.map((q,i)=>L(st[i])).join(',')}
qs.forEach((q,i)=>{if(st[i]!==undefined)show(q,st[i]);
 q.querySelectorAll('.opt').forEach((b,j)=>b.onclick=()=>{st[i]=j;try{localStorage.setItem(KEY,JSON.stringify(st))}catch(_){};show(q,j);upd()})});
if($('retry'))$('retry').onclick=()=>{st={};try{localStorage.removeItem(KEY)}catch(_){};location.reload()};
if($('cbtn'))$('cbtn').onclick=async()=>{const i=$('cline');i.select();
 try{await navigator.clipboard.writeText(i.value)}catch(_){document.execCommand('copy')}$('cbtn').lastChild.textContent=' Copied'};
upd();
"""


def page(title, body, scripts=""):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title>{FONTS}<style>{CSS}</style>{THEME_HEAD}</head>{body}{scripts}{THEME_JS}</body></html>')


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
    o = [f'<svg viewBox="0 0 {W} 248" role="img" aria-label="Commits on your Mac and on GitHub, before and after the push">']
    for y, name, sub in [(yG, "GitHub", f'{d.get("remote", "origin")}/{d.get("branch", "")}'), (yM, "Your Mac", d.get("branch", ""))]:
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
             f'<text x="{x0}" y="{yG-20}" text-anchor="middle" font-size="11" fill="var(--muted)" {mono}>shared</text>')
    for x, c in zip(xs, shown):
        for y in (yG, yM):
            o.append(f'<circle cx="{x}" cy="{y}" r="8" fill="var(--accent)" stroke="var(--surface)" stroke-width="3"/>')
        o.append(f'<text x="{x}" y="{yM+32}" text-anchor="middle" font-size="11" fill="var(--ink-2)" {mono}>{e(str(c.get("sha", ""))[:7])}</text>'
                 f'<text x="{x}" y="{yG-20}" text-anchor="middle" font-size="11" fill="var(--accent)" {mono}>{e(c.get("type", "new"))}</text>')
    if extra:
        o.append(f'<text x="{xe+12}" y="{(yG+yM)/2+4}" font-size="12" fill="var(--muted)" {mono}>+{extra} more</text>')
    o.append("</svg>")
    ahead = int(d.get("remote_ahead_before") or 0)
    extra_p = ""
    if d.get("new_branch"):
        extra_p += ('<p class="para">This branch didn\'t exist on GitHub yet, so the push created it. '
                    '<code>-u</code> links your local branch to it, so later pushes know where to go.</p>')
    if ahead:
        extra_p += (f'<p class="para">GitHub had {ahead} commit{"s" if ahead != 1 else ""} you didn\'t have yet. '
                    f'They were pulled in first so both histories matched before pushing.</p>')
    return (f'<div class="card diagram">{"".join(o)}<div class="legend">'
            f'<span><i class="dot" style="border:2px solid var(--muted)"></i>On both before the push</span>'
            f'<span><i class="dot" style="background:var(--accent)"></i>Sent by this push</span></div>'
            f'<p class="para">Before the push, the blue commits existed only on your Mac. <code>git push</code> copied them to GitHub, '
            f'so both now hold the same history.</p>{extra_p}</div>')


def checks_html(checks):
    if not checks:
        return ('<div class="card"><ul class="list"><li><span class="muted">' + icon("circle") + '</span><span>No automated checks '
                '(tests, lint, type check, build) were found in this project. Even a build check catches broken code before it reaches GitHub.'
                '</span></li></ul></div>')
    ic = {"pass": ("check", "pos"), "fail": ("x", "neg"), "skipped": ("minus", "muted")}
    rows = []
    for c in checks:
        n, cls = ic.get(c.get("status"), ("minus", "muted"))
        out = f'<details><summary>Show output</summary><pre>{e(c["output"])}</pre></details>' if c.get("output") else ""
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
    return (f'<div class="k">Key code <span class="mono muted" style="margin-left:8px">{e(sn.get("file", ""))}</span></div>'
            f'<pre>{"".join(lines)}</pre><p class="cap">{e(sn.get("explanation", ""))}</p>')


def commit_html(c, open_):
    status = {"added": "new", "modified": "edit", "deleted": "removed", "renamed": "renamed"}
    fl = c.get("files", [])
    files = "".join(
        f'<div class="file"><span class="p mono"><span class="s">{status.get(f.get("status"), "edit")}</span>{e(f.get("path"))}</span>'
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
            f'<div class="body"><div class="k">Why</div><div>{e(c.get("why", ""))}</div>'
            + (f'<div class="k">What changed</div><ul>{what}</ul>' if what else "")
            + (f'<div class="k">Files</div><div class="files">{files}</div>' if files else "")
            + snippet_html(c.get("snippet")) + "</div></details></div>")


def quiz_html(quiz, attempt):
    if not quiz:
        return '<div class="card empty">No quiz for this push</div>'
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
        rec = (f'<div class="recorded"><span class="{tone(p)}">{icon("check-circle")}</span>'
               f'<span>Recorded score <b class="mono num {tone(p)}">{attempt["score"]}/{attempt["total"]}</b> on {e(attempt["date"])}, '
               f'counted in your progress</span></div>')
    return (f'{rec}<div class="qhead"><div class="track"><div id="qtrack"></div></div><span class="mono muted" id="qcount"></span></div>'
            f'{"".join(qs)}'
            '<div class="card result" id="result"><svg class="ring" viewBox="0 0 120 120">'
            '<circle cx="60" cy="60" r="50" fill="none" stroke="var(--raised)" stroke-width="8"/>'
            '<circle id="arc" cx="60" cy="60" r="50" fill="none" stroke-width="8" stroke-linecap="round" transform="rotate(-90 60 60)" stroke-dasharray="0 999"/>'
            '<text id="rnum" x="60" y="68" text-anchor="middle" font-size="24" font-weight="500" fill="var(--ink)" font-family="ui-monospace,SF Mono,Menlo,monospace"></text></svg>'
            '<h3 id="rtitle"></h3><p id="rtext"></p>'
            f'<div class="copy"><input id="cline" readonly aria-label="Answers to paste to Claude"><button class="btn" id="cbtn" type="button">{icon("copy")} Copy</button></div>'
            '<p class="hint">Paste this line to Claude to save the score in your progress</p>'
            f'<p style="margin:20px 0 0"><button class="btn ghost" id="retry" type="button">{icon("rotate")} Try again</button></p></div>')


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
        f'<a href="{e(d["compare_url"])}">Diff {icon("out", 14)}</a>' if d.get("compare_url") else ""] if x)
    steps = "".join(f'<div class="item"><span class="node"></span><code>{e(o.get("command"))}</code><p>{e(o.get("explanation"))}</p>'
                    + (f'<pre>{e(o["output"])}</pre>' if o.get("output") else "") + "</div>" for o in d.get("git_operations", []))
    terms = "".join(f'<dt>{e(c.get("term"))}</dt><dd>{e(c.get("explanation"))}</dd>' for c in d.get("concepts", []))
    nav = [("done", "Done"), ("checks", "Checks"), ("diagram", "Mac vs GitHub"), ("commits", "Commits"), ("git", "Git steps"), ("quiz", "Quiz")]
    headline = d.get("headline") or f"Pushed {len(commits)} commit{'s' if len(commits) != 1 else ''} to {repo}"
    banner = ""
    if failed:
        banner = (f'<div class="banner"><span class="neg">{icon("alert")}</span><span>{failed} check{"s" if failed != 1 else ""} failed. '
                  + ("You chose to push anyway, the output is below." if d.get("pushed_despite_failures")
                     else "Look at them before relying on this push.") + "</span></div>")
    nd, rk = d.get("not_done_yet"), d.get("risks")
    side = ""
    if nd or rk:
        blocks = []
        if nd:
            blocks.append(f'<div class="card"><p class="sub">Still to do</p>{bullet_list(nd, "circle", "muted")}</div>')
        if rk:
            blocks.append(f'<div class="card"><p class="sub">Watch out</p>{bullet_list(rk, "alert", "warn")}</div>')
        side = f'<div class="{"two" if len(blocks) == 2 else ""}" style="margin-top:12px">{"".join(blocks)}</div>'
    cell = lambda l, v, cls="": f'<div><div class="l">{l}</div><div class="v {cls}">{v}</div></div>'
    body = f"""<body data-key="{e(report_rel)}:{e(d.get("head_sha", ""))}" data-report="{e(report_rel)}">
<nav class="bar"><div class="in"><a class="home" href="../index.html">{icon("chev-l")} Reports</a>{"".join(f'<a href="#{i}">{t}</a>' for i, t in nav)}{THEME_BTN}</div></nav>
<main><header>
<div class="meta"><span class="mono" style="color:var(--ink-2)">{e(repo)}</span><span class="mono">{icon("branch", 14)}{e(branch)}</span>
<span class="mono">{e(d.get("pushed_at", ""))}</span>{links}</div>
<h1>{e(headline)}</h1><p class="lede">{e(d.get("tldr", ""))}</p>
<div class="strip">{cell("Commits", len(commits))}{cell("Files changed", len({f.get("path") for f in allf}))}
{cell("Lines", f'<span class="pos">+{add}</span> <small>−{rem}</small>')}
{cell("Checks passed", f"{passed}<small>/{len(ran)}</small>" if ran else "<small>none</small>", "neg" if failed else "")}
{cell("Quiz score" if attempt else "Quiz", f'{attempt["score"]}<small>/{attempt["total"]}</small>' if attempt else f"{len(quiz)}<small> questions</small>")}</div>
</header>

<section id="done"><div class="sh"><h2>What you can mark as done</h2></div>
<div class="card">{bullet_list(d.get("done_for_project", []), "check-circle", "pos")}</div>{side}</section>

<section id="checks"><div class="sh"><h2>Checks before pushing</h2><span class="c">tests, lint, types, build</span></div>{banner}{checks_html(checks)}</section>

<section id="diagram"><div class="sh"><h2>Your Mac and GitHub</h2></div>{diagram(d)}</section>

<section id="commits"><div class="sh"><h2>Commits explained</h2><span class="c">{len(commits)}</span></div>
<div class="rail">{"".join(commit_html(c, len(commits) <= 3) for c in commits)}</div></section>

<section id="git"><div class="sh"><h2>What was done with Git and GitHub</h2></div>
<div class="card"><div class="rail steps">{steps}</div></div>
{('<div class="card"><p class="sub">Terms used in this push</p><dl class="terms">' + terms + '</dl></div>') if terms else ""}</section>

<section id="quiz"><div class="sh"><h2>Check your understanding</h2></div>{quiz_html(quiz, attempt)}</section>
</main>"""
    return page(f"{repo} · {branch} · push report", body, f"<script>{QUIZ_JS}</script>")


def trend_chart(attempts):
    last = attempts[-16:]
    if not last:
        return '<p class="muted" style="margin:0">Your scores show up here once you record a quiz</p>'
    W, H, L, T, B = 520, 200, 36, 12, 28
    n = len(last)
    step = (W - L) / max(n, 1)
    bw = min(24, step * .55)
    r = lambda a: a["score"] / max(a["total"], 1)
    y = lambda p: T + (H - T - B) * (1 - p)
    mono = 'font-family="ui-monospace,SF Mono,Menlo,monospace"'
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Quiz scores over time">']
    for p in (0, .5, 1):
        o.append(f'<line x1="{L}" x2="{W}" y1="{y(p)}" y2="{y(p)}" stroke="var(--line)" />'
                 f'<text x="{L-8}" y="{y(p)+4}" text-anchor="end" font-size="11" fill="var(--muted)" {mono}>{int(p*100)}%</text>')
    o.append(f'<line x1="{L}" x2="{W}" y1="{y(.7)}" y2="{y(.7)}" stroke="var(--muted)" stroke-dasharray="3 4" opacity=".6"/>'
             f'<text x="{W}" y="{y(.7)-6}" text-anchor="end" font-size="11" fill="var(--muted)" {mono}>70% goal</text>')
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
    reports = sorted(root.glob("*/*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    by_repo = {}
    for p in reports:
        by_repo.setdefault(p.parent.name, []).append(p)
    attempts = prog["attempts"]
    ratio = lambda a: a["score"] / max(a["total"], 1)
    avg = sum(map(ratio, attempts)) / len(attempts) if attempts else None
    weak = {t for t, _, _ in weak_topics(prog)}
    topics = sorted(topic_stats(prog).items(), key=lambda kv: kv[1][0] / kv[1][1])
    topic_rows = "".join(
        f'<div class="topic{" weak" if t in weak else ""}"><span class="nm">{e(t)}'
        f'{"<span class=tag>focus</span>" if t in weak else ""}</span><span class="pc">{c}/{n} · {c/n*100:.0f}%</span>'
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
                  else '<span class="sc muted">no score yet</span>')
            rows.append(f'<a class="row" href="{e(rel)}"><div class="w"><b>{e(meta.get("headline") or p.stem)}</b>'
                        f'<div class="mono">{e(meta.get("pushed_at") or p.stem)} · {e(meta.get("branch", ""))}</div></div>{sc}{icon("chev-r", 16, "i muted")}</a>')
        groups.append(f'<div class="group"><p class="gl">{e(repo)}</p><div class="card rows">{"".join(rows)}</div></div>')
    cell = lambda l, v: f'<div><div class="l">{l}</div><div class="v">{v}</div></div>'
    body = f"""<body>
<nav class="bar"><div class="in"><a class="home" href="#">git-explained</a>{THEME_BTN}</div></nav>
<main><h1 style="margin-top:0">Push reports and progress</h1>
<p class="lede">Every push made with Claude, what it delivered, and how well you understood it</p>
<div class="strip">{cell("Pushes", len(reports))}{cell("Quizzes recorded", len(attempts))}
{cell("Average score", f"{avg*100:.0f}<small>%</small>" if avg is not None else "<small>none yet</small>")}{cell("Repos", len(by_repo))}</div>
<section><div class="sh"><h2>Progress</h2></div><div class="prog">
<div class="card chart"><p class="sub">Quiz scores, latest in blue</p>{trend_chart(attempts)}</div>
<div class="card"><p class="sub">By topic</p>{topic_rows or '<p class="muted" style="margin:0">Topics appear after your first recorded quiz</p>'}
{('<p class="cap" style="margin-top:12px">Topics marked focus come up more in your next quizzes</p>') if weak else ""}</div></div></section>
<section><div class="sh"><h2>Reports</h2></div>{"".join(groups) or '<div class="card empty">No reports yet</div>'}</section>
</main>"""
    (root / "index.html").write_text(page("Push reports", body))


# ───────────────────────────── commands ─────────────────────────────

def write_report(root, data, html_path):
    rel = html_path.relative_to(root).as_posix()
    html_path.write_text(render(data, rel, latest_attempt(load_progress(root), rel)))


def cmd_render():
    root = out_root()
    data = json.loads(Path(sys.argv[1]).read_text())
    for q in data.get("quiz", []):
        assert 0 <= int(q["answer"]) < len(q["options"]), f"bad answer index in: {q['question']}"
    folder = root / slug(data.get("repo", "repo"))
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f'{datetime.now():%Y-%m-%d_%H%M}_{slug(data.get("branch", "branch"))}.html'
    out.with_suffix(".json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    write_report(root, data, out)
    render_index(root)
    print(out)


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
    render_index(root)
    print(json.dumps({"score": attempt["score"], "total": attempt["total"],
                      "wrong": [{"question": i + 1, "topic": q["topic"], "picked": chr(65 + q["picked"]), "answer": chr(65 + q["answer"])}
                                for i, q in enumerate(qs) if not q["correct"]],
                      "weak_topics": [t for t, _, _ in weak_topics(prog)]}, indent=2))


def cmd_weak():
    prog = load_progress(out_root())
    print(json.dumps({"known_topics": sorted(topic_stats(prog)),
                      "weak_topics": [{"topic": t, "accuracy": round(a, 2), "answers": n} for t, a, n in weak_topics(prog)]}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    {"record": cmd_record, "weak": cmd_weak}.get(sys.argv[1], cmd_render)()
