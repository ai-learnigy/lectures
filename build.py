# ლექციების ბიბლიოთეკის ბილდი.
#   python3 build.py              → ყველა ლექცია + მთავარი გვერდი → რეპოს root (index.html, <კურსი>/<ლექცია>/)
#   python3 build.py efcore/03    → მხოლოდ ის ლექციები, რომელთა გზაც ამას შეიცავს (მთავარი გვერდის გარეშე)
#
# courses/<კურსი>/course.json — {"title", "order"}: ერთი კურსი = ერთი ჩანართი მთავარ გვერდზე (C#, EF Core, ASP.NET, SQL, DevOps)
# ლექციის საქაღალდე courses/<კურსი>/<NN-slug>/:
#   deck.html       სლაიდები. ყოველ სლაიდში შეიძლება <aside class="study">…markdown…</aside> — სტუდენტის ახსნა
#   lecture.json    {"title", "why", "outcomes": [...], "review": [{"q", "a"}, ...], "starts_series": true?}
#   classwork.md    კლასში დავალება            homework.md    საშინაო (+ "## ამოხსნა" — ჩანს მხოლოდ შემდეგ ლექციაზე)
#   materials/      ფაილები ჩამოსატვირთად
#
# ყველა HTML გვერდი იშიფრება კოდით (.access-code ან LECTURES_CODE) — engine/gate.html კოდს ერთხელ ითხოვს.
#
# deck.html-ში ლექციის ნაწილები ცხადად იწერება (build მათ სლაიდებად აქცევს):
#   <lecture-review/>            გამეორება — წინა ლექციის review კითხვები
#   <lecture-homework-review/>   წინა ლექციის საშინაო + ამოხსნა
#   <lecture-intro/>             დღის თემა — why + outcomes
#   <lecture-classwork/>         კლასში დავალება (classwork.md)
#   <lecture-check/>             შევამოწმოთ — ამ ლექციის review კითხვები
#   <lecture-homework/>          საშინაო (homework.md, ამოხსნის გარეშე)
import base64, html, json, os, pathlib, re, shutil, sys
import markdown
from pygments.lexers import get_lexer_by_name
from pygments.token import STANDARD_TYPES
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = pathlib.Path(__file__).parent
ENGINE = ROOT / 'engine'
# LECTURES_OUT=dist → separate output folder (Vercel); default: repo root (GitHub Pages serves main/root)
OUT = (ROOT / os.environ['LECTURES_OUT']).resolve() if os.environ.get('LECTURES_OUT') else ROOT
GENERATED = '.generated'   # list of folders build.py created — only these are ever deleted
CSS = (ENGINE / 'engine.css').read_text() + '\n' + (ENGINE / 'theme-light.css').read_text()
JS = (ENGINE / 'engine.js').read_text()
TOKEN_CSS = '\n'.join(l for l in (ENGINE / 'theme-light.css').read_text().split('\n') if l.startswith('.code .'))
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Georgian:wght@400;600;700;800'
         '&family=JetBrains+Mono:wght@400;600;700;800&display=swap" rel="stylesheet">')
esc = html.escape

# ---------- access code ----------
# Every published HTML page is AES-GCM encrypted with a key derived from the access code; engine/gate.html asks for
# the code once, remembers it in the browser and decrypts the page. The code lives in .access-code (not in git).
CODE_FILE = ROOT / '.access-code'
PBKDF2_ITERATIONS = 200_000
_key = None

def access_key():
    global _key
    if _key is None:
        code = os.environ.get('LECTURES_CODE') or (CODE_FILE.read_text().strip() if CODE_FILE.exists() else '')
        if not code:
            sys.exit('⚠ კოდი არ არის: შექმენი .access-code ფაილი (ერთი ხაზი — კოდი) ან LECTURES_CODE ცვლადი')
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS)
        _key = (salt, kdf.derive(code.encode()))
    return _key

LECTURER_FILE = ROOT / '.lecturer-code'

def lecturer_code():
    return os.environ.get('LECTURER_CODE') or (LECTURER_FILE.read_text().strip() if LECTURER_FILE.exists() else '')

def write_locked(path, page, code, key_name, heading):
    """ცალკე კოდით დაშიფრული გვერდი (ლექტორისთვის) — სტუდენტის გვერდები ამაზე არ არის დამოკიდებული"""
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS).derive(code.encode())
    b = lambda x: base64.b64encode(x).decode()
    payload = {'s': b(salt), 'i': b(iv), 'n': PBKDF2_ITERATIONS, 'c': b(AESGCM(key).encrypt(iv, page.encode(), None))}
    gate = (ENGINE / 'gate.html').read_text().replace("const KEY = 'lectures:code';", f"const KEY = '{key_name}';")
    gate = gate.replace('<h1>ლექციები</h1>', f'<h1>{heading}</h1>').replace('<title>ლექციები</title>', f'<title>{heading}</title>')
    path.write_text(gate.replace('/*PAYLOAD*/{}', json.dumps(payload)))

def has_code():
    return bool(os.environ.get('LECTURES_CODE') or (CODE_FILE.exists() and CODE_FILE.read_text().strip()))

def write_page(path, page):
    if not has_code():   # კოდი არ არის → გვერდი ღიად ქვეყნდება
        path.write_text(page)
        return
    salt, key = access_key()
    iv = os.urandom(12)
    b = lambda x: base64.b64encode(x).decode()
    payload = {'s': b(salt), 'i': b(iv), 'n': PBKDF2_ITERATIONS, 'c': b(AESGCM(key).encrypt(iv, page.encode(), None))}
    path.write_text((ENGINE / 'gate.html').read_text().replace('/*PAYLOAD*/{}', json.dumps(payload)))

# ---------- code highlighting ----------
def _short(tt):
    while tt not in STANDARD_TYPES:
        tt = tt.parent
    return STANDARD_TYPES[tt]

def highlight(code, lang):
    lines = code.strip('\n').split('\n')
    ind = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    code = '\n'.join(l[ind:] for l in lines)
    toks = [(None, code)] if lang in ('plain', 'text', '') else list(get_lexer_by_name(lang, stripnl=False, ensurenl=False).get_tokens(code))
    out = [[]]
    for tt, val in toks:
        cls = _short(tt) if tt is not None else ''
        for n, part in enumerate(val.split('\n')):
            if n:
                out.append([])
            if part:
                e = esc(part, quote=False)
                if lang.startswith('aspx') or lang == 'asp':
                    e = re.sub(r'(&lt;%[=#:]?|%&gt;)', r'<span class="asp-delim">\1</span>', e)
                out[-1].append(f'<span class="{cls}">{e}</span>' if cls else e)
    while out and not ''.join(out[-1]).strip():
        out.pop()
    return ''.join(f'<span class="ln">{"".join(l) or " "}</span>' for l in out)

