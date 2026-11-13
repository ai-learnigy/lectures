(() => {
  // the study window (P) follows the deck over this channel; title is unique per lecture
  let bc = null; try { bc = new BroadcastChannel('deck-' + document.title); } catch (e) {}
  const deck = document.getElementById('deck');
  const slides = [...deck.querySelectorAll('.slide')];
  const hud = { sec: document.querySelector('#hud .sec'), num: document.querySelector('#hud .num'), dots: document.querySelector('#hud .dots') };
  const bar = document.getElementById('bar');
  const ov = document.getElementById('overview');

  // ----- build step groups per slide -----
  const groups = slides.map(s => {
    const els = [...s.querySelectorAll('.step, .trigger, .codestep')].filter(e => !e.closest('.study'));
    const g = [];
    els.forEach(e => { if (e.hasAttribute('data-with') && g.length) g[g.length - 1].push(e); else g.push([e]); });
    return g;
  });
  // sections
  let curSec = '';
  const sections = slides.map(s => (curSec = s.dataset.section ?? curSec));

  // typing lengths
  document.querySelectorAll('.typing').forEach(t => { t.style.setProperty('--n', t.textContent.length); if (!t.style.getPropertyValue('--t')) t.style.setProperty('--t', Math.max(.6, t.textContent.length * .045) + 's'); });

  // svg draw lengths
  document.querySelectorAll('.draw path,.draw line,.draw polyline,path.draw,line.draw,.autodraw path,path.autodraw').forEach(p => {
    try { const L = Math.ceil(p.getTotalLength()) + 2; p.style.setProperty('--len', L); } catch (e) {}
  });

  let i = 0, k = 0;
  const parseHash = () => { const m = location.hash.match(/#\/?(\d+)(?:\.(\d+))?/); if (m) { i = Math.min(slides.length - 1, Math.max(0, +m[1] - 1)); k = Math.min(groups[i].length, +(m[2] || 0)); } };
  parseHash();

  function smil(root, filter) {
    root.querySelectorAll('animate,animateMotion,animateTransform,set').forEach(a => {
      if (filter(a)) { try { a.beginElement(); } catch (e) {} }
    });
  }
  function ranges(spec) {
    const out = new Set();
    String(spec).split(',').forEach(p => { const [a, b] = p.split('-').map(Number); for (let x = a; x <= (b || a); x++) out.add(x); });
    return out;
  }

  let prevI = -1, prevK = -1;
  function render(forward) {
    slides.forEach((s, x) => { s.classList.toggle('active', x === i); s.classList.toggle('past', x < i); });
    const s = slides[i];
    groups[i].forEach((g, x) => g.forEach(e => e.classList.toggle('shown', x < k)));
    // data-hide triggers: hide target element(s) once the trigger is shown
    s.querySelectorAll('[data-hide]').forEach(t => {
      s.querySelectorAll(t.dataset.hide).forEach(el => el.classList.toggle('gone', t.classList.contains('shown')));
    });
    // code highlights
    s.querySelectorAll('pre.code[id]').forEach(pre => {
      const steps = [...s.querySelectorAll(`.codestep[data-for="${pre.id}"]`)].filter(c => c.classList.contains('shown'));
      const last = steps[steps.length - 1];
      const lines = [...pre.querySelectorAll('.ln')];
      if (!last || last.dataset.lines === 'all') { lines.forEach(l => l.classList.remove('hl', 'dim')); return; }
      const set = ranges(last.dataset.lines);
      lines.forEach((l, n) => { const on = set.has(n + 1); l.classList.toggle('hl', on); l.classList.toggle('dim', !on); });
    });
    // animations
    if (i !== prevI) {
      smil(s, a => a.hasAttribute('data-auto'));
      // ინტერაქტიული ვიჯეტები სლაიდზე (ტოკენაიზერი, სლაიდერები…) — აქტიური სლაიდის შესახებ
      document.dispatchEvent(new CustomEvent('deck:slide', { detail: s }));
    }
    if (i === prevI && k > prevK) {
      for (let x = prevK; x < k; x++) groups[i][x].forEach(e => smil(e, a => !a.hasAttribute('data-auto')));
    } else if (i !== prevI && k > 0) {
      for (let x = 0; x < k; x++) groups[i][x].forEach(e => smil(e, a => !a.hasAttribute('data-auto')));
    }
    prevI = i; prevK = k;
    // hud
    hud.sec.textContent = sections[i] || '';
    hud.num.textContent = `${i + 1} / ${slides.length}`;
    const n = groups[i].length;
    hud.dots.innerHTML = n ? Array.from({ length: n }, (_, x) => x < k ? '<b>●</b>' : '○').join('') : '';
    bar.style.width = ((i + (n ? k / n : 1)) / slides.length * 100) + '%';
    history.replaceState(null, '', `#/${i + 1}${k ? '.' + k : ''}`);
    try { bc && bc.postMessage({ t: 'state', i, k }); } catch (e) {}
    [...ov.children].forEach((b, x) => b.classList.toggle('cur', x === i));
    fitSlide(s);
  }

  // სლაიდი ეკრანის სიმაღლეში თუ არ ეტევა (გრძელი ტექსტი, ფონტი, ბევრი ნაბიჯი) —
  // შიგთავსი პროპორციულად პატარავდება, რომ ქვედა ზოლამდე დაეტიოს. ყველა ეკრანზე ერთნაირად.
  function fitSlide(s) {
    if (!s) return;
    const kids = [...s.children].filter(e => !e.matches('aside, script, style, .big-num, .abs'));
    kids.forEach(e => { e.style.zoom = ''; });
    const sc = parseFloat(getComputedStyle(deck).getPropertyValue('--s')) || 1;
    const sr = s.getBoundingClientRect();
    let top = Infinity, bottom = -Infinity;
    kids.forEach(k => {
      const r = k.getBoundingClientRect(); if (r.height) { top = Math.min(top, r.top); bottom = Math.max(bottom, r.bottom); }
      k.querySelectorAll('*').forEach(e => { const q = e.getBoundingClientRect(); if (q.height && q.width) bottom = Math.max(bottom, q.bottom); });
    });
    const limit = sr.bottom - 70 * sc;
    if (bottom > limit && bottom > top) {
      const f = Math.max(0.55, (limit - top) / (bottom - top) * 0.98);
      kids.forEach(e => { e.style.zoom = f.toFixed(3); });
    }
  }

  function next() { if (k < groups[i].length) k++; else if (i < slides.length - 1) { i++; k = 0; } render(true); }
  function prev() { if (k > 0) { k--; prevK = k; } else if (i > 0) { i--; k = groups[i].length; } render(false); }
  function go(x, all) { i = Math.max(0, Math.min(slides.length - 1, x)); k = all ? groups[i].length : 0; render(true); }

  // overview
  slides.forEach((s, x) => {
    const b = document.createElement('button');
    const t = s.querySelector('h1,h2,h3')?.textContent.trim() || s.dataset.title || 'სლაიდი';
    b.innerHTML = `<small>${x + 1} · ${sections[x] || ''}</small>${t}`;
    b.onclick = e => { e.stopPropagation(); ov.classList.remove('open'); go(x); };
    ov.appendChild(b);
  });

  if (bc) bc.onmessage = ({ data }) => {
    if (data.t === 'hello') bc.postMessage({ t: 'state', i, k });
    if (data.t === 'go') go(data.n);
  };
  const openStudy = () => {
    // ცალკე ჩანართში (არა popup ფანჯარაში) — სლაიდებს მაინც მიჰყვება
    window.open('study.html?live#s-' + (i + 1), 'study-' + document.title);
  };
  document.getElementById('studybtn')?.addEventListener('click', e => { e.currentTarget.blur(); openStudy(); });
  const openLecturer = () => window.open('lecturer.html', 'lecturer-' + document.title);
  // ka ⇄ en: იგივე სლაიდზე გადასვლა
  document.getElementById('langbtn')?.addEventListener('click', e => { location.href = e.currentTarget.dataset.href + location.hash; });

  document.addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    // სლაიდზე ტექსტის ველში წერისას კლავიშები ნავიგაციას არ ეკუთვნის (Escape — ველიდან გამოსვლა)
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) { if (e.key === 'Escape') t.blur(); return; }
    const key = e.key, code = e.code;
    if (key === 'ArrowRight') { e.preventDefault(); e.shiftKey ? go(i + 1) : next(); }
    else if (key === 'ArrowLeft') { e.preventDefault(); e.shiftKey ? go(i - 1) : prev(); }
    else if ([' ', 'Enter', 'PageDown', 'PageUp', 'ArrowDown', 'ArrowUp', 'Backspace'].includes(key)) { e.preventDefault(); }
    else if (key === 'Home') go(0);
    else if (key === 'End') go(slides.length - 1, true);
    else if (code === 'KeyO' || key === 'Escape') ov.classList.toggle('open', key === 'Escape' ? false : !ov.classList.contains('open'));
    else if (code === 'KeyF') { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.(); }
    else if (code === 'KeyA') { k = groups[i].length; render(true); }
    else if (code === 'KeyP' && document.body.dataset.study) { e.preventDefault(); openStudy(); }
    else if (code === 'KeyL' && document.body.dataset.lect)   // ლექტორის გვერდი: ღილაკი არ ჩანს, მხოლოდ L
     { e.preventDefault(); openLecturer(); }
    else if (code === 'KeyT' && window.toggleTheme) { e.preventDefault(); toggleTheme(); }
  });
  addEventListener('hashchange', () => { const oi = i, ok = k; parseHash(); if (oi !== i || ok !== k) render(true); });

  function fit() {
    // 16:9 on wide screens; grow canvas height up to 16:10 so MacBook-style screens have no bars
    const H = Math.max(900, Math.min(1000, Math.round(1600 * innerHeight / innerWidth)));
    deck.style.setProperty('--h', H + 'px');
    deck.style.setProperty('--s', Math.min(innerWidth / 1600, innerHeight / H));
  }
  setTimeout(() => document.getElementById('help')?.classList.add('hide'), 6000);
  addEventListener('resize', () => { fit(); fitSlide(slides[i]); }); fit();
  document.fonts?.ready.then(() => fitSlide(slides[i]));
  render(true);
})();
