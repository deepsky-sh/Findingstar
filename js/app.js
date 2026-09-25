/* ==========================================================================
   별찾기 FindingStar — application controller
   ========================================================================== */
(function () {
  'use strict';
  const A = window.Astro, SR = window.SkyRenderer, G = window.GUIDE, S = window.Sensors;
  const CONS = SR.CONS;
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const store = {
    get(k, d) { try { const v = localStorage.getItem('fs.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem('fs.' + k, JSON.stringify(v)); } catch { /* private mode */ } }
  };

  /* ---------------- data prep ---------------- */
  Object.assign(CONS.Cyg, { ko: '백조자리' });
  Object.assign(CONS.Cep, { ko: '케페우스자리' });
  const SEASONS = ['spring', 'summer', 'autumn', 'winter'];
  const FEATURED = {};
  for (const s of SEASONS) for (const c of G.seasons[s].cons) FEATURED[c.id] = Object.assign({ season: s }, c);
  const BODY_ICON = { moon: '🌙', sun: '☀️', mercury: '☿', venus: '♀', mars: '♂', jupiter: '♃', saturn: '♄' };
  const BODY_KEYS = ['moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];

  /* ---------------- state ---------------- */
  const DEFAULT_LOC = { lat: 37.5665, lon: 126.978, name: '서울' };
  const state = {
    loc: store.get('loc', null) || DEFAULT_LOC,
    hasLoc: !!store.get('loc', null),
    skyTime: null, // null → live
    season: null,
    layers: store.get('layers', null),
    magLimit: store.get('mag', 4.5),
    calib: store.get('calib', 0),
    arFov: store.get('arFov', 62),
    lastPage: 'tonight'
  };
  const skyNow = () => state.skyTime ? new Date(state.skyTime) : new Date();

  /* ---------------- helpers ---------------- */
  const DIRS = ['북', '북북동', '북동', '동북동', '동', '동남동', '남동', '남남동', '남', '남남서', '남서', '서남서', '서', '서북서', '북서', '북북서'];
  const dirName = az => DIRS[Math.round(A.norm360(az) / 22.5) % 16];
  const fmtT = d => d ? d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false }) : '—';
  const fmtDT = d => d.toLocaleString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
  const altAz = (v, date) => A.toAltAz(A.apply(A.j2000ToHorizon(date, state.loc.lat, state.loc.lon), v));
  function bodyVec(key, date) {
    if (key === 'moon') { const m = A.moon(date); return A.topocentric(m.v, m.dist, date, state.loc.lat, state.loc.lon); }
    return A.planets(date)[key].v;
  }
  const _bestMonth = {};
  function bestMonth(id) {
    if (_bestMonth[id]) return _bestMonth[id];
    const ra = A.toRaDec(CONS[id].center).ra;
    let best = 1, bd = 1e9; const y = new Date().getFullYear();
    for (let m = 1; m <= 12; m++) {
      const d = new Date(y, m - 1, 15, 21, 0, 0);
      const ha = Math.abs(A.norm180(A.lst(d, state.loc.lon) - ra));
      if (ha < bd) { bd = ha; best = m; }
    }
    return (_bestMonth[id] = best);
  }
  const seasonOfMonth = m => (m >= 3 && m <= 5) ? 'spring' : (m >= 6 && m <= 8) ? 'summer' : (m >= 9 && m <= 11) ? 'autumn' : 'winter';
  const seasonOf = id => FEATURED[id] ? FEATURED[id].season : seasonOfMonth(bestMonth(id));
  function statusPill(alt, az) {
    if (alt > 20) return `<span class="pill up">보여요 · ${dirName(az)} ${Math.round(alt)}°</span>`;
    if (alt > 0) return `<span class="pill low">낮게 떠요 · ${dirName(az)} ${Math.round(alt)}°</span>`;
    return `<span class="pill down">지평선 아래</span>`;
  }
  function riseSetOf(vec, from, h0 = -0.5667) {
    return A.riseSet(typeof vec === 'function' ? vec : () => vec, from, state.loc.lat, state.loc.lon, h0, 24, 15);
  }
  function riseSetText(rs) {
    if (rs.alwaysUp) return '지지 않음 (주극성)';
    if (rs.neverUp) return '오늘은 뜨지 않음';
    return `뜸 ${fmtT(rs.rise)} · 짐 ${fmtT(rs.set)}`;
  }
  function brightestStarOf(id) {
    const f = FEATURED[id];
    if (f && f.mainHip) {
      const n = SR.NAME_BY_HIP.get(f.mainHip);
      if (n) return { name: n.ko, mag: SR.starMag(n.idx) };
    }
    // match stick-figure vertices to catalog names
    let best = null;
    for (const n of SR.STAR_NAMES) {
      if (!n.desig.endsWith(' ' + id)) continue;
      const mag = SR.starMag(n.idx);
      if (!best || mag < best.mag) best = { name: n.ko, mag };
    }
    return best;
  }
  function setAccent(hex) {
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    document.documentElement.style.setProperty('--accent', hex);
    document.documentElement.style.setProperty('--accent-rgb', `${r},${g},${b}`);
  }
  let toastTimer;
  function toast(msg, ms = 2600) {
    const t = $('#toast'); t.textContent = msg; t.classList.add('on');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('on'), ms);
  }
  function moonEmoji(m) {
    const a = m.age / 29.53;
    return ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘'][Math.round(a * 8) % 8];
  }

  /* ---------------- decorative background ---------------- */
  function drawBgStars() {
    const c = $('#bgStars'), x = c.getContext('2d'), d = Math.min(devicePixelRatio || 1, 2);
    c.width = innerWidth * d; c.height = innerHeight * d; x.scale(d, d);
    const n = Math.floor(innerWidth * innerHeight / 3500);
    for (let i = 0; i < n; i++) {
      x.globalAlpha = Math.random() * 0.5 + 0.1;
      x.fillStyle = '#dfe4ff';
      x.beginPath(); x.arc(Math.random() * innerWidth, Math.random() * innerHeight, Math.random() * 1.1 + 0.2, 0, Math.PI * 2); x.fill();
    }
  }

  /* ---------------- renderers ---------------- */
  const defaultLayers = { stars: true, lines: true, conNames: true, starNames: true, planets: true, milkyway: true, ground: true, cardinals: true, altazGrid: false, eqGrid: false };
  state.layers = Object.assign({}, defaultLayers, state.layers || {});

  function highlightFeatured(r, only) {
    r.highlight.clear();
    for (const id in FEATURED) if (!only || only.includes(id)) r.highlight.set(id, G.seasons[FEATURED[id].season].color);
  }

  const allsky = new SR($('#allsky'), { frame: 'horizon', interactive: false, fov: 196, maxFov: 200, lat: 89.9, lon: 180, fontScale: 0.85,
    layers: { starNames: true, milkyway: true, allConLines: true } });
  allsky.magLimit = 5;
  $('#allsky').addEventListener('click', () => { location.hash = '#sky'; });

  let seasonChart = null, detailChart = null, sky = null;

  /* ======================================================================
     ROUTER
     ====================================================================== */
  function route() {
    const h = (location.hash || '#tonight').slice(1);
    const [page, arg] = h.split('/');
    if (page === 'sky') { openSky(arg ? decodeURIComponent(arg) : null); navOn('sky'); return; }
    closeSky();
    const p = ['tonight', 'seasons', 'catalog'].includes(page) ? page : 'tonight';
    state.lastPage = p + (arg ? '/' + arg : '');
    $$('.page').forEach(s => { s.hidden = s.dataset.page !== p; });
    navOn(p);
    if (p === 'tonight') renderTonight();
    if (p === 'seasons') renderSeason(SEASONS.includes(arg) ? arg : (state.season || seasonOfMonth(new Date().getMonth() + 1)));
    if (p === 'catalog') renderCatalog();
    window.scrollTo({ top: 0 });
  }
  function navOn(p) { $$('[data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === p)); }

  /* ======================================================================
     TONIGHT
     ====================================================================== */
  function tonightRefTime() {
    const now = new Date();
    const sunAlt = altAz(A.planets(now).sun.v, now).alt;
    if (sunAlt < -8) return { t: now, label: '지금 기준' };
    const t = new Date(now); t.setHours(21, 0, 0, 0);
    if (t < now) t.setDate(t.getDate() + 1);
    const s = altAz(A.planets(t).sun.v, t).alt;
    if (s > -8) { const ni = A.nightInfo(now, state.loc.lat, state.loc.lon); if (ni.darkStart) return { t: ni.darkStart, label: `오늘 밤 ${fmtT(ni.darkStart)} 기준` }; }
    return { t, label: '오늘 밤 9시 기준' };
  }

  function renderTonight() {
    const now = new Date();
    $('#tonightDate').textContent = now.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }) + ' · ' + state.loc.name;
    $('#gpsBanner').hidden = state.hasLoc;

    allsky.setLocation(state.loc.lat, state.loc.lon);
    allsky.setTime(now);
    highlightFeatured(allsky);
    allsky.start();

    // --- stats ---
    const { lat, lon } = state.loc;
    const ni = A.nightInfo(now, lat, lon);
    const moon = A.moon(now);
    const noon = new Date(now); noon.setHours(12, 0, 0, 0);
    const mrs = riseSetOf(t => bodyVec('moon', t), noon, 0.125);
    // moonlight impact during the dark window
    const w0 = ni.darkStart || ni.sunset, w1 = ni.darkEnd || ni.sunrise;
    let frac = 0.5;
    if (w0 && w1 && w1 > w0) {
      let up = 0; const N = 12;
      for (let i = 0; i < N; i++) { const t = new Date(w0.getTime() + (w1 - w0) * (i + 0.5) / N); if (altAz(bodyVec('moon', t), t).alt > 0) up++; }
      frac = up / N;
    }
    const penalty = moon.illum * frac;
    const score = penalty < 0.15 ? ['좋음', 'score-good', '달빛 방해가 거의 없어요'] : penalty < 0.45 ? ['보통', 'score-mid', '달빛이 조금 있어요'] : ['아쉬움', 'score-bad', '밝은 달이 오래 떠 있어요'];
    $('#statGrid').innerHTML = `
      <div class="stat"><div class="k">${moonEmoji(moon)} 달</div><div class="v">${A.moonPhaseName(moon)}</div><div class="s">밝기 ${Math.round(moon.illum * 100)}% · ${mrs.neverUp ? '뜨지 않음' : `뜸 ${fmtT(mrs.rise)}`}</div></div>
      <div class="stat"><div class="k">🌇 해넘이 / 해돋이</div><div class="v">${fmtT(ni.sunset)}</div><div class="s">내일 해돋이 ${fmtT(ni.sunrise)}</div></div>
      <div class="stat"><div class="k">🌌 완전히 어두운 시간</div><div class="v">${ni.darkStart ? fmtT(ni.darkStart) : '없음'}</div><div class="s">${ni.darkEnd ? `~ ${fmtT(ni.darkEnd)} (천문박명)` : '백야/박명 지속'}</div></div>
      <div class="stat"><div class="k">🔭 오늘 밤 관측 지수</div><div class="v ${score[1]}">${score[0]}</div><div class="s">${score[2]}</div></div>`;

    // --- visible featured constellations ---
    const ref = tonightRefTime();
    $('#visibleWhen').textContent = ref.label;
    const vis = Object.keys(FEATURED).map(id => ({ id, ...altAz(CONS[id].center, ref.t) }))
      .filter(o => o.alt > 12).sort((a, b) => b.alt - a.alt).slice(0, 8);
    $('#visibleList').innerHTML = vis.length ? vis.map(o => {
      const f = FEATURED[o.id];
      return `<button class="lc" data-con="${o.id}"><span class="ico">${f.icon}</span><span class="body"><span class="t">${esc(CONS[o.id].ko)}<small>${esc(CONS[o.id].la)}</small></span><span class="d">${esc(f.brief)}</span></span><span class="side"><b>${dirName(o.az)}</b>고도 ${Math.round(o.alt)}°</span></button>`;
    }).join('') : '<div class="empty">지금은 대표 별자리가 낮게 떠 있어요. 3D 천구에서 전체 하늘을 둘러보세요.</div>';

    // --- planets ---
    $('#planetList').innerHTML = BODY_KEYS.map(k => {
      const v = bodyVec(k, ref.t), h = altAz(v, ref.t);
      const info = k === 'moon' ? { ko: '달', color: '#f4f1e6', mag: -12.7 } : Object.assign({}, A.PLANET_INFO[k], { mag: A.planets(ref.t)[k].mag });
      const where = h.alt > 0 ? `${dirName(h.az)} · 고도 ${Math.round(h.alt)}°` : '지평선 아래';
      return `<button class="pc" data-body="${k}"><div class="t"><span class="dot" style="color:${info.color};background:${info.color}"></span>${info.ko}</div><div class="d">${where}</div><div class="d">${k === 'moon' ? A.moonPhaseName(moon) : info.mag.toFixed(1) + '등급'}</div></button>`;
    }).join('');

    $('#tipsList').innerHTML = G.tips.map(t => `<div class="tip"><div class="i">${t.icon}</div><div class="t">${esc(t.title)}</div><div class="d">${esc(t.text)}</div></div>`).join('');
  }

  /* ======================================================================
     SEASONS
     ====================================================================== */
  function seasonChartDate(s) {
    const [m, d] = G.seasons[s].chartDate;
    const now = new Date();
    let t = new Date(now.getFullYear(), m - 1, d, 21, 0, 0);
    if (t.getTime() < now.getTime() - 45 * 864e5) t = new Date(now.getFullYear() + 1, m - 1, d, 21, 0, 0);
    return t;
  }

  function renderSeason(s) {
    state.season = s;
    const S0 = G.seasons[s];
    setAccent(S0.color);
    $('#seasonTabs').innerHTML = SEASONS.map(k => `<button role="tab" aria-selected="${k === s}" data-season="${k}">${G.seasons[k].emoji} ${G.seasons[k].name}</button>`).join('');
    const t = seasonChartDate(s);
    $('#seasonEyebrow').textContent = `${S0.emoji} ${S0.months.join('·')}월 저녁 하늘`;
    $('#seasonTitle').textContent = S0.title;
    $('#seasonDesc').textContent = S0.desc;
    $('#seasonSkyBtn').href = '#sky/season-' + s;
    $('#seasonSteps').innerHTML = S0.steps.map(x => `<li><span>${x}</span></li>`).join('');
    $('#seasonConsTitle').textContent = `${S0.name}철 대표 별자리`;

    if (!seasonChart) {
      seasonChart = new SR($('#seasonChart'), { frame: 'horizon', fov: 125, maxFov: 170, onSelect: o => {
        if (o.kind === 'con') openDetail(o.id);
        else if (o.kind === 'star') toast(`⭐ ${o.name}${o.en && o.en !== o.name ? ' (' + o.en + ')' : ''} · ${o.mag.toFixed(1)}등급`);
        else toast(`${BODY_ICON[o.key] || ''} ${o.name}`);
      } });
      seasonChart.magLimit = 5.0;
      seasonChart.start();
    }
    seasonChart.setLocation(state.loc.lat, state.loc.lon);
    seasonChart.setTime(t);
    seasonChart.highlight.clear();
    for (const c of S0.cons) seasonChart.highlight.set(c.id, S0.color);
    seasonChart.guides = S0.guides;
    seasonChart.setView(S0.view.az, S0.view.alt, 125);
    $('#seasonLegend').innerHTML = `<span>📅 ${t.getMonth() + 1}월 ${t.getDate()}일 밤 9시</span><span>📍 ${esc(state.loc.name)}</span>` +
      S0.guides.map(g => `<span style="color:${g.color.replace(/[\d.]+\)$/, '1)')}">┅ ${esc(g.label)}</span>`).join('');

    const now = new Date();
    $('#seasonCons').innerHTML = S0.cons.map(c => {
      const h = altAz(CONS[c.id].center, now), st = brightestStarOf(c.id);
      return `<button class="con-card" data-con="${c.id}">
        <div class="top"><span class="ico">${c.icon}</span><div><div class="t">${esc(CONS[c.id].ko)}</div><div class="la">${esc(CONS[c.id].la)}</div></div></div>
        <p class="brief">${esc(c.brief)}</p>
        <div class="meta"><span>⭐ ${esc(st ? st.name : '-')} ${st ? st.mag.toFixed(1) + '등급' : ''}</span><span>🗓️ ${bestMonth(c.id)}월 저녁 9시 남중</span>${statusPill(h.alt, h.az)}</div>
      </button>`;
    }).join('');
  }

  /* ======================================================================
     CATALOG
     ====================================================================== */
  let catFilter = 'all';
  const CAT_FILTERS = [['all', '전체'], ['featured', '⭐ 대표 20'], ['spring', '🌸 봄'], ['summer', '🌌 여름'], ['autumn', '🍁 가을'], ['winter', '❄️ 겨울'], ['visible', '👀 지금 보임']];
  function renderCatalog() {
    $('#catalogFilters').innerHTML = CAT_FILTERS.map(([k, l]) => `<button data-filter="${k}" class="${k === catFilter ? 'on' : ''}">${l}</button>`).join('');
    const q = $('#catalogSearch').value.trim().toLowerCase();
    const now = new Date();
    let ids = Object.keys(CONS);
    ids = ids.filter(id => {
      if (catFilter === 'featured' && !FEATURED[id]) return false;
      if (SEASONS.includes(catFilter) && seasonOf(id) !== catFilter) return false;
      if (catFilter === 'visible' && altAz(CONS[id].center, now).alt < 10) return false;
      if (q) { const c = CONS[id]; return [c.ko, c.la, c.en, id].some(s => s && s.toLowerCase().includes(q)); }
      return true;
    });
    ids.sort((a, b) => (!!FEATURED[b] - !!FEATURED[a]) || CONS[a].ko.localeCompare(CONS[b].ko, 'ko'));
    let html = ids.map(id => {
      const c = CONS[id], f = FEATURED[id], h = altAz(c.center, now);
      return `<button class="lc" data-con="${id}"><span class="ico">${f ? f.icon : '✦'}</span><span class="body"><span class="t">${esc(c.ko)}<small>${esc(c.la)}</small></span><span class="d">${f ? esc(f.brief) : `${G.seasons[seasonOf(id)].name}철 · ${bestMonth(id)}월 저녁 9시 남중`}</span></span><span class="side">${statusPill(h.alt, h.az)}</span></button>`;
    }).join('');
    if (q) {
      const stars = SR.STAR_NAMES.filter(n => n.ko.toLowerCase().includes(q) || (n.en || '').toLowerCase().includes(q)).slice(0, 12);
      html += stars.map(n => {
        const h = altAz(SR.starVec(n.idx), now);
        return `<button class="lc" data-star="${n.hip}"><span class="ico">⭐</span><span class="body"><span class="t">${esc(n.ko)}<small>${esc(n.en || '')}</small></span><span class="d">${esc(n.desig)} · ${SR.starMag(n.idx).toFixed(1)}등급</span></span><span class="side">${statusPill(h.alt, h.az)}</span></button>`;
      }).join('');
    }
    $('#catalogList').innerHTML = html || '<div class="empty">검색 결과가 없어요.</div>';
  }

  /* ======================================================================
     DETAIL SHEET
     ====================================================================== */
  function openDetail(id) {
    const c = CONS[id]; if (!c) return;
    const f = FEATURED[id], s = seasonOf(id), S0 = G.seasons[s];
    const now = new Date();
    $('#dIcon').textContent = f ? f.icon : '✦';
    $('#dTitle').textContent = c.ko;
    $('#dLatin').textContent = `${c.la} · ${c.gen || ''}`.replace(/ · $/, '');
    $('#dBadge').textContent = `${S0.emoji} ${S0.name}철 별자리 · ${bestMonth(id)}월 저녁 9시 남중`;
    const h = altAz(c.center, now), st = brightestStarOf(id);
    const noon = new Date(now); noon.setHours(12, 0, 0, 0);
    const rs = riseSetOf(c.center, noon);
    const decl = A.toRaDec(c.center).dec;
    $('#dGrid').innerHTML = `
      <div class="it"><div class="k">으뜸별</div><div class="v">${st ? `${esc(st.name)} · ${st.mag.toFixed(1)}등급` : '—'}</div></div>
      <div class="it"><div class="k">관측 적기</div><div class="v">${bestMonth(id)}월 저녁</div></div>
      <div class="it"><div class="k">지금 위치 (${fmtT(now)})</div><div class="v">${h.alt > 0 ? `${dirName(h.az)} · 고도 ${Math.round(h.alt)}°` : '지평선 아래'}</div></div>
      <div class="it"><div class="k">오늘 뜨고 지는 시각</div><div class="v">${riseSetText(rs)}</div></div>
      <div class="it"><div class="k">최대 고도</div><div class="v">${Math.round(90 - Math.abs(state.loc.lat - decl))}° (${(state.loc.lat - decl) >= 0 ? '남쪽' : '북쪽'})</div></div>
      <div class="it"><div class="k">겉보기 크기</div><div class="v">약 ${Math.round(c.extent * 2)}°</div></div>`;
    $('#dFindSec').hidden = false;
    $('#dFindText').innerHTML = f ? f.find : `<p>저녁 9시 기준 <b>${bestMonth(id)}월</b>에 ${(state.loc.lat - decl) >= 0 ? '남쪽' : '북쪽'} 하늘에서 가장 높이 뜹니다. 아래 “3D 천구에서 찾기”를 누르면 휴대폰을 움직여 방향을 안내받을 수 있어요.</p>`;
    $('#dMythSec').hidden = !f;
    $('#dMyth').innerHTML = f ? f.myth : '';
    $('#dFind').onclick = e => { e.preventDefault(); closeDetail(); startFinding('con-' + id, true); };
    $('#sheetBg').hidden = false;
    document.body.style.overflow = 'hidden';
    $('#sheet').scrollTop = 0;

    if (!detailChart) {
      detailChart = new SR($('#dChart'), { frame: 'equatorial', fov: 60, minFov: 10, maxFov: 140, onSelect: o => {
        if (o.kind === 'star') toast(`⭐ ${o.name} · ${o.mag.toFixed(1)}등급`);
        else if (o.kind === 'con' && o.id !== id) openDetail(o.id);
      } });
      detailChart.magLimit = 5.5;
      detailChart.layers.planets = true;
      detailChart.start();
    }
    detailChart.setTime(now);
    detailChart.highlight.clear();
    detailChart.highlight.set(id, S0.color);
    detailChart.guides = [];
    const rd = A.toRaDec(c.center);
    requestAnimationFrame(() => { detailChart.resize(); detailChart.setView(rd.ra, rd.dec, Math.max(28, Math.min(120, c.extent * 2.6))); });
  }
  function closeDetail() { $('#sheetBg').hidden = true; document.body.style.overflow = ''; }

  /* ======================================================================
     3D SKY VIEW
     ====================================================================== */
  const sensor = new S.OrientationSensor();
  sensor.calibration = state.calib;
  let sensorOn = false, arOn = false, liveTimer = null, lapseTimer = null, targetState = null, foundBuzzed = false, hudRaf = 0;

  function ensureSky() {
    if (sky) return sky;
    sky = new SR($('#skyCanvas'), {
      frame: 'horizon', fov: 90, minFov: 5, maxFov: 150, lon: 180, lat: 35,
      onSelect: showInfo,
      onTarget: updateTargetHint,
      onViewChange: () => scheduleHud()
    });
    sky.onCalibrate = d => { sensor.calibration += d; state.calib = sensor.calibration; store.set('calib', state.calib); };
    Object.assign(sky.layers, state.layers);
    sky.magLimit = state.magLimit;
    sensor.onChange(b => { if (sensorOn) { sky.setSensorBasis(b); scheduleHud(); } });
    buildLayerToggles();
    return sky;
  }

  function openSky(arg) {
    ensureSky();
    const sv = $('#skyview');
    if (sv.hidden) {
      sv.hidden = false;
      document.body.classList.add('sky-open');
      $('#svClose').href = '#' + state.lastPage;
      sky.setLocation(state.loc.lat, state.loc.lon);
      sky.setTime(skyNow());
      sky.resize();
      sky.start();
      clearInterval(liveTimer);
      liveTimer = setInterval(() => { if (!state.skyTime && !lapseTimer) { sky.setTime(new Date()); updateTimeLabel(); } }, 5000);
      updateTimeLabel();
      $('#svLoc').textContent = state.loc.name;
    }
    if (arg && arg !== state.skyArg) applySkyArg(arg);
    state.skyArg = arg;
    scheduleHud();
  }
  function closeSky() {
    const sv = $('#skyview');
    if (sv.hidden) return;
    sv.hidden = true;
    document.body.classList.remove('sky-open');
    setSensor(false); setAR(false);
    stopLapse();
    clearInterval(liveTimer);
    if (sky) sky.stop();
    hidePanels(); $('#svInfo').hidden = true;
    state.skyArg = null;
  }

  function applySkyArg(arg) {
    if (arg.startsWith('season-')) {
      const s = arg.slice(7), S0 = G.seasons[s]; if (!S0) return;
      sky.highlight.clear(); for (const c of S0.cons) sky.highlight.set(c.id, S0.color);
      sky.guides = S0.guides;
      setTarget(targetFromKey('con-' + S0.cons[0].id));
      return;
    }
    const t = targetFromKey(arg);
    if (t) setTarget(t);
  }

  function targetFromKey(key) {
    if (key.startsWith('con-')) {
      const id = key.slice(4), c = CONS[id]; if (!c) return null;
      return { key, kind: 'con', id, label: c.ko, vec: () => c.center };
    }
    if (key.startsWith('star-')) {
      const n = SR.NAME_BY_HIP.get(+key.slice(5)); if (!n) return null;
      const v = SR.starVec(n.idx);
      return { key, kind: 'star', label: n.ko, vec: () => v };
    }
    if (key.startsWith('body-')) {
      const k = key.slice(5); if (!BODY_ICON[k]) return null;
      let cacheT = 0, cacheV = null;
      return { key, kind: 'body', label: k === 'moon' ? '달' : k === 'sun' ? '태양' : A.PLANET_INFO[k].ko,
        vec: () => { const t = sky.time.getTime(); if (t !== cacheT) { cacheT = t; cacheV = bodyVec(k, sky.time); } return cacheV; } };
    }
    return null;
  }

  function setTarget(t) {
    sky.target = t; foundBuzzed = false; targetState = null;
    if (!t) { $('#svTarget').hidden = true; sky.invalidate(); return; }
    if (t.kind === 'con' && !sky.highlight.has(t.id)) sky.highlight.set(t.id, '#ffd166');
    $('#stName').textContent = t.label;
    $('#stHint').textContent = '';
    $('#svTarget').hidden = false;
    $('#svInfo').hidden = true;
    const rs = riseSetOf(t.vec(), sky.time);
    t.riseText = rs.rise ? fmtT(rs.rise) : null;
    if (!sensorOn) {
      const h = sky.altAz(t.vec());
      const fov = t.kind === 'con' ? Math.max(40, Math.min(110, CONS[t.id].extent * 3)) : 50;
      // below the horizon: look toward its azimuth just above the ground instead of into the earth
      if (h.alt < 0) sky.flyToView(h.az, 12, 100); else sky.flyTo(t.vec(), fov);
      if (h.alt < 0) toast(`${t.label}은(는) 지금 지평선 아래에 있어요${t.riseText ? ` · ${t.riseText}에 떠요` : ''}`);
    }
    sky.invalidate();
  }

  /** Start "find" from outside the sky view (user gesture → can request sensor permission). */
  function startFinding(key, withSensor) {
    location.hash = '#sky/' + encodeURIComponent(key);
    openSky(key);
    if (withSensor && isTouchDevice()) setSensor(true);
  }
  const isTouchDevice = () => matchMedia('(pointer: coarse)').matches;

  let lastHint = 0;
  function updateTargetHint(s) {
    const now = performance.now();
    if (now - lastHint < 150) return; lastHint = now;
    const t = sky.target; if (!t || !s.target) return;
    const box = $('#svTarget'), hint = $('#stHint');
    const found = s.angle < Math.max(3, sky.fov * 0.08);
    box.classList.toggle('found', found && s.target.alt > -1);
    if (s.target.alt < -1) {
      hint.textContent = `지금은 지평선 아래 (${dirName(s.target.az)}쪽)${t.riseText ? ` · ${t.riseText}에 떠요` : ''}`;
      return;
    }
    const where = `${dirName(s.target.az)}쪽 · 고도 ${Math.round(s.target.alt)}°`;
    if (found) {
      hint.textContent = `찾았어요! 화면 가운데를 보세요 · ${where}`;
      if (!foundBuzzed && sensorOn) { foundBuzzed = true; navigator.vibrate && navigator.vibrate([60, 40, 60]); }
      return;
    }
    if (s.angle > 12) foundBuzzed = false;
    if (s.angle > 110) { hint.textContent = `뒤쪽에 있어요 · 몸을 돌려 ${dirName(s.target.az)}쪽 하늘(고도 ${Math.round(s.target.alt)}°)을 보세요`; return; }
    const parts = [];
    if (Math.abs(s.right) > 2) parts.push(`${s.right > 0 ? '➡ 오른쪽' : '⬅ 왼쪽'}으로 ${Math.round(Math.abs(s.right))}°`);
    if (Math.abs(s.up) > 2) parts.push(`${s.up > 0 ? '⬆ 위' : '⬇ 아래'}로 ${Math.round(Math.abs(s.up))}°`);
    hint.textContent = (sensorOn ? '휴대폰을 ' : '') + (parts.join(', ') || '거의 다 왔어요') + ` · ${where}`;
  }

  function scheduleHud() {
    if (hudRaf) return;
    hudRaf = requestAnimationFrame(() => {
      hudRaf = 0; if (!sky) return;
      const f = sky._cam.f;
      const alt = Math.asin(Math.max(-1, Math.min(1, f[2]))) * A.R2D, az = A.norm360(Math.atan2(f[0], f[1]) * A.R2D);
      $('#svHud').textContent = `${dirName(az)} ${Math.round(az)}° · 고도 ${Math.round(alt)}° · 시야 ${Math.round(sky.fov)}°`;
    });
  }

  function updateTimeLabel() {
    const t = skyNow();
    $('#svTime').textContent = (state.skyTime ? '🕒 ' : '● 실시간 ') + fmtDT(t);
    $('#svTime').parentElement.style.color = state.skyTime ? 'var(--gold)' : '';
  }
  function setSkyTime(t) {
    state.skyTime = t ? t.getTime() : null;
    if (sky) sky.setTime(skyNow());
    updateTimeLabel();
    if (sky && sky.target) { const rs = riseSetOf(sky.target.vec(), sky.time); sky.target.riseText = rs.rise ? fmtT(rs.rise) : null; }
  }
  function stopLapse() { if (lapseTimer) { clearInterval(lapseTimer); lapseTimer = null; $('#timeLapse').textContent = '▶ 타임랩스'; } }

  /* ----- sensors ----- */
  async function setSensor(on) {
    if (on === sensorOn) return;
    const btn = $('#svSensor');
    if (on) {
      if (!S.OrientationSensor.supported) { toast('이 브라우저는 방향 센서를 지원하지 않아요. 드래그로 둘러보세요.'); return; }
      try {
        btn.setAttribute('aria-pressed', 'true');
        await sensor.start();
        sensorOn = true;
        sky.projection = 'gnomonic';
        sky.minFov = 20; sky.maxFov = 100;
        sky.fov = arOn ? state.arFov : 75;
        $('#svCalib').hidden = false;
        setTimeout(() => { $('#svCalib').hidden = true; }, 6000);
        if (!sensor.absolute) toast('나침반 정보가 없어 방위가 실제와 다를 수 있어요. 좌우로 드래그해 보정하세요.', 4200);
        else toast('휴대폰을 하늘로 들어 비춰 보세요 ✨');
        if (!state.hasLoc) useGPS(true);
      } catch (e) {
        btn.setAttribute('aria-pressed', 'false');
        sensorOn = false;
        const msg = e && e.message === 'denied' ? '센서 사용 권한이 거부됐어요. 브라우저 설정에서 “동작 및 방향” 접근을 허용해 주세요.'
          : location.protocol !== 'https:' && location.hostname !== 'localhost' ? '센서는 HTTPS 접속에서만 사용할 수 있어요.'
            : '이 기기에서는 자이로 센서를 찾을 수 없어요. 드래그와 확대로 둘러보세요.';
        toast(msg, 4200);
      }
    } else {
      sensor.stop();
      sensorOn = false;
      btn.setAttribute('aria-pressed', 'false');
      $('#svCalib').hidden = true;
      if (sky) {
        const v = sky.getView();
        sky.setSensorBasis(null);
        sky.projection = 'stereo'; sky.minFov = 5; sky.maxFov = 150;
        sky.setView(v.lon, v.lat, 90);
      }
    }
  }
  async function setAR(on) {
    if (on === arOn) return;
    const btn = $('#svAR'), video = $('#arVideo');
    if (on) {
      try {
        btn.setAttribute('aria-pressed', 'true');
        await S.startCamera(video);
        arOn = true;
        $('#skyview').classList.add('ar');
        sky.transparentBg = true;
        if (!sensorOn) await setSensor(true);
        sky.fov = state.arFov;
        sky.invalidate();
        toast('두 손가락으로 확대·축소해 카메라 화면과 별 위치를 맞춰 보세요.', 3800);
      } catch (e) {
        btn.setAttribute('aria-pressed', 'false');
        toast(e && e.name === 'NotAllowedError' ? '카메라 권한이 필요해요.' : '카메라를 사용할 수 없어요.');
      }
    } else {
      S.stopCamera(video);
      if (sky && arOn) { state.arFov = sky.fov; store.set('arFov', state.arFov); }
      arOn = false;
      btn.setAttribute('aria-pressed', 'false');
      $('#skyview').classList.remove('ar');
      if (sky) { sky.transparentBg = false; sky.invalidate(); }
    }
  }

  /* ----- info card on tap ----- */
  function showInfo(o) {
    const t = sky.time, box = $('#svInfo'), body = $('#siBody');
    const v = o.vec, h = sky.altAz(v);
    const noon = new Date(t); noon.setHours(12, 0, 0, 0);
    let title = o.name, sub = '', extra = '', key = '';
    if (o.kind === 'con') {
      const c = CONS[o.id];
      sub = `${c.la} · 별자리`; key = 'con-' + o.id;
      extra = `<div><small>관측 적기</small><b>${bestMonth(o.id)}월 저녁</b></div>`;
    } else if (o.kind === 'star') {
      sub = [o.en, o.desig].filter(Boolean).join(' · ') || '항성';
      const n = SR.STAR_NAMES.find(x => x.idx === o.idx);
      key = n ? 'star-' + n.hip : '';
      extra = `<div><small>밝기</small><b>${o.mag.toFixed(2)}등급</b></div>`;
    } else {
      const d = o.data;
      sub = o.key === 'moon' ? `${A.moonPhaseName(d)} · ${Math.round(d.illum * 100)}%` : o.key === 'sun' ? '항성 · 태양계의 중심' : `행성 · ${(d.dist).toFixed(2)} AU`;
      key = 'body-' + o.key;
      extra = `<div><small>밝기</small><b>${d.mag.toFixed(1)}등급</b></div>`;
    }
    const rs = o.kind === 'body' ? riseSetOf(tt => bodyVec(o.key, tt), noon, o.key === 'sun' ? -0.833 : 0.125) : riseSetOf(v, noon);
    body.innerHTML = `<h3>${o.kind === 'body' ? BODY_ICON[o.key] + ' ' : ''}${esc(title)}</h3><div class="sub">${esc(sub)}</div>
      <div class="kv"><div><small>방위</small><b>${dirName(h.az)} ${Math.round(h.az)}°</b></div><div><small>고도</small><b>${h.alt.toFixed(1)}°</b></div>${extra}</div>
      <p class="muted small" style="margin-bottom:10px">${riseSetText(rs)}</p>
      <div class="btn-row">${o.kind === 'con' ? `<button class="btn small" data-detail="${o.id}">📖 이야기</button>` : ''}${key ? `<button class="btn small primary" data-target="${key}">🎯 안내</button>` : ''}</div>`;
    box.hidden = false;
    hidePanels();
  }

  /* ----- panels ----- */
  function hidePanels() { $$('.sv-panel').forEach(p => { p.hidden = true; }); }
  function togglePanel(id) { const p = $(id), was = p.hidden; hidePanels(); $('#svInfo').hidden = true; p.hidden = !was; return !was; }

  const LAYER_LABELS = [['lines', '별자리 선'], ['conNames', '별자리 이름'], ['starNames', '별 이름'], ['planets', '행성·달'], ['milkyway', '은하수'], ['ground', '지면'], ['altazGrid', '지평 좌표선'], ['eqGrid', '적도 좌표선']];
  function buildLayerToggles() {
    $('#layerToggles').innerHTML = LAYER_LABELS.map(([k, l]) => `<label>${l}<input type="checkbox" data-layer="${k}" ${state.layers[k] ? 'checked' : ''}></label>`).join('');
    $('#magSelect').value = String(state.magLimit);
  }

  function searchSky(q) {
    q = q.trim().toLowerCase();
    const out = [];
    const t = sky.time;
    for (const k of BODY_KEYS.concat('sun')) {
      const name = k === 'moon' ? '달' : k === 'sun' ? '태양' : A.PLANET_INFO[k].ko;
      if (!q || name.includes(q) || k.includes(q)) out.push({ key: 'body-' + k, i: BODY_ICON[k], t: name, d: k === 'sun' ? '태양' : '태양계 천체', v: bodyVec(k, t) });
    }
    const featuredFirst = Object.keys(CONS).sort((a, b) => (!!FEATURED[b] - !!FEATURED[a]) || CONS[a].ko.localeCompare(CONS[b].ko, 'ko'));
    for (const id of featuredFirst) {
      const c = CONS[id];
      if (!q || [c.ko, c.la, c.en, id].some(s => s && s.toLowerCase().includes(q))) out.push({ key: 'con-' + id, i: FEATURED[id] ? FEATURED[id].icon : '✦', t: c.ko, d: c.la, v: c.center });
    }
    if (q) for (const n of SR.STAR_NAMES) {
      if (n.ko.toLowerCase().includes(q) || (n.en || '').toLowerCase().includes(q)) out.push({ key: 'star-' + n.hip, i: '⭐', t: n.ko, d: `${n.en || ''} · ${SR.starMag(n.idx).toFixed(1)}등급`, v: SR.starVec(n.idx) });
    }
    $('#skySearchResults').innerHTML = out.slice(0, 60).map(r => {
      const h = sky.altAz(r.v);
      return `<button class="sr" data-target="${r.key}"><span class="i">${r.i}</span><span><div class="t">${esc(r.t)}</div><div class="d">${esc(r.d)}</div></span><span class="r">${h.alt > 0 ? `<span class="pill up">${dirName(h.az)} ${Math.round(h.alt)}°</span>` : '<span class="pill down">지평선 아래</span>'}</span></button>`;
    }).join('') || '<div class="empty">찾는 천체가 없어요.</div>';
  }

  /* ======================================================================
     LOCATION
     ====================================================================== */
  function nearestCity(lat, lon) {
    let best = null, bd = 1e9;
    for (const [n, la, lo] of G.cities) { const d = Math.hypot(la - lat, (lo - lon) * Math.cos(lat * A.D2R)) * 111; if (d < bd) { bd = d; best = n; } }
    return bd < 35 ? best : null;
  }
  function setLocation(lat, lon, name, persist = true) {
    state.loc = { lat, lon, name };
    if (persist) { store.set('loc', state.loc); state.hasLoc = true; }
    $('#locName').textContent = name; $('#svLoc').textContent = name;
    for (const k in _bestMonth) delete _bestMonth[k];
    if (sky) sky.setLocation(lat, lon);
    if (!$('#skyview').hidden) return;
    route();
  }
  async function useGPS(silent) {
    const st = $('#gpsStatus');
    if (!silent) st.textContent = '위치를 확인하는 중…';
    try {
      const p = await S.getPosition();
      const city = nearestCity(p.lat, p.lon);
      setLocation(+p.lat.toFixed(4), +p.lon.toFixed(4), city ? `${city} (현재 위치)` : '현재 위치');
      if (!silent) { st.textContent = `위도 ${p.lat.toFixed(3)}°, 경도 ${p.lon.toFixed(3)}° (±${Math.round(p.acc)}m)`; closeLoc(); }
      toast('📍 현재 위치로 하늘을 맞췄어요');
    } catch (e) {
      const msg = e && e.code === 1 ? '위치 권한이 거부됐어요. 도시를 직접 선택해 주세요.' : '위치를 가져오지 못했어요. 도시를 직접 선택해 주세요.';
      if (!silent) st.textContent = msg; else toast(msg);
    }
  }
  function openLoc() {
    $('#cityGrid').innerHTML = G.cities.map(([n, la, lo]) => `<button data-city="${n}" class="${state.loc.name === n ? 'on' : ''}">${n}</button>`).join('');
    $('#latInput').value = state.loc.lat; $('#lonInput').value = state.loc.lon;
    $('#gpsStatus').textContent = '';
    $('#locBg').hidden = false;
  }
  function closeLoc() { $('#locBg').hidden = true; }

  /* ======================================================================
     EVENTS
     ====================================================================== */
  function bind() {
    addEventListener('hashchange', route);
    addEventListener('resize', () => { clearTimeout(bind._r); bind._r = setTimeout(drawBgStars, 200); });

    document.addEventListener('click', e => {
      const el = e.target.closest('[data-con],[data-body],[data-star],[data-season],[data-filter],[data-target],[data-detail],[data-city],[data-close],[data-sensor-start],[data-dt]');
      if (!el) return;
      const d = el.dataset;
      if (d.sensorStart !== undefined) { e.preventDefault(); location.hash = '#sky'; openSky(); if (isTouchDevice()) setSensor(true); else toast('PC에서는 드래그·휠로 둘러보세요. 휴대폰에서는 센서로 찾을 수 있어요!'); return; }
      if (d.con) { openDetail(d.con); return; }
      if (d.body) { startFinding('body-' + d.body, false); return; }
      if (d.star) { startFinding('star-' + d.star, false); return; }
      if (d.season) { location.hash = '#seasons/' + d.season; return; }
      if (d.filter) { catFilter = d.filter; renderCatalog(); return; }
      if (d.detail) { openDetail(d.detail); return; }
      if (d.target) { const t = targetFromKey(d.target); if (t) { hidePanels(); setTarget(t); history.replaceState(null, '', '#sky/' + encodeURIComponent(d.target)); } return; }
      if (d.city) { const c = G.cities.find(x => x[0] === d.city); setLocation(c[1], c[2], c[0]); closeLoc(); toast(`📍 ${c[0]} 하늘로 바꿨어요`); return; }
      if (d.dt) { stopLapse(); setSkyTime(new Date(skyNow().getTime() + (+d.dt) * 1000)); syncTimeInput(); return; }
      if (d.close !== undefined) { hidePanels(); closeLoc(); return; }
    });

    $('#sheetClose').onclick = closeDetail;
    $('#sheetBg').addEventListener('click', e => { if (e.target.id === 'sheetBg') closeDetail(); });
    $('#locBg').addEventListener('click', e => { if (e.target.id === 'locBg') closeLoc(); });
    addEventListener('keydown', e => { if (e.key === 'Escape') { closeDetail(); closeLoc(); hidePanels(); } });

    $('#locChip').onclick = openLoc;
    $('#svLocBtn').onclick = openLoc;
    $('#gpsBtn').onclick = () => useGPS(false);
    $('#gpsBannerBtn').onclick = () => useGPS(false);
    $('#latlonApply').onclick = () => {
      const la = parseFloat($('#latInput').value), lo = parseFloat($('#lonInput').value);
      if (!(Math.abs(la) <= 90 && Math.abs(lo) <= 180)) { toast('위도/경도 값을 확인해 주세요'); return; }
      setLocation(la, lo, `${la.toFixed(2)}°, ${lo.toFixed(2)}°`); closeLoc();
    };

    const red = store.get('red', false);
    document.documentElement.classList.toggle('red', red);
    $('#redToggle').setAttribute('aria-pressed', String(red));
    $('#redToggle').onclick = () => {
      const on = !document.documentElement.classList.contains('red');
      document.documentElement.classList.toggle('red', on);
      $('#redToggle').setAttribute('aria-pressed', String(on)); store.set('red', on);
      toast(on ? '🔴 야간 모드: 눈의 암순응을 지켜줘요' : '야간 모드 해제');
    };

    $('#catalogSearch').addEventListener('input', () => renderCatalog());

    // sky view tools
    $('#svSensor').onclick = () => setSensor(!sensorOn);
    $('#svAR').onclick = () => setAR(!arOn);
    $('#svSearch').onclick = () => { if (togglePanel('#searchPanel')) { $('#skySearch').value = ''; searchSky(''); setTimeout(() => $('#skySearch').focus(), 50); } };
    $('#skySearch').addEventListener('input', e => searchSky(e.target.value));
    $('#svLayers').onclick = () => togglePanel('#layerPanel');
    $('#svTimeBtn').onclick = () => { if (togglePanel('#timePanel')) syncTimeInput(); };
    $('#svNow').onclick = () => { stopLapse(); setSkyTime(null); toast('실시간 하늘로 돌아왔어요'); };
    $('#svCalibReset').onclick = () => { sensor.calibration = 0; state.calib = 0; store.set('calib', 0); toast('방위 보정을 초기화했어요'); };
    $('#stClose').onclick = () => setTarget(null);
    $('#siClose').onclick = () => { $('#svInfo').hidden = true; };
    $('#layerToggles').addEventListener('change', e => {
      const k = e.target.dataset.layer; if (!k) return;
      state.layers[k] = e.target.checked; sky.layers[k] = e.target.checked; sky.invalidate(); store.set('layers', state.layers);
    });
    $('#magSelect').addEventListener('change', e => { state.magLimit = +e.target.value; sky.magLimit = state.magLimit; sky.invalidate(); store.set('mag', state.magLimit); });
    $('#timeInput').addEventListener('change', e => { if (e.target.value) { stopLapse(); setSkyTime(new Date(e.target.value)); } });
    $('#timeNow').onclick = () => { stopLapse(); setSkyTime(null); syncTimeInput(); };
    $('#time21').onclick = () => { stopLapse(); const t = new Date(); t.setHours(21, 0, 0, 0); setSkyTime(t); syncTimeInput(); };
    $('#timeLapse').onclick = () => {
      if (lapseTimer) { stopLapse(); return; }
      $('#timeLapse').textContent = '⏸ 멈춤';
      let t = skyNow().getTime();
      lapseTimer = setInterval(() => { t += 4 * 60000; setSkyTime(new Date(t)); }, 40);
    };
    document.addEventListener('visibilitychange', () => { if (document.hidden) { sensor.stop(); } else if (sensorOn) sensor.start().catch(() => setSensor(false)); });
  }
  function syncTimeInput() {
    const t = skyNow(), p = n => String(n).padStart(2, '0');
    $('#timeInput').value = `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}T${p(t.getHours())}:${p(t.getMinutes())}`;
  }

  /* ======================================================================
     BOOT
     ====================================================================== */
  function boot() {
    drawBgStars();
    $('#locName').textContent = state.loc.name;
    bind();
    route();
    if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  window.FindingStar = { state, openDetail, setTarget: k => setTarget(targetFromKey(k)), get sky() { return sky; } };
})();