def code_block(m):
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    idattr = f' id="{a["id"]}"' if 'id' in a else ''
    style = f' style="{a["style"]}"' if 'style' in a else ''
    ttl = f'<span class="ttl">{a["title"]}</span>' if 'title' in a else ''
    w = ' data-with' if 'data-with' in m.group(1) else ''
    cls = ('code ' + a.get('cls', '')).strip()
    return f'<pre class="{cls}"{idattr}{style}{w}>{ttl}<code>{highlight(m.group(2), a.get("lang", "plain"))}</code></pre>'

LIGHT_MAP = [  # dark-theme SVG colours → light theme (all decks use the light theme)
    ('#151935', '#ffffff'), ('#1b1f3d', '#f1ece3'), ('#0a0c16', '#fbf8f3'), ('#0d1024', '#ffffff'), ('#e8ecff', '#dbeafe'),
    ('#1d1640', '#f3effe'), ('#2a1d4d', '#ede7fd'), ('#0e2a33', '#eaf2fe'), ('#33240b', '#fef5e4'), ('#123321', '#eaf8ef'),
    ('#272c52', '#e6dfd2'), ('#353b6b', '#cfc6b6'),
    ('#22d3ee', '#2563eb'), ('#3b82f6', '#2563eb'), ('#22c55e', '#16a34a'), ('#f5a524', '#d97706'), ('#8b6cff', '#6d28d9'),
    ('#ec4899', '#db2777'), ('#f43f5e', '#dc2626'), ('#a78bfa', '#0d9488'),
    ('rgba(34,211,238,', 'rgba(37,99,235,'), ('rgba(59,130,246,', 'rgba(37,99,235,'), ('rgba(34,197,94,', 'rgba(22,163,74,'),
    ('rgba(245,165,36,', 'rgba(217,119,6,'), ('rgba(244,63,94,', 'rgba(220,38,38,'), ('rgba(167,139,250,', 'rgba(13,148,136,'),
    ('rgba(139,108,255,', 'rgba(109,40,217,'),
]

# ---------- study markdown ----------
# Fenced blocks:  ```csharp Title   ```prompt Title   ```check (? კითხვა / = პასუხი)   ```terms (ტერმინი — ახსნა)   ```note / ```warn
def md_inline(text):
    h = markdown.markdown(text.strip(), extensions=['sane_lists'])
    return re.sub(r'^<p>(.*)</p>$', r'\1', h, flags=re.S)

def render_fence(kind, arg, body):
    body = body.strip('\n')
    if kind == 'prompt':
        return (f'<div class="prompt"><div class="ph"><span>🤖 {esc(arg or "AI-სთვის — დააკოპირე და ჰკითხე")}</span>'
                f'<button class="copy" type="button">კოპირება</button></div><div class="pb">{esc(body)}</div></div>')
    if kind == 'check':
        items, cur = [], None
        for line in body.split('\n'):
            if line.startswith('?'):
                cur = [line[1:].strip(), []]; items.append(cur)
            elif line.startswith('=') and cur:
                cur[1].append(line[1:].strip())
            elif cur and cur[1] and line.strip():
                cur[1].append(line.strip())
        qs = ''.join(f'<details><summary>{md_inline(q)}</summary><div class="ans">{md_inline(" ".join(a))}</div></details>' for q, a in items)
        return f'<div class="selfcheck"><div class="sh">✅ შეამოწმე თავი <small>დაფიქრდი, მერე გახსენი პასუხი</small></div>{qs}</div>'
    if kind == 'terms':
        rows = [l.split('—', 1) for l in body.split('\n') if '—' in l]
        dl = ''.join(f'<dt>{md_inline(t)}</dt><dd>{md_inline(d)}</dd>' for t, d in rows)
        return f'<div class="terms"><div class="th">📘 ტერმინები</div><dl>{dl}</dl></div>'
    if kind in ('note', 'warn', 'tip'):
        ico = {'note': '💡', 'warn': '⚠️', 'tip': '👉'}[kind]
        return f'<div class="callout {kind}"><span class="ci">{ico}</span><div>{markdown.markdown(body, extensions=["sane_lists"])}</div></div>'
    lang = kind or 'plain'
    arg = arg.rstrip('!').strip()   # '!' only marks the block shown on the homework-review slide
    title = esc(arg) if arg else esc(lang)
    return (f'<div class="codebox"><div class="ch"><span>{title}</span><button class="copy" type="button">კოპირება</button></div>'
            f'<pre class="code"><code>{highlight(body, lang)}</code></pre></div>')

FENCE = re.compile(r'^```(\w*)[ \t]*([^\n]*)\n(.*?)^```[ \t]*$', re.M | re.S)

def md(text):
    lines = text.strip('\n').split('\n')
    ind = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    text = '\n'.join(l[ind:] for l in lines)
    blocks = []
    def keep(m):
        blocks.append(render_fence(m.group(1), m.group(2).strip(), m.group(3)))
        return f'\n\n@@B{len(blocks) - 1}@@\n\n'
    text = FENCE.sub(keep, text)
    h = markdown.markdown(text, extensions=['tables', 'sane_lists'])
    return re.sub(r'<p>@@B(\d+)@@</p>|@@B(\d+)@@', lambda m: blocks[int(m.group(1) or m.group(2))], h)

def md_doc(path):
    """# სათაური / შესავალი / ## სექციები → {'title', 'intro', 'parts': [(heading, md)]}"""
    if not path.exists():
        return None
    t = path.read_text()
    title = re.search(r'^# (.+)$', t, re.M).group(1).strip()
    t = re.sub(r'^# .+\n', '', t, count=1, flags=re.M)
    chunks = re.split(r'^## (.+)$', t, flags=re.M)
    return {'title': title, 'intro': chunks[0].strip(), 'parts': [(chunks[i].strip(), chunks[i + 1].strip()) for i in range(1, len(chunks), 2)]}

def part(doc, key):
    return next((b for h, b in doc['parts'] if key in h), '')

def slide_md(text):   # markdown → slide markup (deck classes)
    h = markdown.markdown(text, extensions=['sane_lists']).replace('<code>', '<code class="i">')
    return h.replace('<ul>', '<ul class="clean small">').replace('<ol>', '<ol class="clean small">')

def first_code(text):   # the code fence marked with a trailing "!" in its title, else the first code fence
    fences = [m for m in FENCE.finditer(text) if m.group(1) not in ('prompt', 'check', 'terms', 'note', 'warn', 'tip')]
    m = next((f for f in fences if f.group(2).strip().endswith('!')), fences[0] if fences else None)
    return (m.group(1), m.group(2).strip().rstrip('!').strip(), m.group(3)) if m else None

# ---------- generated slides ----------
def qa_rows(review):
    return ''.join(f'<div class="qa"><span class="n">{n}</span><span class="q">{md_inline(r["q"]).replace("<code>", "<code class=\"i\">")}</span>'
                   f'<span class="a step">{md_inline(r["a"]).replace("<code>", "<code class=\"i\">")}</span></div>' for n, r in enumerate(review, 1))

def check_md(review):
    return '```check\n' + '\n'.join(f'? {r["q"]}\n= {r["a"]}' for r in review) + '\n```'

def gen_review(prev):
    pm, num = prev['meta'], prev['num']
    return f'''<section class="slide" data-section="გამეორება">
  <div class="kicker">გამეორება · ლექცია {num}</div>
  <h2>გავიხსენოთ: <span class="grad">{esc(pm["title"])}</span></h2>
  {qa_rows(pm["review"])}
  <aside class="study">
## გავიხსენოთ წინა ლექცია

ლექცია {num} — **{esc(pm["title"])}**. ახალ თემამდე ვამოწმებთ, რა დაგვამახსოვრდა. ჯერ თვითონ უპასუხე, მერე გახსენი პასუხი. თუ რომელიმე გაგიჭირდა, [წინა ლექციის კონსპექტს]({prev["href"]}study.html) გადახედე.

{check_md(pm["review"])}
  </aside>
</section>'''

def gen_homework_review(prev):
    hw = prev['homework']
    sol = part(hw, 'ამოხსნ')
    code = first_code(sol)
    if code and code[2].strip('\n').count('\n') >= 20:
        print(f'  ⚠ ლექცია {prev["num"]}-ის ამოხსნის კოდი სლაიდზე {code[2].strip(chr(10)).count(chr(10)) + 1} ხაზია — ≤20 ჯობია (მონიშნე სხვა ბლოკი "!"-ით)')
    right = (f'<code-block lang="{code[0]}" cls="sm" title="{esc(code[1])}">\n{code[2]}</code-block>' if code else '')   # code-block escapes itself
    return f'''<section class="slide" data-section="საშინაოს განხილვა">
  <div class="kicker">🏠 საშინაოს განხილვა · ლექცია {prev["num"]}</div>
  <h2>{esc(hw["title"])}</h2>
  <div class="grid2" style="grid-template-columns:1fr 1.25fr;align-items:start;gap:30px">
    <div class="card accent" style="--a:var(--mvc)"><h3><span class="ico">📝</span>რა უნდა გაგეკეთებინათ</h3>{slide_md(part(hw, "მოთხოვნ"))}</div>
    <div class="step">{right}</div>
  </div>
  <div class="callout step mt" data-with style="--a:var(--api)">შეადარეთ თქვენს კოდს. რა გამოგივიდათ სხვანაირად — და რატომ?</div>
  <aside class="study">
## საშინაოს განხილვა

წინა ლექციის საშინაო: **{esc(hw["title"])}**. ქვემოთ არის ერთ-ერთი სწორი ამოხსნა. შენი კოდი შეიძლება სხვანაირად იყოს დაწერილი — მთავარია, მოთხოვნები სრულდებოდეს.

### მოთხოვნები
{part(hw, "მოთხოვნ")}

### ამოხსნა
{sol}
  </aside>
</section>'''

def gen_intro(meta):
    outs = ''.join(f'<li>{md_inline(o).replace("<code>", "<code class=\"i\">")}</li>' for o in meta['outcomes'])
    return f'''<section class="slide" data-section="დღის თემა">
  <div class="kicker">დღის თემა</div>
  <h2><span class="grad">{esc(meta["title"])}</span></h2>
  <div class="grid2" style="grid-template-columns:1fr 1fr;align-items:start;gap:40px">
    <div class="card accent" style="--a:var(--asp)"><h3><span class="ico">🤔</span>რატომ გჭირდებათ</h3><p class="small">{md_inline(meta["why"]).replace("<code>", "<code class=\"i\">")}</p></div>
    <div class="card accent" style="--a:var(--mvc)"><h3><span class="ico">🎯</span>ლექციის ბოლოს შეძლებთ</h3><ul class="clean small">{outs}</ul></div>
  </div>
  <aside class="study">
## დღის თემა: {esc(meta["title"])}

{meta["why"]}

**ლექციის ბოლოს შეძლებ:**

{chr(10).join("- " + o for o in meta["outcomes"])}
  </aside>
</section>'''

def gen_task(doc, section, kicker, ico, color, footer, study_head):
    bonus = part(doc, 'ბონუს')
    done = part(doc, 'მზადაა')
    steps = part(doc, 'ნაბიჯ') or part(doc, 'მოთხოვნ')
    right = f'<div class="card accent" style="--a:var(--asp)"><h3><span class="ico">⭐</span>ბონუსი</h3>{slide_md(bonus)}</div>' if bonus else ''
    cols = '1.5fr 1fr' if bonus else '1fr'
    study_parts = '\n\n'.join(f'### {h}\n\n{b}' for h, b in doc['parts'] if 'ამოხსნ' not in h)
    return f'''<section class="slide" data-section="{section}">
  <div class="kicker">{kicker}</div>
  <h2>{esc(doc["title"])}</h2>
  <div class="grid2" style="grid-template-columns:{cols};align-items:start">
    <div class="card accent" style="--a:{color}">
      <h3><span class="ico">{ico}</span>{md_inline(doc["intro"]).replace("<code>", "<code class=\"i\">") if doc["intro"] else "დავალება"}</h3>
      {slide_md(steps)}
      {f'<p class="tiny" style="margin-top:14px">✓ მზადაა, როცა: {md_inline(done)}</p>' if done else ''}
    </div>
    {right}
  </div>
  <div class="callout mt" style="--a:var(--api)">{footer}</div>
  <aside class="study">
## {study_head}: {esc(doc["title"])}

{doc["intro"]}

{study_parts}
  </aside>
</section>'''

def gen_check(meta):
    return f'''<section class="slide" data-section="შეჯამება">
  <div class="kicker">შევამოწმოთ</div>
  <h2>{len(meta["review"])} კითხვა</h2>
  {qa_rows(meta["review"])}
  <aside class="study">
## შეამოწმე, რა დაგამახსოვრდა

ეს კითხვები შემდეგი ლექციის დასაწყისშიც დაისმება.

{check_md(meta["review"])}
  </aside>
</section>'''

def expand(src, meta, ldir, prev):
    gen = {
        'lecture-review': lambda: gen_review(prev) if prev and prev['meta'].get('review') else None,
        'lecture-homework-review': lambda: gen_homework_review(prev) if prev and prev['homework'] else None,
        'lecture-intro': lambda: gen_intro(meta),
        'lecture-classwork': lambda: gen_task(md_doc(ldir / 'classwork.md'), 'პრაქტიკა', '🧑‍💻 თქვენ აკეთებთ · კლასში', '📝', 'var(--mvc)',
                                              'წესი: <b>ჯერ ცდი თვითონ</b> → გვერდით მჯდომს ჰკითხე → მერე მე', 'კლასში დავალება'),
        'lecture-check': lambda: gen_check(meta),
        'lecture-homework': lambda: gen_task(md_doc(ldir / 'homework.md'), 'საშინაო', '🏠 საშინაო დავალება', '🏠', 'var(--net)',
                                             'შემდეგი ლექციის დასაწყისში ამ დავალებას <b>ერთად განვიხილავთ</b>', 'საშინაო დავალება'),
    }
    problems = []
    if '<lecture-intro/>' in src:   # new-format lecture: every part is required
        need = ['lecture-intro', 'lecture-classwork', 'lecture-check', 'lecture-homework']
        if prev and prev['meta'].get('review'): need.append('lecture-review')
        if prev and prev['homework']: need.append('lecture-homework-review')
        problems += [f'<{n}/> აკლია' for n in need if f'<{n}/>' not in src]
        for f in ('classwork.md', 'homework.md'):
            if not (ldir / f).exists(): problems.append(f'{f} აკლია')
        for k in ('why', 'outcomes', 'review'):
            if not meta.get(k): problems.append(f'lecture.json: "{k}" აკლია')
        if problems:
            return src, problems
    for tag, fn in gen.items():
        if f'<{tag}/>' in src:
            out = fn()
            src = src.replace(f'<{tag}/>', out or '')
    return src, problems

# ---------- one lecture ----------
HOME_CSS = '''#home{position:fixed;left:12px;top:10px;z-index:41;font:600 13px var(--mono);color:var(--muted);text-decoration:none;
padding:6px 10px;border-radius:8px;opacity:0;transition:opacity .25s}
#home:hover,#home:focus-visible{opacity:1;background:rgba(0,0,0,.05)}
:fullscreen #home{display:none}
#studybtn{position:fixed;right:16px;top:12px;z-index:41;display:flex;align-items:center;gap:6px;font:700 14px var(--font);color:#fff;
background:var(--net);border:0;border-radius:10px;padding:7px 13px;cursor:pointer;opacity:.9;box-shadow:0 4px 14px rgba(109,40,217,.25)}
#studybtn:hover{opacity:1}#studybtn kbd{font:600 11px var(--mono);background:rgba(255,255,255,.22);border-radius:5px;padding:1px 6px}
body[data-study] #help{right:250px}
#lectbtn{position:fixed;right:170px;top:12px;z-index:41;display:flex;align-items:center;gap:6px;font:700 14px var(--font);color:var(--ink2);
background:#fff;border:1px solid var(--line2);border-radius:10px;padding:7px 11px;cursor:pointer;opacity:.85}
#lectbtn:hover{opacity:1}#lectbtn kbd{font:600 11px var(--mono);background:var(--bg2);border-radius:5px;padding:1px 6px}'''

def heading(sl):
    h = re.search(r'<h[12][^>]*>(.*?)</h[12]>', sl, re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h.group(1)))).strip() if h else ''

def build_lecture(course, cdir, ldir, meta, prev):
    src, problems = expand((ldir / 'deck.html').read_text(), meta, ldir, prev)
    num = int(ldir.name.split('-', 1)[0])
    title = f'{course["title"]} · {num} — {meta["title"]}'   # also the BroadcastChannel key: must be unique
    out = OUT / cdir.name / ldir.name
    if problems:
        print(f'  {cdir.name}/{ldir.name}: ⚠ ' + '; '.join(problems))
        return None, problems

    slides = re.findall(r'<section class="slide.*?</section>', src, re.S)
    study = []
    for i, sl in enumerate(slides, 1):
        m = re.search(r'<aside class="study">(.*?)</aside>', sl, re.S)
        sec = re.search(r'data-section="([^"]*)"', sl)
        study.append({'n': i, 'title': heading(sl), 'section': sec.group(1) if sec else '', 'html': md(m.group(1)) if m else None, 'raw': m.group(1) if m else ''})
        clean = re.sub(r'<aside class="(?:study|notes)">.*?</aside>', '', sl, flags=re.S)
        src = src.replace(sl, clean, 1)
    src = re.sub(r'<aside class="notes">.*?</aside>', '', src, flags=re.S)   # old lecturer notes are never published
    for a, b in LIGHT_MAP:
        src = src.replace(a, b).replace(a.upper(), b)
    src = re.sub(r'<code-block([^>]*)>(.*?)</code-block>', code_block, src, flags=re.S)
    has_study = any(s['html'] for s in study)

    out.mkdir(parents=True, exist_ok=True)
    write_page(out / 'index.html', f'''<!doctype html>
<html lang="ka"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
{FONTS}
<style>{CSS}
{HOME_CSS}</style></head>
<body{' data-study="1"' if has_study else ''}>
<a id="home" href="../../" title="ყველა ლექცია">← ლექციები</a>{'<button id="studybtn" type="button" title="კონსპექტი ცალკე ჩანართში — სლაიდებს მიჰყვება">📖 კონსპექტი <kbd>P</kbd></button>' if has_study else ''}{'<button id="lectbtn" type="button" title="ლექტორის გვერდი — გეგმა, კითხვები, ამოხსნები">🎓 <kbd>L</kbd></button>' if (ldir / 'lecturer.md').exists() else ''}
<div id="stage"><div id="deck">
{src}
<div id="hud"><span class="sec"></span><span class="dots"></span><span class="num"></span></div><div id="bar"></div>
</div></div>
<div id="overview"></div>
<div id="help">← → · F</div>
<script>{JS}</script>
</body></html>''')
    for stale in ('script.html', 'study.html', 'lecturer.html'):
        (out / stale).unlink(missing_ok=True)

    materials = []
    if (ldir / 'materials').is_dir():
        shutil.copytree(ldir / 'materials', out / 'materials', dirs_exist_ok=True)
        materials = sorted(p.name for p in (ldir / 'materials').iterdir() if p.is_file())
    if has_study:
        write_study(out, course, meta, num, title, study, materials, ldir, len(slides))
    has_lecturer = write_lecturer(out, course, meta, num, title, ldir)
    print(f'  {cdir.name}/{ldir.name}: {len(slides)} slides' + (f', study {sum(1 for s in study if s["html"])} blocks' if has_study else ''))
    return {'num': num, 'slug': ldir.name, 'title': meta['title'], 'slides': len(slides), 'materials': materials, 'study': has_study,
            'classwork': (ldir / 'classwork.md').exists(), 'homework': (ldir / 'homework.md').exists(), 'quiz': len(meta.get('quiz', [])), 'lecturer': has_lecturer}, []

# ლექტორის გვერდი. lecturer.md:
#   ## სათაური                       ზოგადი ნაწილი (მიმოხილვა, ადგილი მოდულში, შეფასება…)
#   ## 3 · ტოკენები · 15 წთ · 16–20   თემა: ნომერი · სათაური · დრო · სლაიდები (დრო → ლექციის მსვლელობაში ჩადის)
#   ### 🎯 მთავარი სათქმელი           ბლოკი; ტიპს emoji წყვეტს (LECT_KINDS). ### 📋 ლექციაზე = შპარგალკა
# lecture.json → "lecturer_quiz": [{"q", "options", "answer", "explain"}] — „✅ მზად ხარ?“
LECT_KINDS = {'🎯': 'main', '🧠': 'deep', '🗣': 'how', '🙋': 'ask', '⚠': 'myth', '💡': 'ex', '❓': 'faq', '💻': 'code',
              '📋': 'cheat', '✅': 'prep', '📌': 'must', '✂': 'cut', '⬅': 'prev', '➡': 'next', '🚫': 'no', '🏁': 'wrap',
              '📏': 'rubric', '🔁': 'next'}

def lect_kind(h):
    h = h.replace('️', '')
    return next((v for k, v in LECT_KINDS.items() if h.startswith(k)), 'plain')

def lect_heading(h):
    """'3 · ტოკენები · 15 წთ · 16–20' → (num, title, minutes, (from, to))"""
    num, mins, slides, rest = None, None, None, []
    for i, x in enumerate(p.strip() for p in h.split(' · ')):
        if i == 0 and x.isdigit(): num = int(x)
        elif re.fullmatch(r'(\d+) წთ', x): mins = int(x.split()[0])
        elif re.fullmatch(r'\d+(?:[–-]\d+)?', x):
            a, _, b = x.replace('–', '-').partition('-'); slides = (int(a), int(b or a))
        else: rest.append(x)
    return num, ' · '.join(rest), mins, slides

def lect_split(text):
    """### ბლოკებად: [(None, intro), (heading, body), …]"""
    ch = re.split(r'^### (.+)$', text, flags=re.M)
    return [(None, ch[0])] + [(ch[i].strip(), ch[i + 1]) for i in range(1, len(ch), 2)]

def render_lecturer_quiz(quiz):
    items = []
    for n, x in enumerate(quiz, 1):
        opts = ''.join(f'<button type="button" class="opt" data-i="{i}">{md_inline(o)}</button>' for i, o in enumerate(x['options']))
        items.append(f'<div class="qq" data-answer="{x["answer"]}"><div class="qt"><span class="qn">{n}</span><div>{md_inline(x["q"])}</div></div>'
                     f'<div class="opts">{opts}</div><div class="qe"><span class="verdict"></span> {md_inline(x.get("explain", ""))}</div></div>')
    return (f'<div class="qscore"><span id="qs">0</span> / {len(quiz)} სწორი · <span id="qd">0</span> / {len(quiz)} პასუხი'
            f'<button type="button" class="btn qreset">თავიდან</button></div>{"".join(items)}<div class="qsum" id="qsum"></div>')

def write_lecturer(out, course, meta, num, deck_title, ldir):
    """lecturer.md (+ დავალებები, კითხვები, ტესტის პასუხები, „მზად ხარ?“) → lecturer.html, ცალკე კოდით"""
    src = ldir / 'lecturer.md'
    code = lecturer_code()
    if not src.exists():
        return False
    if not code:
        print('  ⚠ ლექტორის გვერდი არ აიწყო: .lecturer-code ფაილი ან LECTURER_CODE ცვლადი არ არის')
        return False
    t = re.sub(r'^# .+\n', '', src.read_text(), count=1, flags=re.M)
    chunks = re.split(r'^## (.+)$', t, flags=re.M)
    intro = chunks[0].strip()
    parts = []   # {id, num, title, mins, slides, group, html}
    for i in range(1, len(chunks), 2):
        n, title, mins, slides = lect_heading(chunks[i].strip())
        subs = []
        for h, b in lect_split(chunks[i + 1]):
            if not b.strip(): continue
            if h is None:
                subs.append(f'<div class="pintro">{md(b)}</div>')
            else:
                k = lect_kind(h)
                subs.append(f'<div class="sub k-{k}"><div class="sl">{esc(h)}</div><div class="sb">{md(b)}</div></div>')
        parts.append({'num': n, 'title': title, 'mins': mins, 'slides': slides, 'html': ''.join(subs)})
    timed = [i for i, p in enumerate(parts) if p['mins']]
    first, last = (timed[0], timed[-1]) if timed else (len(parts), -1)
    for i, p in enumerate(parts):
        p['group'] = 'prep' if i < first else 'flow' if i <= last else 'after'
    # ავტომატური მასალა — დავალებების სრული ტექსტი, კითხვები, პასუხები
    def doc_md(path):
        return re.sub(r'^# (.+)$', r'### \1', path.read_text(), count=1, flags=re.M).replace('\n## ', '\n#### ')
    mat = []
    if (ldir / 'classwork.md').exists(): mat.append(('📝 კლასის დავალება — სრული ტექსტი', doc_md(ldir / 'classwork.md')))
    if (ldir / 'homework.md').exists(): mat.append(('🏠 საშინაო — სრული ტექსტი და ამოხსნა', doc_md(ldir / 'homework.md')))
    if meta.get('review'): mat.append(('❓ შემოწმების კითხვები — პასუხებით', check_md(meta['review'])))
    if meta.get('quiz'):
        mat.append(('✅ სტუდენტის ტესტი — სწორი პასუხები', 'კონსპექტის ბოლოს სტუდენტი ამ კითხვებს თვითონ პასუხობს.\n\n' +
                    '\n'.join(f'{n}. {x["q"]} → **{x["options"][x["answer"]]}**' for n, x in enumerate(meta['quiz'], 1))))
    for h, b in mat:
        parts.append({'num': None, 'title': h, 'mins': None, 'slides': None, 'group': 'mat', 'html': f'<div class="sb">{md(b)}</div>'})
    if meta.get('lecturer_quiz'):
        parts.append({'num': None, 'title': '✅ მზად ხარ?', 'mins': None, 'slides': None, 'group': 'ready',
                      'html': '<div class="pintro"><p>ეს კითხვები შენთვისაა. თუ ყველას ზუსტად უპასუხე და ახსნაც გეთანხმება, ლექციისთვის მზად ხარ. '
                              'შეცდომის შემთხვევაში ახსნას წაიკითხე და შესაბამისი თემა გადახედე.</p></div>' + render_lecturer_quiz(meta['lecturer_quiz'])})
    groups = {'prep': ('📚', 'მომზადება'), 'flow': ('🎬', 'ლექციის მსვლელობა'), 'after': ('🏠', 'ლექციის შემდეგ'),
              'mat': ('📎', 'მასალა: დავალებები და პასუხები'), 'ready': ('✅', 'მზად ხარ?')}
    # დრო: დაწყების წუთები
    clock = 0
    for p in parts:
        if p['mins']:
            p['start'] = clock; clock += p['mins']
    total = clock
    fmt = lambda m: f'{m // 60}:{m % 60:02d}'
    nav, body, tl, cur = [], [], [], None
    for i, p in enumerate(parts, 1):
        pid = f'p-{i}'
        if p['group'] != cur:
            cur = p['group']
            ico, name = groups[cur]
            nav.append(f'<div class="ng" data-g="{cur}">{ico} {esc(name)}</div>')
            body.append(f'<div class="grp" data-g="{cur}"><span>{ico}</span>{esc(name)}</div>')
        badge, title = str(p['num']) if p['num'] else '', p['title']
        em = re.match(r'^([^\w\s]+)\s+(.+)$', title)
        if not badge and em:   # „☕ შესვენება“ → ☕ ბეჯში, სათაური emoji-ს გარეშე
            badge, title = em.group(1), em.group(2)
        p['title'] = title
        meta_bits = []
        if p['mins']:
            meta_bits.append(f'<span class="pt">⏱ {p["mins"]} წთ · {fmt(p["start"])}–{fmt(p["start"] + p["mins"])}</span>')
        if p['slides']:
            a, b = p['slides']
            meta_bits.append(f'<a class="ps" href="index.html#/{a}" target="_blank" data-go="{a}">▶ სლაიდ{"ები " + str(a) + "–" + str(b) if b != a else "ი " + str(a)}</a>')
        done = '<button type="button" class="done" title="მონიშნე, როცა ამ ნაწილს მოემზადები">☐ მომზადებული ვარ</button>' if p['group'] in ('prep', 'flow', 'after') else ''
        attrs = f' data-g="{p["group"]}"' + (f' data-start="{p["start"]}" data-min="{p["mins"]}"' if p['mins'] else '') + \
                (f' data-from="{p["slides"][0]}" data-to="{p["slides"][1]}"' if p['slides'] else '') + (' data-cheat' if 'k-cheat' in p['html'] else '')
        fold = p['group'] == 'mat'
        head = (f'<header class="ph"><span class="pn{"" if p["num"] else " e"}">{badge or "•"}</span><div class="pht"><h2>{esc(p["title"])}</h2>'
                f'<div class="pm">{"".join(meta_bits)}</div></div>{done}</header>')
        if fold:
            body.append(f'<section class="part" id="{pid}"{attrs}><details><summary>{head}</summary><div class="pbody">{p["html"]}</div></details></section>')
        else:
            body.append(f'<section class="part" id="{pid}"{attrs}>{head}<div class="pbody">{p["html"]}</div></section>')
        nav.append(f'<a href="#{pid}" data-g="{p["group"]}"><span class="nn{"" if p["num"] else " e"}">{badge or "·"}</span><span class="nt">{esc(p["title"])}</span>'
                   f'{"<span class=nm>" + str(p["mins"]) + "′</span>" if p["mins"] else ""}</a>')
        if p['mins']:
            short = title.split(':')[0]
            tl.append(f'<a class="seg{" brk" if not p["num"] else ""}" href="#{pid}" style="flex:{p["mins"]}" data-start="{p["start"]}" data-min="{p["mins"]}" '
                      f'title="{esc(p["title"])} · {p["mins"]} წთ"><b>{badge}</b><span>{esc(short)}</span><i>{p["mins"]}′</i></a>')
    timeline = (f'<div class="tl"><div class="tlh"><b>ლექციის გეგმა</b><span>{total} წთ</span></div><div class="segs">{"".join(tl)}<div class="cursor" id="cursor"></div></div></div>'
                if tl else '')
    page = (ENGINE / 'lecturer.html').read_text()
    for k, v in {'{{TITLE}}': esc(meta['title']), '{{COURSE}}': esc(course['title']), '{{NUM}}': str(num),
                 '{{DECK_TITLE_JSON}}': json.dumps(deck_title, ensure_ascii=False), '{{NAV}}': ''.join(nav), '{{BODY}}': '\n'.join(body),
                 '{{INTRO}}': md_inline(intro) if intro else '', '{{TIMELINE}}': timeline, '{{TOTAL}}': str(total),
                 '{{TOKEN_CSS}}': TOKEN_CSS, '{{FONTS}}': FONTS}.items():
        page = page.replace(k, v)
    write_locked(out / 'lecturer.html', page, code, 'lectures:lecturer', 'ლექტორის გვერდი')
    return True

def render_resources(meta, ldir, materials, n_slides, n_quiz):
    """კონსპექტის თავში: გარე ბმულები და მასალები (დავალებებს და ტესტს „5 წუთში“ აჩვენებს)"""
    files = ''.join(f'<a class="rf" href="materials/{esc(m)}" download>📎 {esc(m)}</a>' for m in materials)
    links = ''.join(f'<li><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a>'
                    f'{" — " + md_inline(r["note"]) if r.get("note") else ""}</li>' for r in meta.get('resources', []))
    if not files and not links:
        return ''
    return (f'<section class="res" id="resources"><h3>🔗 სასარგებლო ბმულები</h3>'
            + (f'<ul class="rlinks">{links}</ul>' if links else '')
            + (f'<div class="rfiles">{files}</div>' if files else '') + '</section>')

def render_quiz_items(quiz):
    """lecture.json → quiz: [{"q", "options": [...], "answer": index, "explain", "slide"?}] → ინტერაქტიული ტესტი"""
    items = []
    for n, x in enumerate(quiz, 1):
        opts = ''.join(f'<button type="button" class="opt" data-i="{i}">{md_inline(o)}</button>' for i, o in enumerate(x['options']))
        back = f' <a class="chip" href="#s-{x["slide"]}">გაიმეორე · სლაიდი {x["slide"]}</a>' if x.get('slide') else ''
        items.append(f'<div class="qq" data-answer="{x["answer"]}"><div class="qt"><span class="qn">{n}</span><div>{md_inline(x["q"])}</div></div>'
                     f'<div class="opts">{opts}</div><div class="qe"><span class="verdict"></span> {md_inline(x.get("explain", ""))}{back}</div></div>')
    return (f'<div class="qscore"><span id="qs">0</span> / {len(quiz)} სწორი · <span id="qd">0</span> / {len(quiz)} პასუხი'
            f'<button type="button" class="btn qreset">თავიდან</button></div>{"".join(items)}<div class="qsum" id="qsum"></div>')

# კონსპექტი თავებად. lecture.json → "study" (არააუცილებელი):
#   "summary":  ["…"]                     „⚡ 5 წუთში“ — მთავარი აზრები (თუ არ არის — outcomes)
#   "skip":     ["დღის თემა", …]           data-section-ები, რომლებიც მხოლოდ ლექციისთვისაა
#   "chapters": {"<data-section>": {"title", "goal", "icon"}}
STUDY_ICONS = {'მოდული': '🧭', 'პრაქტიკა': '✍️', 'შეჯამება': '🏁', 'საშინაო': '🏠'}

def read_minutes(text):
    return max(1, round(len(re.findall(r'\w+', re.sub(r'```.*?```', '', text, flags=re.S))) / 130))

def glossary(raws):
    seen, rows = set(), []
    for raw in raws:
        for m in FENCE.finditer(raw):
            if m.group(1) != 'terms': continue
            for line in m.group(3).split('\n'):
                if '—' not in line: continue
                t, d = (x.strip() for x in line.split('—', 1))
                if t.lower() not in seen:
                    seen.add(t.lower()); rows.append((t, d))
    return rows

def write_study(out, course, meta, num, deck_title, study, materials, ldir, n_slides):
    cfg = meta.get('study', {})
    skip = set(cfg.get('skip', []))
    blocks, pending = [], []   # [{slides, title, section, html, raw}] — სლაიდები ტექსტის გარეშე წინა ბლოკს მიჰყვება
    for s in study:
        if s['html']:
            title, body = s['title'], s['html']
            m = re.match(r'\s*<h([23])>(.*?)</h\1>', body, re.S)   # study text's own heading wins over the slide title
            if m:
                title, body = html.unescape(re.sub(r'<[^>]+>', '', m.group(2))), body[m.end():]
            blocks.append({'slides': pending + [s['n']], 'title': title, 'section': s['section'], 'html': body, 'raw': s['raw']}); pending = []
        elif blocks:
            blocks[-1]['slides'].append(s['n'])
        else:
            pending.append(s['n'])
    chapters = []
    for b in blocks:
        if b['section'] in skip: continue
        if not chapters or chapters[-1]['section'] != b['section']:
            chapters.append({'section': b['section'], 'blocks': []})
        chapters[-1]['blocks'].append(b)
    body, nav, total = [], [], 0
    for n, c in enumerate(chapters, 1):
        sec = c['section']; info = cfg.get('chapters', {}).get(sec, {})
        mnum = re.match(r'^(\d+)\s*·\s*(.+)$', sec)
        badge = mnum.group(1) if mnum else info.get('icon', STUDY_ICONS.get(sec, '•'))
        title = info.get('title') or (mnum.group(2) if mnum else sec)
        mins = read_minutes(''.join(b['raw'] for b in c['blocks'])); total += mins
        cid = f'c-{n}'
        anchors = ''.join(f'<span class="anchor" id="{a}"></span>' for k, a in (('პრაქტიკა', 'classwork'), ('საშინაო', 'homework')) if sec == k)
        arts = []
        for b in c['blocks']:
            first = b['slides'][0]
            sl = ''.join(f'<span class="anchor" id="s-{x}"></span>' for x in b['slides'])
            kind = ' check' if 'შეამოწმე' in b['title'] else ' lead' if b['title'].startswith('ნაწილი') else ''   # „ნაწილი N“ = თავის შესავალი
            arts.append(f'<article class="blk{kind}" data-slides="{",".join(map(str, b["slides"]))}">{sl}'
                        f'<div class="bh"><h3>{esc(b["title"])}</h3><a class="chip" href="index.html#/{first}" data-go="{first}" target="_blank" title="ეს ნაწილი პრეზენტაციაში">სლაიდი {first}</a></div>'
                        f'{b["html"]}</article>')
        goal = f'<p class="goal">🎯 <b>ამის შემდეგ:</b> {md_inline(info["goal"])}</p>' if info.get('goal') else ''
        body.append(f'<section class="chap" id="{cid}" data-num="{1 if mnum else 0}">{anchors}<header class="chh"><span class="cn{"" if mnum else " e"}">{badge}</span>'
                    f'<div class="cht"><div class="ck">{"თავი " + mnum.group(1) + " · " if mnum else ""}~{mins} წთ კითხვა</div><h2>{esc(title)}</h2>{goal}</div>'
                    f'<button type="button" class="read">☐ წავიკითხე</button></header><div class="cbody">{"".join(arts)}</div></section>')
        nav.append(f'<a href="#{cid}"><span class="nn{"" if mnum else " e"}">{badge}</span><span class="nt">{esc(title)}</span><span class="nm">{mins}′</span></a>')
    quiz = meta.get('quiz', [])
    terms = glossary(b['raw'] for b in blocks)
    extra = ''
    if quiz:
        nav.append('<a href="#quiz" class="x"><span class="nn e">✅</span><span class="nt">შეამოწმე ცოდნა</span><span class="nm">' + str(len(quiz)) + '</span></a>')
        extra += f'<section class="chap fin" id="quiz-wrap"><header class="chh"><span class="cn e">✅</span><div class="cht"><div class="ck">ტესტი · ქულით</div><h2 id="quiz">შეამოწმე ცოდნა</h2>' \
                 f'<p class="goal">აირჩიე პასუხი — მაშინვე ნახავ, სწორია თუ არა და რატომ. ბოლოს გეცოდინება, რა გაიმეორო.</p></div></header><div class="cbody">{render_quiz_items(quiz)}</div></section>'
    if terms:
        nav.append('<a href="#glossary" class="x"><span class="nn e">📘</span><span class="nt">ტერმინები</span><span class="nm">' + str(len(terms)) + '</span></a>')
        dl = ''.join(f'<dt>{md_inline(t)}</dt><dd>{md_inline(d)}</dd>' for t, d in terms)
        extra += f'<section class="chap fin" id="glossary"><header class="chh"><span class="cn e">📘</span><div class="cht"><div class="ck">ლექციის ყველა ტერმინი</div><h2>ტერმინები</h2></div></header><div class="cbody"><div class="terms"><dl>{dl}</dl></div></div></section>'
    # ⚡ 5 წუთში
    summary = cfg.get('summary') or meta.get('outcomes', [])
    ch_num = [c for c in chapters if re.match(r'^\d', c['section'])]
    path = [f'<li><a href="#c-1">წაიკითხე თავები</a> — სულ ~{total} წთ. ყოველი თავის ბოლოს არის „შეამოწმე თავი“</li>']
    if quiz: path.append(f'<li><a href="#quiz">გაიარე ტესტი</a> — {len(quiz)} კითხვა, ქულით</li>')
    if (ldir / 'classwork.md').exists(): path.append('<li><a href="#classwork">გააკეთე კლასის დავალება</a> სახლში</li>')
    if (ldir / 'homework.md').exists(): path.append('<li><a href="#homework">საშინაო დავალება</a> — შემდეგ ლექციაზე განვიხილავთ</li>')
    quick = (f'<section class="quick"><div class="qk"><h2>⚡ 5 წუთში</h2><p class="qs">თუ მხოლოდ ეს დაგამახსოვრდა, ლექციის მთავარი იცი:</p>'
             f'<ol class="take">{"".join(f"<li>{md_inline(x)}</li>" for x in summary)}</ol></div>'
             f'<div class="qp"><h3>📍 ლექცია გააცდინე?</h3><ol class="path">{"".join(path)}</ol></div></section>')
    resources = render_resources(meta, ldir, materials, n_slides, len(quiz))
    page = (ENGINE / 'study.html').read_text()
    mats = ''.join(f'<a href="materials/{esc(m)}" download>📎 {esc(m)}</a>' for m in materials)
    for k, v in {'{{TITLE}}': esc(meta['title']), '{{COURSE}}': esc(course['title']), '{{NUM}}': str(num), '{{TOTAL}}': str(total),
                 '{{DECK_TITLE_JSON}}': json.dumps(deck_title, ensure_ascii=False), '{{NAV}}': ''.join(nav), '{{QUICK}}': quick,
                 '{{BODY}}': '\n'.join(body) + extra, '{{RESOURCES}}': resources, '{{MATERIALS}}': mats, '{{TOKEN_CSS}}': TOKEN_CSS, '{{FONTS}}': FONTS}.items():
        page = page.replace(k, v)
    write_page(out / 'study.html', page)

# ---------- everything ----------
def main(filters):
    OUT.mkdir(parents=True, exist_ok=True)
    marker = OUT / GENERATED
    if not filters and marker.exists():
        for d in marker.read_text().split():
            if (OUT / d).is_dir() and d not in ('courses', 'engine', '.git', '.github'):
                shutil.rmtree(OUT / d)
    if (ENGINE / 'assets').is_dir():   # საერთო ფაილები (თუ არის) → /assets/
        shutil.copytree(ENGINE / 'assets', OUT / 'assets', dirs_exist_ok=True)
    catalog, problems = [], []
    for cdir in sorted((ROOT / 'courses').iterdir()):
        if not (cdir / 'course.json').exists():
            continue
        course = json.loads((cdir / 'course.json').read_text())
        lectures, prev = [], None
        for ldir in sorted(p for p in cdir.iterdir() if (p / 'deck.html').exists()):
            meta = json.loads((ldir / 'lecture.json').read_text())
            if meta.get('starts_series'):   # e.g. a guest lecture for another group: no review of the previous lecture
                prev = None
            rel = f'{cdir.name}/{ldir.name}'
            if not filters or any(f in rel for f in filters):
                info, errs = build_lecture(course, cdir, ldir, meta, prev)
                problems += errs
                if info: lectures.append(info)
            prev = {'meta': meta, 'num': int(ldir.name.split('-', 1)[0]), 'homework': md_doc(ldir / 'homework.md'),
                    'href': f'../{ldir.name}/'}
        catalog.append({'slug': cdir.name, 'title': course['title'], 'order': course.get('order', 99), 'lectures': lectures})
    catalog.sort(key=lambda c: c['order'])
    if not filters:
        page = (ENGINE / 'index.html').read_text().replace('/*CATALOG*/[]', json.dumps(catalog, ensure_ascii=False))
        write_page(OUT / 'index.html', page)
        (OUT / '.nojekyll').write_text('')
        marker.write_text('\n'.join([c['slug'] for c in catalog] + ['assets']) + '\n')
        print(f'index: {sum(len(c["lectures"]) for c in catalog)} lectures in {len(catalog)} courses')
    if problems:
        sys.exit('⚠ ლექციის სტრუქტურა არასრულია — იხ. ზემოთ')

if __name__ == '__main__':
    main(sys.argv[1:])
