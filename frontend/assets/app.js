/* Bhumi Vikas Sahayak – single-page UI. No build step: vanilla JS + Tailwind CDN + Chart.js. */
const CFG = window.BVS_CONFIG || { apiBase: '/v1', apiKey: 'bvs-web-ui' };
const $ = (s, el = document) => el.querySelector(s);
const view = $('#view');
const charts = [];

const SAMPLES = [
  'My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?',
  'मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?',
  'What is the fee for building permission for a 180 sq m residential house?',
  'Do I need separate development permission for a 300 sq m plot that matches the Development Plan?',
  'How far must my balcony stay from a low-voltage overhead electric line?',
  'My development permission was granted in 2023. How long does it stay valid?',
  'बिल्डिंग परमिशन की फीस कितनी है और किस नियम में लिखी है?',
  'How do I pay my property tax online?',
];

/* ---------------- settings (stored only in this browser) ---------------- */
const SETTINGS_KEY = 'bvs-settings';
const DEFAULT_SETTINGS = {
  remember: false, uiLang: 'both', aiDefault: true, gatewayKey: '',
  cerebrasKey: '', cerebrasModel: 'gpt-oss-120b', anthropicKey: '', anthropicModel: 'claude-sonnet-4-5',
  openaiKey: '', openaiBase: 'https://api.openai.com/v1', openaiModel: 'gpt-4o-mini',
  order: 'cerebras,anthropic,openai_compat',
};
function loadSettings() {
  const raw = localStorage.getItem(SETTINGS_KEY) || sessionStorage.getItem(SETTINGS_KEY);
  try { return { ...DEFAULT_SETTINGS, ...(raw ? JSON.parse(raw) : {}) }; } catch { return { ...DEFAULT_SETTINGS }; }
}
let SETTINGS = loadSettings();
function saveSettings(next) {
  SETTINGS = { ...SETTINGS, ...next };
  const raw = JSON.stringify(SETTINGS);
  localStorage.removeItem(SETTINGS_KEY); sessionStorage.removeItem(SETTINGS_KEY);
  (SETTINGS.remember ? localStorage : sessionStorage).setItem(SETTINGS_KEY, raw);
  // the language choice is not a secret: keep it across sessions either way
  localStorage.setItem('bvs-ui-lang', SETTINGS.uiLang);
}
if (localStorage.getItem('bvs-ui-lang')) SETTINGS.uiLang = localStorage.getItem('bvs-ui-lang');
function byokHeaders() {
  const h = {}, S = SETTINGS;
  if (S.cerebrasKey) { h['X-BVS-Cerebras-Key'] = S.cerebrasKey; if (S.cerebrasModel) h['X-BVS-Cerebras-Model'] = S.cerebrasModel; }
  if (S.anthropicKey) { h['X-BVS-Anthropic-Key'] = S.anthropicKey; if (S.anthropicModel) h['X-BVS-Anthropic-Model'] = S.anthropicModel; }
  if (S.openaiKey) { h['X-BVS-OpenAI-Key'] = S.openaiKey; h['X-BVS-OpenAI-Base'] = S.openaiBase; h['X-BVS-OpenAI-Model'] = S.openaiModel; }
  if (S.order && S.order !== DEFAULT_SETTINGS.order) h['X-BVS-Provider-Order'] = S.order;
  return h;
}
const hasOwnKey = () => !!(SETTINGS.cerebrasKey || SETTINGS.anthropicKey || SETTINGS.openaiKey);

/* bilingual text helper: uiLang = 'en' | 'hi' | 'both' */
function t(en, hi) {
  const L = SETTINGS.uiLang;
  if (L === 'en') return en;
  if (L === 'hi') return `<span class="hi">${hi}</span>`;
  return `${en}<span class="hi-sub">${hi}</span>`;
}

async function api(path, opts = {}) {
  const res = await fetch(CFG.apiBase + path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', 'X-API-Key': SETTINGS.gatewayKey || CFG.apiKey, ...byokHeaders(), ...(opts.headers || {}) },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  const ct = res.headers.get('content-type') || '';
  return ct.includes('json') ? res.json() : res.text();
}
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n) => (n == null ? '–' : Number(n).toLocaleString('en-IN'));

/* ---------------- shell ---------------- */
const ROUTES = {
  ask: ['Ask the rulebook', renderAsk, 'नियम पूछें', '💬'],
  dashboard: ['Dashboard', renderDashboard, 'डैशबोर्ड', '📊'],
  rules: ['Rule explorer', renderRules, 'नियम खोजें', '📚'],
  calculators: ['Calculators', renderCalculators, 'कैलकुलेटर', '🧮'],
  summaries: ['Summaries', renderSummaries, 'सारांश', '📝'],
  reports: ['Reports & accuracy', renderReports, 'रिपोर्ट व सटीकता', '📈'],
  integrate: ['API & integrate', renderIntegrate, 'API व जोड़ें', '🔌'],
  settings: ['Settings & API keys', renderSettings, 'सेटिंग्स व API कुंजी', '⚙️'],
  guide: ['How to use', renderGuide, 'उपयोग गाइड', '🧭'],
};

/* one-line help shown at the top of every page (dismissible), in English and Hindi */
const PAGE_HELP = {
  ask: ['Type a question in English or Hindi, or tap a sample. The answer shows the rule number, the PDF page and the exact quote. Green “✓ verified quote” means the text was matched word-for-word in the rulebook.',
        'अंग्रेज़ी या हिंदी में सवाल लिखें या कोई नमूना सवाल चुनें। जवाब में नियम संख्या, PDF पेज और नियम का असली पाठ दिखेगा। हरा “✓ verified quote” मतलब पाठ नियम-पुस्तिका से शब्दशः मिलाया गया है।'],
  dashboard: ['Live usage: how many questions, how many answered vs “not found”, which language, which AI provider answered, and which rules are asked about most.',
              'लाइव उपयोग: कितने सवाल आए, कितनों का जवाब मिला और कितने “नियम में नहीं”, कौन सी भाषा, किस AI ने जवाब दिया, और कौन से नियम सबसे ज़्यादा पूछे गए।'],
  rules: ['Browse all 106 rules or search a word (e.g. “balcony”, “fee”). Click a rule to read its full text, its PDF page and any later amendment.',
          'सभी 106 नियम देखें या कोई शब्द खोजें (जैसे “balcony”, “fee”)। किसी नियम पर क्लिक करें: पूरा पाठ, PDF पेज और बाद का संशोधन दिखेगा।'],
  calculators: ['Enter the street width, plot area or built-up area to get the exact open space or fee from the rule tables. No AI is used, so numbers are always the table value.',
                'सड़क की चौड़ाई, प्लॉट या निर्मित क्षेत्रफल डालें: नियम-तालिका से सटीक खुली जगह या फीस मिलेगी। इसमें AI का उपयोग नहीं होता, इसलिए संख्या हमेशा तालिका वाली ही होगी।'],
  summaries: ['Pick a rule and a language to get a short plain-language summary with its key numbers. With an AI key it is written by the AI; without one it is extracted from the text.',
              'नियम और भाषा चुनें: मुख्य संख्याओं के साथ आसान भाषा में छोटा सारांश मिलेगा। AI कुंजी हो तो AI लिखता है, नहीं तो पाठ से निकाला जाता है।'],
  reports: ['Accuracy on the 17 official sample questions, plus questions that were not found or low-confidence. Run the evaluation again or download all questions as CSV.',
            '17 आधिकारिक नमूना सवालों पर सटीकता, साथ में “नहीं मिला” और कम-भरोसे वाले सवाल। मूल्यांकन दोबारा चलाएं या सभी सवाल CSV में डाउनलोड करें।'],
  integrate: ['For other portals and developers: copy the cURL / JavaScript example or the one-line widget, and test the public API live.',
              'दूसरे पोर्टल और डेवलपर के लिए: cURL / JavaScript उदाहरण या एक-लाइन विजेट कॉपी करें और पब्लिक API को लाइव जांचें।'],
  settings: ['Add your own AI key (Cerebras recommended) so answers are written by AI. Keys stay in this browser and are sent only with your own requests.',
             'अपनी AI कुंजी (Cerebras सुझाई गई) डालें ताकि जवाब AI लिखे। कुंजी सिर्फ़ इसी ब्राउज़र में रहती है और केवल आपके अपने अनुरोधों के साथ भेजी जाती है।'],
  guide: ['Everything this app can do, where to click for it, and how to read the results.', 'यह ऐप क्या-क्या कर सकता है, किस काम के लिए कहाँ जाएं, और नतीजे कैसे पढ़ें।'],
};
function helpBanner(route) {
  const h = PAGE_HELP[route];
  if (!h || localStorage.getItem('bvs-hide-help-' + route)) return '';
  return `<div class="help-banner card p-4 mb-5 flex gap-3 items-start" id="help-banner">
    <div class="text-xl">💡</div>
    <div class="flex-1 text-sm leading-relaxed">${t(h[0], h[1])}
      ${route !== 'guide' ? `<a href="#/guide" class="block mt-1 text-xs underline text-brand-600 dark:text-brand-300">${t('Full guide →', 'पूरी गाइड →')}</a>` : ''}</div>
    <button class="text-slate-400 hover:text-slate-600 text-lg leading-none" title="Hide" data-hide-help="${route}">×</button>
  </div>`;
}

function router() {
  charts.splice(0).forEach((c) => c.destroy());
  const [route, arg] = (location.hash.replace(/^#\/?/, '') || 'ask').split('/');
  const r = ROUTES[route] ? route : 'ask';
  const [title, fn, titleHi] = ROUTES[r];
  $('#page-title').innerHTML = SETTINGS.uiLang === 'hi' ? titleHi : SETTINGS.uiLang === 'en' ? title : `${title} <span class="text-slate-400 font-normal text-sm">· ${titleHi}</span>`;
  document.querySelectorAll('.nav-link').forEach((a) => a.classList.toggle('active', a.dataset.route === r));
  view.innerHTML = '';
  view.className = 'px-4 md:px-8 py-6 max-w-7xl mx-auto fade-in';
  Promise.resolve(fn(arg ? decodeURIComponent(arg) : undefined)).finally(() => {
    const banner = helpBanner(r);
    if (banner) {
      view.insertAdjacentHTML('afterbegin', banner);
      const b = view.querySelector('[data-hide-help]');
      if (b) b.onclick = () => { localStorage.setItem('bvs-hide-help-' + r, '1'); $('#help-banner').remove(); };
    }
  });
}
function renderNav() {
  const groups = [['Use', 'उपयोग', ['ask', 'rules', 'calculators', 'summaries']], ['Monitor', 'निगरानी', ['dashboard', 'reports']],
                  ['Set up', 'सेटअप', ['settings', 'integrate', 'guide']]];
  const html = groups.map(([g, gh, items]) => `<div class="nav-group">${SETTINGS.uiLang === 'hi' ? gh : g}${SETTINGS.uiLang === 'both' ? ' · ' + gh : ''}</div>` +
    items.map((k) => { const [en, , hi, ic] = ROUTES[k];
      return `<a href="#/${k}" data-route="${k}" class="nav-link"><span>${ic}</span><span class="leading-4">${SETTINGS.uiLang === 'hi' ? hi : en}${SETTINGS.uiLang === 'both' ? `<span class="block text-[11px] opacity-70 font-normal">${hi}</span>` : ''}</span></a>`; }).join('')).join('');
  $('#nav').innerHTML = html;
  $('#mobile-nav-inner').innerHTML = html;
  document.querySelectorAll('[data-lang]').forEach((b) => b.classList.toggle('on', b.dataset.lang === SETTINGS.uiLang));
}
window.addEventListener('hashchange', router);

function initShell() {
  if (new URLSearchParams(location.search).get('embed')) document.body.classList.add('embed');
  const pref = localStorage.getItem('bvs-theme');
  if (pref === 'dark' || (!pref && matchMedia('(prefers-color-scheme: dark)').matches)) document.documentElement.classList.add('dark');
  $('#theme-toggle').onclick = () => {
    const d = document.documentElement.classList.toggle('dark');
    localStorage.setItem('bvs-theme', d ? 'dark' : 'light');
    router();
  };
  renderNav();
  document.querySelectorAll('[data-lang]').forEach((b) => (b.onclick = () => { saveSettings({ uiLang: b.dataset.lang }); renderNav(); router(); }));
  $('#menu-btn').onclick = () => $('#mobile-nav').classList.remove('hidden');
  $('#help-btn').onclick = () => (location.hash = '#/guide');
  refreshHealth();
  setInterval(refreshHealth, 30000);
  router();
  if (!localStorage.getItem('bvs-welcomed')) showWelcome();
}

function showWelcome() {
  const steps = [
    ['💬', 'Ask', 'पूछें', 'Type a building-rule question in English or Hindi on “Ask the rulebook”.', '“नियम पूछें” पेज पर अंग्रेज़ी या हिंदी में भवन-नियम का सवाल लिखें।'],
    ['📑', 'Check the rule', 'नियम जांचें', 'Every answer shows the rule number, PDF page and exact quote. Click the rule badge or “PDF p.” to verify.', 'हर जवाब में नियम संख्या, PDF पेज और असली पाठ होता है। जांचने के लिए नियम बैज या “PDF p.” पर क्लिक करें।'],
    ['⚙️', 'Turn on AI (optional)', 'AI चालू करें (वैकल्पिक)', 'Add a free Cerebras key in Settings for fuller AI-written answers. Without it the app still answers from the rules and calculators.', 'पूरे AI जवाबों के लिए सेटिंग्स में मुफ़्त Cerebras कुंजी डालें। इसके बिना भी ऐप नियमों और कैलकुलेटर से जवाब देता है।'],
  ];
  const el = document.createElement('div');
  el.id = 'welcome';
  el.className = 'fixed inset-0 z-50 grid place-items-center bg-black/50 p-4';
  el.innerHTML = `<div class="card bg-white dark:bg-ink max-w-lg w-full p-6 fade-in">
    <div class="flex items-center gap-3"><div class="logo h-10 w-10 rounded-xl grid place-items-center text-white font-extrabold">भू</div>
      <div><div class="font-extrabold text-lg">Welcome · स्वागत है</div><div class="text-xs text-slate-500">Bhumi Vikas Sahayak in 3 steps · 3 कदमों में</div></div></div>
    <ol class="mt-5 space-y-4">${steps.map(([ic, en, hi, d, dh], i) => `<li class="flex gap-3"><div class="step-num">${i + 1}</div><div>
      <div class="font-semibold">${ic} ${en} · ${hi}</div><div class="text-sm text-slate-600 dark:text-slate-300">${d}</div><div class="text-sm text-slate-500 hi">${dh}</div></div></li>`).join('')}</ol>
    <div class="mt-6 flex flex-wrap gap-2 justify-end">
      <button class="btn btn-ghost" data-w="guide">🧭 Full guide · पूरी गाइड</button>
      <button class="btn btn-ghost" data-w="settings">⚙️ Add AI key · कुंजी डालें</button>
      <button class="btn btn-primary" data-w="ask">Start asking · शुरू करें</button>
    </div></div>`;
  document.body.append(el);
  el.querySelectorAll('[data-w]').forEach((b) => (b.onclick = () => { localStorage.setItem('bvs-welcomed', '1'); el.remove(); location.hash = '#/' + b.dataset.w; }));
}

async function refreshHealth() {
  try {
    const h = await api('/health');
    const live = h.providers.find((p) => p.configured && p.status === 'up' && p.name !== 'offline');
    $('#health-text').textContent = `${h.rules} rules · ${live ? live.name : 'offline mode'}`;
    $('.dot').className = 'dot up';
    $('#provider-pill').innerHTML = `<div class="font-semibold mb-1">AI providers · AI सेवाएं</div>` + h.providers.map((p) =>
      `<div class="flex items-center justify-between py-0.5"><span>${p.name}${p.source === 'your key' ? ' <span class="text-[10px] text-brand-600 dark:text-brand-300">(your key)</span>' : ''}</span><span class="badge ${badgeColor(p.status)}">${p.status.replace('_', ' ')}</span></div>`).join('') +
      (live ? '' : `<a href="#/settings" class="block mt-2 text-[11px] underline text-brand-600 dark:text-brand-300">+ Add an AI key · AI कुंजी जोड़ें</a>`);
  } catch (e) {
    $('#health-text').textContent = 'API unreachable';
    $('.dot').className = 'dot down';
  }
}
function badgeColor(s) {
  return { up: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300', degraded: 'bg-amber-100 text-amber-700', not_configured: 'bg-slate-200 text-slate-600 dark:bg-white/10 dark:text-slate-300' }[s] || 'bg-slate-200 text-slate-600';
}

/* ---------------- Ask ---------------- */
function renderAsk() {
  view.innerHTML = `
  <div class="card hero p-6 md:p-8 mb-6">
    <div class="flex flex-wrap items-start gap-6">
      <div class="flex-1 min-w-[260px]">
        <div class="badge bg-brand-100 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300 mb-3">BMC building-permission counter</div>
        <h2 class="text-2xl md:text-3xl font-extrabold tracking-tight">Ask the rulebook. <span class="grad-text">Get the rule number.</span></h2>
        <p class="mt-2 text-slate-600 dark:text-slate-300 max-w-2xl">English या हिंदी में पूछें। Every answer cites the rule, the page and the exact text, computes table numbers in code, and says <b>“not found”</b> when the rules are silent.</p>
      </div>
      <div class="grid grid-cols-3 gap-3 text-center text-xs">
        <div class="card p-3"><div class="text-xl font-extrabold">106</div>rules indexed</div>
        <div class="card p-3"><div class="text-xl font-extrabold">108</div>PDF pages</div>
        <div class="card p-3"><div class="text-xl font-extrabold" id="acc-mini">–</div>sample accuracy</div>
      </div>
    </div>
    <form id="ask-form" class="mt-6 flex flex-col md:flex-row gap-3">
      <textarea id="q" rows="2" class="input flex-1 resize-none" placeholder="e.g. My plot is 200 sq m on a 9 m road. How much gap at the front, and what fee?"></textarea>
      <div class="flex md:flex-col gap-2">
        <button class="btn btn-primary justify-center flex-1" type="submit">Ask ↵</button>
        <label class="text-xs flex items-center gap-2 justify-center"><input type="checkbox" id="use-llm" ${SETTINGS.aiDefault ? 'checked' : ''}> AI composer</label>
      </div>
    </form>
    <div class="mt-4 flex flex-wrap gap-2" id="samples">${SAMPLES.map((s) => `<button class="chip" data-q="${esc(s)}">${esc(s.length > 70 ? s.slice(0, 68) + '…' : s)}</button>`).join('')}</div>
  </div>
  <div id="ai-hint"></div>
  <div id="answers" class="space-y-5"></div>`;
  api('/health').then((h) => {
    const live = h.providers.some((p) => p.configured && p.status === 'up' && p.name !== 'offline');
    if (!live) $('#ai-hint').innerHTML = `<div class="card p-4 mb-5 text-sm flex flex-wrap items-center gap-3 border-amber-200">
      <span>🔌 ${t('Running in offline mode: answers come from rule text and calculators only.', 'ऑफ़लाइन मोड: जवाब सिर्फ़ नियम-पाठ और कैलकुलेटर से।')}</span>
      <a href="#/settings" class="btn btn-ghost ml-auto">⚙️ ${t('Add AI key', 'AI कुंजी डालें')}</a></div>`;
  }).catch(() => {});
  api('/eval').then((r) => { if (r.accuracy != null) $('#acc-mini').textContent = Math.round(r.accuracy * 100) + '%'; }).catch(() => {});
  $('#samples').onclick = (e) => { const b = e.target.closest('.chip'); if (b) { $('#q').value = b.dataset.q; ask(); } };
  $('#ask-form').onsubmit = (e) => { e.preventDefault(); ask(); };
  $('#q').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); } });
  const hist = JSON.parse(sessionStorage.getItem('bvs-hist') || '[]');
  hist.slice(0, 5).forEach((r) => $('#answers').append(answerCard(r)));
}

async function ask() {
  const q = $('#q').value.trim();
  if (!q) return;
  const holder = document.createElement('div');
  holder.className = 'card p-6';
  holder.innerHTML = `<div class="text-sm font-semibold mb-3">${esc(q)}</div><div class="space-y-2"><div class="skeleton h-4 w-3/4"></div><div class="skeleton h-4 w-2/3"></div><div class="skeleton h-4 w-1/2"></div></div>
    <div class="text-xs text-slate-400 mt-3">Agents working: language → scope guard → tools → retriever → amendments → composer → verifier</div>`;
  $('#answers').prepend(holder);
  try {
    const r = await api('/ask', { method: 'POST', body: JSON.stringify({ question: q, use_llm: $('#use-llm').checked }) });
    holder.replaceWith(answerCard(r));
    const hist = JSON.parse(sessionStorage.getItem('bvs-hist') || '[]');
    hist.unshift(r); sessionStorage.setItem('bvs-hist', JSON.stringify(hist.slice(0, 10)));
    $('#q').value = '';
  } catch (e) {
    holder.innerHTML = `<div class="text-red-600 text-sm">Request failed: ${esc(e.message)}</div>`;
  }
}

function answerCard(r) {
  const el = document.createElement('div');
  el.className = 'card p-6 fade-in';
  const conf = { high: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300', medium: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300', low: 'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300' }[r.confidence] || '';
  const calcs = (r.calculations || []).filter((c) => c.value != null).map((c) => `
    <div class="rounded-xl p-4 bg-gradient-to-br from-brand-50 to-white dark:from-brand-500/10 dark:to-transparent border border-brand-100 dark:border-brand-500/20">
      <div class="text-[11px] uppercase tracking-wide text-slate-500">${esc(c.tool.replaceAll('_', ' '))}</div>
      <div class="text-2xl font-extrabold">${c.unit === 'INR' ? '₹' + fmt(c.value) : esc(c.value) + ' ' + esc(c.unit)}</div>
      <div class="text-xs text-slate-500">Rule ${esc(c.sub_rule)} · p.${c.page}${c.table_row ? ' · ' + esc(c.table_row) : ''}</div>
    </div>`).join('');
  const amends = (r.amendments || []).map((a) => `
    <div class="quote amend"><div class="text-xs font-semibold text-amber-700 dark:text-amber-300 mb-1">⚠ Amendment ${esc(a.date)} · Rule ${esc(a.sub_rule)}</div>
    ${esc(r.language === 'hi' ? a.summary_hi : a.summary)}<div class="text-[11px] mt-1 text-slate-500">${esc(a.verification)} ${(a.sources || []).map((s) => `<a class="underline" target="_blank" href="${esc(s.url)}">${esc(s.name)}</a>`).join(' · ')}</div></div>`).join('');
  const cites = (r.citations || []).map((c) => `
    <div class="quote"><div class="flex flex-wrap items-center gap-2 mb-1">
      <a href="#/rules/${encodeURIComponent(c.rule)}" class="badge bg-brand-600 text-white">Rule ${esc(c.sub_rule || c.rule)}</a>
      <span class="text-xs text-slate-500">${esc(c.title || '')}</span>
      <a href="${esc(c.pdf_url)}" target="_blank" class="text-xs underline text-brand-600 dark:text-brand-300 ml-auto">PDF p.${esc(c.page)} ↗</a>
      ${c.verified ? '<span class="badge bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">✓ verified quote</span>' : ''}
    </div><div class="font-mono text-[12.5px]">“${esc(c.quote)}”</div></div>`).join('');
  const trace = (r.trace || []).map((s) => `<div class="step"><span class="badge bg-slate-100 dark:bg-white/10">${esc(s.step)}</span><span class="text-slate-400">${s.ms} ms</span><span class="truncate text-slate-500">${esc(traceDetail(s))}</span></div>`).join('');
  el.innerHTML = `
    <div class="flex flex-wrap items-start gap-3">
      <div class="text-sm font-semibold flex-1">${esc(r.question)}</div>
      ${r.not_found ? '<span class="badge bg-slate-800 text-white">NOT FOUND IN RULES</span>' : ''}
      <span class="badge ${conf}">${esc(r.confidence)} confidence</span>
      <span class="badge bg-slate-100 dark:bg-white/10">${esc(r.provider)}${r.model ? ' · ' + esc(r.model) : ''}</span>
      <span class="badge bg-slate-100 dark:bg-white/10">${r.latency_ms} ms</span>
    </div>
    <div class="mt-3 text-[15px] leading-relaxed ${r.language === 'hi' ? 'font-[Noto_Sans_Devanagari]' : ''}">${esc(r.answer)}</div>
    ${r.follow_up ? `<div class="mt-2 text-sm text-brand-700 dark:text-brand-300">↳ ${esc(r.follow_up)}</div>` : ''}
    ${calcs ? `<div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">${calcs}</div>` : ''}
    ${amends ? `<div class="mt-4 space-y-2">${amends}</div>` : ''}
    ${cites ? `<div class="mt-4 space-y-2">${cites}</div>` : ''}
    <div class="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
      <span>${esc(r.rules_version || '')}</span>
      <span class="ml-auto">Helpful?</span>
      <button class="btn-ghost rounded-lg px-2 py-1" data-fb="1">👍</button><button class="btn-ghost rounded-lg px-2 py-1" data-fb="0">👎</button>
      <button class="btn-ghost rounded-lg px-2 py-1" data-copy>Copy for citizen</button>
      <details class="w-full"><summary class="cursor-pointer select-none">Agent trace</summary><div class="mt-2">${trace}</div></details>
    </div>`;
  el.querySelectorAll('[data-fb]').forEach((b) => (b.onclick = async () => {
    if (!r.query_id) return; await api('/feedback', { method: 'POST', body: JSON.stringify({ query_id: r.query_id, helpful: b.dataset.fb === '1' }) });
    b.parentElement.querySelectorAll('[data-fb]').forEach((x) => (x.disabled = true)); b.classList.add('bg-brand-100');
  }));
  el.querySelector('[data-copy]').onclick = () => {
    const txt = `${r.answer}\n\n${(r.citations || []).map((c) => `Rule ${c.sub_rule || c.rule}, PDF page ${c.page}: "${c.quote}"`).join('\n')}\n(${r.rules_version})`;
    navigator.clipboard.writeText(txt);
  };
  return el;
}
function traceDetail(s) {
  const { step, ms, ...rest } = s;
  if (rest.hits) rest.hits = rest.hits.map((h) => `R${h.rule}@p${h.page}`).join(' ');
  return Object.entries(rest).map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`).join('  ');
}

/* ---------------- Dashboard ---------------- */
async function renderDashboard() {
  view.innerHTML = `<div class="grid grid-cols-2 lg:grid-cols-4 gap-4" id="kpis">${'<div class="card p-5"><div class="skeleton h-8 w-20"></div></div>'.repeat(4)}</div>
  <div class="grid lg:grid-cols-3 gap-4 mt-4">
    <div class="card p-5 lg:col-span-2"><div class="font-semibold mb-3">Questions over time</div><canvas id="c-time" height="110"></canvas></div>
    <div class="card p-5"><div class="font-semibold mb-3">Answer outcome</div><canvas id="c-outcome" height="200"></canvas></div>
    <div class="card p-5"><div class="font-semibold mb-3">Language</div><canvas id="c-lang" height="200"></canvas></div>
    <div class="card p-5"><div class="font-semibold mb-3">AI provider used</div><canvas id="c-prov" height="200"></canvas></div>
    <div class="card p-5"><div class="font-semibold mb-3">Most cited rules</div><canvas id="c-rules" height="200"></canvas></div>
    <div class="card p-5 lg:col-span-2"><div class="font-semibold mb-3">Provider health &amp; fallback chain</div><div id="prov-table"></div></div>
    <div class="card p-5"><div class="font-semibold mb-3">API consumers (gateway)</div><div id="consumers" class="text-sm"></div></div>
  </div>`;
  let s;
  try { s = await api('/stats'); } catch (e) { view.innerHTML = `<div class="card p-6 text-red-600">${esc(e.message)}</div>`; return; }
  const kpi = (label, val, sub) => `<div class="card p-5"><div class="text-xs text-slate-500">${label}</div><div class="kpi">${val}</div><div class="text-xs text-slate-400">${sub || ''}</div></div>`;
  $('#kpis').innerHTML =
    kpi('Questions answered', fmt(s.total_queries), `${fmt(s.answered)} answered · ${fmt(s.not_found)} not found`) +
    kpi('Median latency', `${fmt(s.latency_ms.p50)} ms`, `p95 ${fmt(s.latency_ms.p95)} ms`) +
    kpi('Sample-set accuracy', s.eval ? Math.round(s.eval.accuracy * 100) + '%' : '–', s.eval ? `${s.eval.score}/${s.eval.questions} · ${s.eval.mode} · ${s.eval.run_at}` : 'run it in Reports') +
    kpi('Helpful rate', s.helpful_rate == null ? '–' : Math.round(s.helpful_rate * 100) + '%', 'from clerk 👍 / 👎');
  const dark = document.documentElement.classList.contains('dark');
  Chart.defaults.color = dark ? '#cbd5e1' : '#475569';
  Chart.defaults.borderColor = dark ? 'rgba(255,255,255,.08)' : 'rgba(15,23,42,.06)';
  const palette = ['#2f86ff', '#7c3aed', '#ff9f1c', '#10b981', '#ef4444', '#06b6d4', '#a3a3a3'];
  const mk = (id, cfg) => charts.push(new Chart($(id), cfg));
  mk('#c-time', { type: 'line', data: { labels: s.timeline.map((t) => t.bucket.slice(5)), datasets: [{ label: 'questions', data: s.timeline.map((t) => t.count), fill: true, tension: 0.35, borderColor: '#2f86ff', backgroundColor: 'rgba(47,134,255,.15)' }] }, options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
  const doughnut = (id, obj) => mk(id, { type: 'doughnut', data: { labels: Object.keys(obj), datasets: [{ data: Object.values(obj), backgroundColor: palette, borderWidth: 0 }] }, options: { cutout: '65%', plugins: { legend: { position: 'bottom' } } } });
  doughnut('#c-outcome', { answered: s.answered, 'not found': s.not_found });
  doughnut('#c-lang', Object.fromEntries(Object.entries(s.languages).map(([k, v]) => [k === 'hi' ? 'Hindi' : 'English', v])));
  doughnut('#c-prov', s.providers);
  mk('#c-rules', { type: 'bar', data: { labels: s.top_rules.map((r) => 'Rule ' + r.rule), datasets: [{ data: s.top_rules.map((r) => r.count), backgroundColor: '#7c3aed', borderRadius: 6 }] }, options: { indexAxis: 'y', plugins: { legend: { display: false } } } });
  $('#prov-table').innerHTML = `<table class="table w-full"><thead><tr><th>#</th><th>Provider</th><th>Status</th><th>Models</th><th>Calls</th><th>Failures</th><th>Avg ms</th></tr></thead><tbody>
    ${s.providers_health.map((p, i) => `<tr><td>${i + 1}</td><td class="font-semibold">${esc(p.name)}</td><td><span class="badge ${badgeColor(p.status)}">${esc(p.status)}</span></td><td class="text-xs">${esc(p.models.join(', '))}</td><td>${p.calls}</td><td>${p.failures}</td><td>${p.avg_latency_ms}</td></tr>`).join('')}
  </tbody></table><p class="text-xs text-slate-500 mt-2">Requests try providers top-down. A failing provider is skipped for 60 s (circuit breaker). Offline mode always answers using calculators and verified extractive citations.</p>`;
  try {
    const u = await fetch('/gateway/usage', { headers: { 'X-API-Key': CFG.apiKey } }).then((r) => r.json());
    $('#consumers').innerHTML = `<div class="text-xs text-slate-500 mb-2">Mode: ${esc(u.mode)} · limit ${u.rate_limit_per_min}/min per key</div>` +
      (u.consumers.length ? u.consumers.map((c) => `<div class="flex justify-between py-1 border-b border-slate-100 dark:border-white/5"><span>${esc(c.name)}</span><span>${c.requests} req · ${c.avg_ms} ms · ${c.errors} err</span></div>`).join('') : 'No traffic yet');
  } catch { $('#consumers').textContent = 'Gateway usage unavailable'; }
}

/* ---------------- Rules ---------------- */
async function renderRules(ruleId) {
  view.innerHTML = `<div class="grid lg:grid-cols-[360px,1fr] gap-4">
    <div class="card p-4 h-[calc(100vh-9rem)] flex flex-col">
      <input id="rule-filter" class="input mb-3" placeholder="Filter rules or search text…" />
      <div id="rule-list" class="overflow-auto text-sm flex-1"></div>
    </div>
    <div class="card p-6 min-h-[60vh]" id="rule-detail"><div class="text-slate-500">Pick a rule to read it with its page references, or search the full text.</div></div>
  </div>`;
  const { parts } = await api('/parts');
  const draw = (f = '') => {
    const fl = f.toLowerCase();
    $('#rule-list').innerHTML = parts.map((p) => {
      const rules = p.rules.filter((r) => !fl || r.rule.toLowerCase() === fl || r.title.toLowerCase().includes(fl));
      if (!rules.length) return '';
      return `<div class="mt-3 mb-1 text-[11px] uppercase tracking-wide text-slate-400">${esc(p.part)} · pp.${p.pages}</div>` +
        rules.map((r) => `<a href="#/rules/${encodeURIComponent(r.rule)}" class="flex gap-2 py-1.5 px-2 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 ${r.rule === ruleId ? 'bg-brand-50 dark:bg-brand-500/10 font-semibold' : ''}"><span class="w-10 text-slate-400">${esc(r.rule)}</span><span class="flex-1">${esc(r.title)}</span><span class="text-xs text-slate-400">p.${r.page_start}</span></a>`).join('');
    }).join('');
  };
  draw();
  let t;
  $('#rule-filter').oninput = (e) => {
    draw(e.target.value);
    clearTimeout(t);
    if (e.target.value.length > 3) t = setTimeout(() => fullSearch(e.target.value), 350);
  };
  if (ruleId) showRule(ruleId);
}
async function fullSearch(q) {
  const { results } = await api('/search?q=' + encodeURIComponent(q) + '&k=8');
  $('#rule-detail').innerHTML = `<div class="font-semibold mb-3">Full-text search: “${esc(q)}”</div>` + results.map((r) =>
    `<a href="#/rules/${encodeURIComponent(r.rule)}" class="block quote mb-2 hover:opacity-80"><div class="text-xs mb-1"><span class="badge bg-brand-600 text-white">Rule ${esc(r.rule)}</span> ${esc(r.title)} · p.${r.page} · score ${r.score}</div><div class="font-mono text-xs">${esc(r.snippet)}…</div></a>`).join('');
}
async function showRule(id) {
  const r = await api('/rules/' + encodeURIComponent(id));
  $('#rule-detail').innerHTML = `
    <div class="flex flex-wrap items-center gap-2">
      <span class="badge bg-brand-600 text-white text-sm">Rule ${esc(r.rule)}</span>
      <h2 class="text-xl font-bold">${esc(r.title)}</h2>
      <a class="ml-auto btn btn-ghost" target="_blank" href="${esc(r.pdf_url)}">Open PDF p.${r.page_start} ↗</a>
      <button class="btn btn-primary" id="sum-btn">✨ Summarise</button>
    </div>
    <div class="text-xs text-slate-500 mt-1">${esc(r.part)} · PDF pages ${r.page_start}–${r.page_end}</div>
    ${(r.amendments || []).map((a) => `<div class="quote amend mt-3"><b>Amended ${esc(a.date)} (${esc(a.sub_rule)}):</b> ${esc(a.summary)}</div>`).join('')}
    <div id="sum-box"></div>
    <div class="rule-text mt-4 max-h-[65vh] overflow-auto">${esc(r.text)}</div>`;
  $('#sum-btn').onclick = async () => {
    $('#sum-box').innerHTML = '<div class="skeleton h-16 mt-3"></div>';
    const s = await api('/summaries/rule/' + encodeURIComponent(id));
    $('#sum-box').innerHTML = summaryBox(s);
  };
}
function summaryBox(s) {
  return `<div class="mt-3 rounded-xl p-4 bg-gradient-to-br from-violet-50 to-white dark:from-violet-500/10 dark:to-transparent border border-violet-100 dark:border-violet-500/20">
    <div class="text-xs text-violet-700 dark:text-violet-300 font-semibold mb-1">Summary · ${esc(s.provider)} ${esc(s.model || '')}</div>
    <div class="text-sm">${esc(s.summary)}</div>
    ${s.key_numbers?.length ? `<ul class="list-disc ml-5 mt-2 text-sm">${s.key_numbers.map((k) => `<li>${esc(k)}</li>`).join('')}</ul>` : ''}
    ${s.watch_out ? `<div class="text-xs mt-2 text-amber-700 dark:text-amber-300">⚠ ${esc(s.watch_out)}</div>` : ''}</div>`;
}

/* ---------------- Calculators ---------------- */
function renderCalculators() {
  view.innerHTML = `<p class="text-sm text-slate-500 mb-4">Table lookups done in code, transcribed from the official PDF. Each result cites its rule, row and page.</p>
  <div class="grid lg:grid-cols-3 gap-4">
    <form class="card p-5 space-y-3" id="f-front"><div class="font-semibold">Front open space · Rule 56(1)(a)</div>
      <label class="text-xs">Street width (m)<input name="street_width_m" type="number" step="0.1" value="9" class="input mt-1"></label>
      <label class="text-xs">Building height (m, optional)<input name="height_m" type="number" step="0.1" value="9" class="input mt-1"></label>
      <button class="btn btn-primary w-full justify-center">Calculate</button><div class="out"></div></form>
    <form class="card p-5 space-y-3" id="f-rear"><div class="font-semibold">Rear open space · Rule 56(2)(a)</div>
      <label class="text-xs">Plot area (sq m)<input name="plot_area_sqm" type="number" step="1" value="200" class="input mt-1"></label>
      <label class="text-xs">Building height (m, optional)<input name="height_m" type="number" step="0.1" class="input mt-1"></label>
      <button class="btn btn-primary w-full justify-center">Calculate</button><div class="out"></div></form>
    <form class="card p-5 space-y-3" id="f-fee"><div class="font-semibold">Building permission fee · Rule 21</div>
      <label class="text-xs">Built-up area (sq m)<input name="built_up_sqm" type="number" step="1" value="180" class="input mt-1"></label>
      <label class="text-xs">Use<select name="use" class="input mt-1"><option value="residential">Residential</option><option value="shop_cum_residence">Shop-cum-residence</option><option value="commercial">Commercial / shop</option><option value="institutional">Social / educational</option></select></label>
      <label class="text-xs">Height (m, optional; &gt;30 m = high-rise)<input name="height_m" type="number" step="0.1" class="input mt-1"></label>
      <button class="btn btn-primary w-full justify-center">Calculate</button><div class="out"></div></form>
  </div>`;
  const bind = (id, path) => ($(id).onsubmit = async (e) => {
    e.preventDefault();
    const p = new URLSearchParams([...new FormData(e.target)].filter(([, v]) => v !== ''));
    const r = await api(path + '?' + p);
    e.target.querySelector('.out').innerHTML = `<div class="mt-2 rounded-xl p-4 bg-brand-50 dark:bg-brand-500/10">
      <div class="text-2xl font-extrabold">${r.value == null ? '—' : r.unit === 'INR' ? '₹' + fmt(r.value) : r.value + ' ' + r.unit}</div>
      <div class="text-sm mt-1">${esc(r.explanation)}</div><div class="text-sm mt-1 text-slate-500">${esc(r.explanation_hi)}</div>
      <div class="text-xs mt-2"><a class="underline" href="#/rules/${r.rule}">Rule ${esc(r.sub_rule)}</a> · p.${r.page}</div>
      ${(r.warnings || []).map((w) => `<div class="text-xs text-amber-700 mt-1">⚠ ${esc(w)}</div>`).join('')}</div>`;
  });
  bind('#f-front', '/calc/front-open-space'); bind('#f-rear', '/calc/rear-open-space'); bind('#f-fee', '/calc/permission-fee');
}

/* ---------------- Summaries ---------------- */
async function renderSummaries() {
  view.innerHTML = `<div class="grid lg:grid-cols-3 gap-4">
    <div class="card p-5 lg:col-span-3" id="amend-box"></div>
    <div class="card p-5 lg:col-span-2"><div class="font-semibold mb-3">The rulebook at a glance</div><div id="parts-box" class="space-y-3"></div></div>
    <div class="card p-5"><div class="font-semibold mb-3">Counter cheat-sheet</div>
      <ul class="text-sm space-y-2">
        <li><b>Front open space</b> (≤12.5 m): ≤9 m road 3.0 m · 9–12 m 3.6 m · 12–18 m 4.5 m · &gt;18 m 6.0 m <span class="text-xs text-slate-400">R56(1)(a) p.77</span></li>
        <li><b>Rear open space</b>: ≤40 sq m nil · ≤150 1.5 m · ≤225 2.5 m · &gt;225 3.0 m <span class="text-xs text-slate-400">R56(2)(a) p.78</span></li>
        <li><b>Fees</b>: application ₹1/sq m + slab ₹750 … ₹50,000; high-rise ₹10/sq m <span class="text-xs text-slate-400">R21 pp.35–37</span></li>
        <li><b>Validity</b>: 3 years, 2 × 1-year revalidations, 5-year cap <span class="text-xs text-slate-400">R23 p.41</span></li>
        <li><b>No reply</b>: deemed sanctioned after the Sec 30(5) period <span class="text-xs text-slate-400">R28 pp.48–49</span></li>
        <li><b>Electric lines (LT)</b>: 2.5 m vertical, 1.2 m horizontal <span class="text-xs text-slate-400">R52 p.69</span></li>
        <li><b>Farm house</b>: min 0.40 ha, FAR 0.10 <span class="text-xs text-slate-400">R17 p.34</span></li>
        <li><b>Lifts</b>: above 12.5 m, NBC Part VIII Sec 5 <span class="text-xs text-slate-400">R83 pp.95–97</span></li>
        <li><b>Conflicts</b>: Development Plan prevails <span class="text-xs text-slate-400">R103 p.107</span></li>
      </ul></div>
  </div>`;
  const [{ amendments, base_version }, { parts }] = await Promise.all([api('/amendments'), api('/parts')]);
  $('#amend-box').innerHTML = `<div class="flex items-center gap-2 mb-2"><div class="font-semibold">Version &amp; amendments tracker</div><span class="badge bg-slate-100 dark:bg-white/10">${esc(base_version)}</span></div>` +
    amendments.map((a) => `<div class="quote amend"><b>${esc(a.date)} · Rule ${esc(a.sub_rule)} · ${esc(a.title)}</b><div class="text-sm mt-1">${esc(a.summary)}</div><div class="text-sm mt-1 text-slate-500">${esc(a.summary_hi)}</div><div class="text-xs mt-1">${esc(a.old_text_note || '')}</div><div class="text-xs mt-1 text-slate-500">${esc(a.verification)}</div></div>`).join('');
  $('#parts-box').innerHTML = parts.map((p, i) => `<details class="rounded-xl border border-slate-100 dark:border-white/10 p-3" ${i === 0 ? 'open' : ''}>
    <summary class="cursor-pointer font-semibold text-sm">${esc(p.part)} <span class="text-xs text-slate-400 font-normal">· ${p.count} rules · pp.${p.pages}</span></summary>
    <div class="mt-2 grid sm:grid-cols-2 gap-1 text-sm">${p.rules.map((r) => `<button class="text-left hover:text-brand-600 py-0.5" data-sum="${esc(r.rule)}"><span class="text-slate-400 w-8 inline-block">${esc(r.rule)}</span>${esc(r.title)}</button>`).join('')}</div>
    <div class="sum-slot"></div></details>`).join('');
  $('#parts-box').onclick = async (e) => {
    const b = e.target.closest('[data-sum]'); if (!b) return;
    const slot = b.closest('details').querySelector('.sum-slot');
    slot.innerHTML = '<div class="skeleton h-16 mt-3"></div>';
    const s = await api('/summaries/rule/' + encodeURIComponent(b.dataset.sum));
    slot.innerHTML = `<div class="text-xs mt-3 font-semibold">Rule ${esc(s.rule)} · ${esc(s.title)} · pp.${s.page_start}–${s.page_end} <a class="underline" href="#/rules/${esc(s.rule)}">read</a></div>` + summaryBox(s);
  };
}

/* ---------------- Reports ---------------- */
async function renderReports() {
  view.innerHTML = `<div class="grid lg:grid-cols-3 gap-4">
    <div class="card p-5 lg:col-span-3"><div class="flex flex-wrap items-center gap-3">
      <div><div class="font-semibold">Accuracy on the 17 official sample questions</div><div class="text-xs text-slate-500">Score 1 = right rule + every expected number (or a correct “not found”); 0.5 = right rule only.</div></div>
      <div class="ml-auto flex gap-2"><button class="btn btn-ghost" id="run-off">Run offline</button><button class="btn btn-primary" id="run-llm">Run with AI</button></div></div>
      <div id="eval-box" class="mt-4"></div></div>
    <div class="card p-5 lg:col-span-2"><div class="flex items-center mb-3"><div class="font-semibold">Query log</div><a class="ml-auto btn btn-ghost" id="csv">⬇ CSV</a></div><div id="log-box" class="overflow-auto max-h-[60vh]"></div></div>
    <div class="card p-5"><div class="font-semibold mb-3">Operational summary</div><div id="sum-report" class="text-sm space-y-3"></div></div>
  </div>`;
  const drawEval = (r) => {
    if (!r || r.accuracy == null) { $('#eval-box').innerHTML = '<div class="text-sm text-slate-500">No run yet.</div>'; return; }
    $('#eval-box').innerHTML = `<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
      ${[['Accuracy', Math.round(r.accuracy * 100) + '%'], ['Rule hit rate', Math.round(r.rule_accuracy * 100) + '%'], ['Score', `${r.score}/${r.questions}`], ['Correct “not found”', `${r.not_found_correct}/2`], ['Avg latency', `${r.avg_latency_ms} ms`]].map(([k, v]) => `<div class="rounded-xl p-3 bg-slate-50 dark:bg-white/5"><div class="text-xs text-slate-500">${k}</div><div class="text-xl font-extrabold">${v}</div></div>`).join('')}</div>
      <div class="text-xs text-slate-500 mb-2">Mode: ${esc(r.mode)} · ${esc(r.run_at)} · ${r.duration_s}s</div>
      <div class="overflow-auto"><table class="table w-full"><thead><tr><th>#</th><th>Question</th><th>Expected</th><th>Cited</th><th>Numbers</th><th>Score</th><th>Answer</th></tr></thead><tbody>
      ${r.rows.map((x) => `<tr><td>${x.id}</td><td class="max-w-[260px]">${esc(x.question)}</td><td>${x.not_found_expected ? 'not found' : esc(x.expected_rules.join(', '))}</td><td>${x.not_found_returned ? 'not found' : esc(x.cited_rules.join(', '))}</td><td>${x.numbers_ok ? '✅' : '—'}</td>
      <td><span class="badge ${x.score === 1 ? 'bg-emerald-100 text-emerald-700' : x.score ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-700'}">${x.score}</span></td><td class="text-xs max-w-[380px]">${esc(x.answer.slice(0, 220))}</td></tr>`).join('')}
      </tbody></table></div>`;
  };
  api('/eval').then(drawEval).catch(() => drawEval(null));
  const run = async (llm) => { $('#eval-box').innerHTML = '<div class="skeleton h-24"></div>'; drawEval(await api('/eval/run?use_llm=' + llm, { method: 'POST' })); };
  $('#run-off').onclick = () => run(false); $('#run-llm').onclick = () => run(true);
  $('#csv').onclick = async (e) => { e.preventDefault(); const t = await api('/queries.csv'); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t], { type: 'text/csv' })); a.download = 'bvs_queries.csv'; a.click(); };
  const { queries } = await api('/queries?limit=200');
  $('#log-box').innerHTML = queries.length ? `<table class="table w-full"><thead><tr><th>Time</th><th>Lang</th><th>Question</th><th>Rules</th><th>Outcome</th><th>Provider</th><th>ms</th></tr></thead><tbody>${queries.map((q) => `<tr><td class="text-xs whitespace-nowrap">${new Date(q.ts * 1000).toLocaleString()}</td><td>${q.language}</td><td class="max-w-[280px]">${esc(q.question)}</td><td>${esc(q.rules.join(', '))}</td><td>${q.not_found ? 'not found' : esc(q.confidence)}</td><td class="text-xs">${esc(q.provider)}</td><td>${Math.round(q.latency_ms)}</td></tr>`).join('')}</tbody></table>` : '<div class="text-sm text-slate-500">No questions yet.</div>';
  const s = await api('/reports/summary');
  $('#sum-report').innerHTML = `
    <div><div class="text-xs text-slate-500">Generated</div>${esc(s.generated_at)}</div>
    <div><div class="text-xs text-slate-500">Usage</div>${fmt(s.usage.total_queries)} questions · ${fmt(s.usage.answered)} answered · ${fmt(s.usage.not_found)} not found · p50 ${s.usage.latency_ms.p50} ms</div>
    <div><div class="text-xs text-slate-500">Quality</div>${s.quality.eval ? `Sample accuracy ${Math.round(s.quality.eval.accuracy * 100)}% (${esc(s.quality.eval.mode)})` : 'Not evaluated yet'} · helpful ${s.quality.helpful_rate == null ? '–' : Math.round(s.quality.helpful_rate * 100) + '%'}</div>
    <div><div class="text-xs text-slate-500">Coverage</div>Top rules: ${s.coverage.top_rules.map((r) => 'R' + r.rule + '×' + r.count).join(', ') || '–'} · ${s.coverage.amendments_tracked} amendment(s) tracked</div>
    <div><div class="text-xs text-slate-500">Gaps to review (not found)</div>${s.gaps.unanswered_questions.map((q) => `<div class="text-xs">• ${esc(q)}</div>`).join('') || '–'}</div>`;
}

/* ---------------- Integrate ---------------- */
function renderIntegrate() {
  const origin = location.origin;
  view.innerHTML = `<div class="grid lg:grid-cols-2 gap-4">
    <div class="card p-5 lg:col-span-2"><div class="font-semibold">One API for every portal</div>
      <p class="text-sm text-slate-500 mt-1">The gateway exposes a versioned, key-protected REST API. MPSeDC, BMC e-Nagarpalika, a WhatsApp bot or a mobile app can call it directly. Full OpenAPI contract at <a class="underline" href="/docs" target="_blank">/docs</a>.</p>
      <div class="grid md:grid-cols-4 gap-3 mt-4 text-sm">
        ${[['POST /v1/ask', 'Answer a question (en/hi) with citations'], ['GET /v1/search?q=', 'Full-text rule search'], ['GET /v1/rules/{id}', 'Rule text + amendments'], ['GET /v1/calc/*', 'Setback & fee calculators']].map(([a, b]) => `<div class="rounded-xl p-3 bg-slate-50 dark:bg-white/5"><div class="font-mono text-xs font-semibold">${a}</div><div class="text-xs text-slate-500 mt-1">${b}</div></div>`).join('')}
      </div></div>
    <div class="card p-5"><div class="font-semibold mb-2">cURL</div><pre class="code">curl -X POST ${origin}/v1/ask \\
  -H "X-API-Key: YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"question":"200 sq m plot on 9 m road: front gap?"}'</pre>
      <div class="font-semibold mt-4 mb-2">JavaScript</div><pre class="code">const r = await fetch("${origin}/v1/ask", {
  method: "POST",
  headers: { "X-API-Key": KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ question, language: "hi" })
}).then(r => r.json());
console.log(r.answer, r.citations);</pre></div>
    <div class="card p-5"><div class="font-semibold mb-2">Embed the widget in any portal</div><pre class="code">&lt;script src="${origin}/widget.js"
        data-api-base="${origin}"&gt;&lt;/script&gt;</pre>
      <p class="text-xs text-slate-500 mt-2">Adds a floating “भूमि विकास सहायक” button that opens the assistant in a panel.</p>
      <div class="font-semibold mt-4 mb-2">Response shape</div><pre class="code">{
  "answer": "...", "language": "en|hi", "not_found": false,
  "confidence": "high|medium|low",
  "citations": [{ "rule": "56", "sub_rule": "56(1)(a)", "page": 77,
                  "quote": "...", "verified": true, "pdf_url": "..." }],
  "calculations": [...], "amendments": [...],
  "provider": "cerebras", "model": "gpt-oss-120b",
  "rules_version": "...", "latency_ms": 640, "trace": [...]
}</pre></div>
    <div class="card p-5 lg:col-span-2"><div class="font-semibold mb-2">Try it live</div>
      <div class="flex gap-2"><input id="try-q" class="input" value="What is the rear open space for a 150 sq m plot?"><button id="try-btn" class="btn btn-primary">Send</button></div>
      <pre class="code mt-3 max-h-96" id="try-out">// response appears here</pre></div>
  </div>`;
  $('#try-btn').onclick = async () => {
    $('#try-out').textContent = '…';
    const r = await api('/ask', { method: 'POST', body: JSON.stringify({ question: $('#try-q').value }) });
    const { trace, ...rest } = r;
    $('#try-out').textContent = JSON.stringify(rest, null, 2);
  };
}

/* ---------------- Settings ---------------- */
function renderSettings() {
  const S = SETTINGS;
  const field = (id, label, labelHi, val, opts = {}) => `<label class="block">
      <span class="text-sm font-semibold">${label}</span> <span class="text-xs text-slate-500 hi">${labelHi}</span>
      <div class="relative mt-1"><input id="${id}" class="input pr-20 ${opts.mono ? 'font-mono text-sm' : ''}" type="${opts.secret ? 'password' : 'text'}" value="${esc(val)}" placeholder="${esc(opts.ph || '')}" autocomplete="off" spellcheck="false">
      ${opts.secret ? `<button type="button" class="absolute right-2 top-1/2 -translate-y-1/2 text-xs btn-ghost rounded-lg px-2 py-1" data-reveal="${id}">Show</button>` : ''}</div>
      ${opts.help ? `<span class="text-xs text-slate-500 mt-1 block">${opts.help}</span>` : ''}</label>`;
  view.innerHTML = `<div class="grid lg:grid-cols-3 gap-4">
    <div class="lg:col-span-2 space-y-4">
      <div class="card p-5">
        <div class="flex items-center gap-2"><div class="text-lg">⚡</div><div class="font-semibold">Cerebras <span class="badge bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">${t('Recommended · fastest', 'सुझाया गया · सबसे तेज़')}</span></div></div>
        <p class="text-xs text-slate-500 mt-1">${t('Get a free key: cloud.cerebras.ai → sign in → API Keys → Create. It starts with “csk-”.', 'मुफ़्त कुंजी: cloud.cerebras.ai → साइन इन → API Keys → Create। यह “csk-” से शुरू होती है।')}</p>
        <div class="grid md:grid-cols-[1fr,220px] gap-3 mt-3">
          ${field('cerebrasKey', 'API key', 'API कुंजी', S.cerebrasKey, { secret: true, mono: true, ph: 'csk-…' })}
          <label class="block"><span class="text-sm font-semibold">Model</span> <span class="text-xs text-slate-500 hi">मॉडल</span>
            <select id="cerebrasModel" class="input mt-1">${['gpt-oss-120b', 'llama-3.3-70b', 'qwen-3-32b', 'llama3.1-8b'].map((m) => `<option ${m === S.cerebrasModel ? 'selected' : ''}>${m}</option>`).join('')}</select></label>
        </div>
      </div>
      <details class="card p-5" ${S.anthropicKey || S.openaiKey ? 'open' : ''}>
        <summary class="font-semibold cursor-pointer select-none">🛟 ${t('Backup providers (optional)', 'बैकअप सेवाएं (वैकल्पिक)')}</summary>
        <p class="text-xs text-slate-500 mt-1">${t('Used automatically, in order, when Cerebras fails or is slow.', 'Cerebras फ़ेल या धीमा होने पर क्रम से अपने-आप उपयोग होंगी।')}</p>
        <div class="grid md:grid-cols-[1fr,220px] gap-3 mt-4">
          ${field('anthropicKey', 'Anthropic (Claude) key', 'Anthropic कुंजी', S.anthropicKey, { secret: true, mono: true, ph: 'sk-ant-…' })}
          ${field('anthropicModel', 'Model', 'मॉडल', S.anthropicModel, { mono: true })}
        </div>
        <div class="grid md:grid-cols-3 gap-3 mt-4">
          ${field('openaiKey', 'OpenAI-compatible key', 'OpenAI-संगत कुंजी', S.openaiKey, { secret: true, mono: true, ph: 'sk-…' })}
          ${field('openaiBase', 'Base URL (https)', 'बेस URL', S.openaiBase, { mono: true, help: 'OpenAI, Groq, OpenRouter…' })}
          ${field('openaiModel', 'Model', 'मॉडल', S.openaiModel, { mono: true })}
        </div>
        <label class="block mt-4"><span class="text-sm font-semibold">${t('Fallback order', 'फ़ॉलबैक क्रम')}</span>
          <select id="order" class="input mt-1">${['cerebras,anthropic,openai_compat', 'cerebras,openai_compat,anthropic', 'anthropic,cerebras,openai_compat', 'openai_compat,cerebras,anthropic'].map((o) => `<option value="${o}" ${o === S.order ? 'selected' : ''}>${o.replaceAll(',', ' → ')} → offline</option>`).join('')}</select></label>
      </details>
      <details class="card p-5" ${S.gatewayKey ? 'open' : ''}>
        <summary class="font-semibold cursor-pointer select-none">🔑 ${t('Gateway API key (partners & admins)', 'गेटवे API कुंजी (पार्टनर व एडमिन)')}</summary>
        <p class="text-xs text-slate-500 mt-1">${t('Leave empty to use the built-in web key. Enter a partner or admin key to test exactly what that portal sees.', 'खाली छोड़ें तो वेब की अपनी कुंजी लगेगी। किसी पार्टनर/एडमिन कुंजी से जांचें कि वह पोर्टल क्या देखता है।')}</p>
        <div class="mt-3">${field('gatewayKey', 'X-API-Key', 'X-API-Key', S.gatewayKey, { secret: true, mono: true, ph: 'bvs-demo-key' })}</div>
      </details>
      <div class="card p-5 space-y-3">
        <div class="font-semibold">🎛 ${t('Preferences', 'पसंद')}</div>
        <label class="flex items-center gap-3 text-sm"><input type="checkbox" id="aiDefault" ${S.aiDefault ? 'checked' : ''}> ${t('Use AI composer by default on Ask', 'Ask पेज पर AI composer डिफ़ॉल्ट चालू रखें')}</label>
        <label class="flex items-center gap-3 text-sm"><input type="checkbox" id="remember" ${S.remember ? 'checked' : ''}> ${t('Remember my keys on this device (otherwise they are cleared when this tab closes)', 'इस डिवाइस पर कुंजी याद रखें (नहीं तो टैब बंद होते ही हट जाएंगी)')}</label>
        <div class="text-sm">${t('Interface language', 'इंटरफ़ेस भाषा')}:
          <span class="inline-flex gap-1 ml-2">${[['en', 'English'], ['hi', 'हिंदी'], ['both', 'Both · दोनों']].map(([k, l]) => `<button type="button" class="chip ${S.uiLang === k ? 'chip-on' : ''}" data-setlang="${k}">${l}</button>`).join('')}</span></div>
      </div>
      <div class="flex flex-wrap gap-2">
        <button id="save" class="btn btn-primary">💾 ${t('Save', 'सेव करें')}</button>
        <button id="test" class="btn btn-ghost">🧪 ${t('Save & test connection', 'सेव करके जांचें')}</button>
        <button id="clear" class="btn btn-ghost text-rose-600">🗑 ${t('Remove all keys', 'सभी कुंजी हटाएं')}</button>
        <span id="save-msg" class="text-sm text-emerald-600 self-center"></span>
      </div>
      <div id="test-out" class="space-y-2"></div>
    </div>
    <div class="space-y-4">
      <div class="card p-5 text-sm space-y-2">
        <div class="font-semibold">🔒 ${t('Where do my keys go?', 'मेरी कुंजी कहाँ जाती है?')}</div>
        <p>${t('Keys are saved only in this browser. They travel with your own requests (as X-BVS-* headers) to this app’s server, which uses them for that one request and never stores or logs them.', 'कुंजी सिर्फ़ इसी ब्राउज़र में सेव होती है। यह आपके अनुरोध के साथ (X-BVS-* हेडर में) सर्वर तक जाती है, जो उसे सिर्फ़ उसी अनुरोध के लिए उपयोग करता है: न सेव करता है, न लॉग।')}</p>
        <p class="text-xs text-slate-500">${t('On a shared counter computer, leave “Remember” off and click “Remove all keys” when done.', 'साझा कंप्यूटर पर “याद रखें” बंद रखें और काम के बाद “सभी कुंजी हटाएं” दबाएं।')}</p>
      </div>
      <div class="card p-5 text-sm space-y-2">
        <div class="font-semibold">🧭 ${t('How answers are made', 'जवाब कैसे बनते हैं')}</div>
        <ol class="list-decimal pl-5 space-y-1 text-slate-600 dark:text-slate-300">
          <li>${t('Numbers from tables are always calculated in code.', 'तालिका की संख्याएं हमेशा कोड से गणना होती हैं।')}</li>
          <li>${t('The AI only words the answer, using retrieved rule text.', 'AI सिर्फ़ मिले हुए नियम-पाठ से जवाब के शब्द लिखता है।')}</li>
          <li>${t('Every quote is checked against the rulebook before you see it.', 'हर उद्धरण दिखाने से पहले नियम-पुस्तिका से मिलाया जाता है।')}</li>
          <li>${t('No key or AI down → offline mode still answers with citations.', 'कुंजी नहीं या AI बंद → ऑफ़लाइन मोड फिर भी हवाले के साथ जवाब देता है।')}</li>
        </ol>
      </div>
      <div class="card p-5 text-sm"><div class="font-semibold mb-2">📡 ${t('Live provider status', 'लाइव सेवा स्थिति')}</div><div id="set-health" class="space-y-1"></div></div>
    </div>
  </div>`;
  const ids = ['cerebrasKey', 'cerebrasModel', 'anthropicKey', 'anthropicModel', 'openaiKey', 'openaiBase', 'openaiModel', 'order', 'gatewayKey'];
  const collect = () => ({ ...Object.fromEntries(ids.map((i) => [i, $('#' + i).value.trim()])), aiDefault: $('#aiDefault').checked, remember: $('#remember').checked });
  const flash = (m) => { $('#save-msg').textContent = m; setTimeout(() => { if ($('#save-msg')) $('#save-msg').textContent = ''; }, 3000); };
  const showHealth = () => api('/health').then((h) => { $('#set-health').innerHTML = h.providers.map((p) => `<div class="flex justify-between"><span>${p.name} <span class="text-[11px] text-slate-400">${p.source || ''}</span></span><span class="badge ${badgeColor(p.status)}">${p.status.replace('_', ' ')}</span></div>`).join(''); }).catch(() => {});
  view.querySelectorAll('[data-reveal]').forEach((b) => (b.onclick = () => { const i = $('#' + b.dataset.reveal); i.type = i.type === 'password' ? 'text' : 'password'; b.textContent = i.type === 'password' ? 'Show' : 'Hide'; }));
  view.querySelectorAll('[data-setlang]').forEach((b) => (b.onclick = () => { saveSettings({ ...collect(), uiLang: b.dataset.setlang }); renderNav(); router(); }));
  $('#save').onclick = () => {
    const c = collect();
    if (c.openaiKey && !/^https:\/\//.test(c.openaiBase)) { flash(''); $('#test-out').innerHTML = `<div class="card p-3 text-sm text-rose-600">Base URL must start with https://</div>`; return; }
    saveSettings(c); flash('✓ ' + (SETTINGS.uiLang === 'hi' ? 'सेव हो गया' : 'Saved')); refreshHealth(); showHealth();
  };
  $('#test').onclick = async () => {
    saveSettings(collect()); refreshHealth();
    $('#test-out').innerHTML = `<div class="card p-4 text-sm"><div class="skeleton h-4 w-1/2"></div></div>`;
    try {
      const r = await api('/llm/test', { method: 'POST', body: '{}' });
      $('#test-out').innerHTML = r.results.map((x) => `<div class="card p-3 text-sm flex flex-wrap items-center gap-3">
        <span class="text-lg">${x.ok ? '✅' : x.source === 'none' ? '⚪' : '❌'}</span><b>${esc(x.provider)}</b>
        <span class="text-xs text-slate-500">${esc(x.source)}</span>
        <span class="${x.ok ? 'text-emerald-600' : 'text-slate-500'}">${esc(x.ok ? `${x.message} · ${x.model} · ${x.latency_ms} ms` : x.message)}</span></div>`).join('');
    } catch (e) { $('#test-out').innerHTML = `<div class="card p-3 text-sm text-rose-600">${esc(e.message)}</div>`; }
    showHealth();
  };
  $('#clear').onclick = () => {
    saveSettings({ cerebrasKey: '', anthropicKey: '', openaiKey: '', gatewayKey: '' });
    localStorage.removeItem(SETTINGS_KEY); sessionStorage.removeItem(SETTINGS_KEY);
    refreshHealth(); router();
  };
  showHealth();
}

/* ---------------- Guide ---------------- */
function renderGuide() {
  const tasks = [
    ['Answer a citizen’s question at the counter', 'काउंटर पर नागरिक के सवाल का जवाब', 'ask', 'Type it (Hindi is fine) → read the answer → tap “Copy for citizen”.', 'सवाल लिखें (हिंदी चलेगी) → जवाब पढ़ें → “Copy for citizen” दबाएं।'],
    ['Find the front / rear open space (setback)', 'आगे / पीछे की खुली जगह (सेटबैक)', 'calculators', 'Enter street width + height (front) or plot area (rear).', 'सड़क चौड़ाई + ऊंचाई (आगे) या प्लॉट क्षेत्रफल (पीछे) डालें।'],
    ['Work out the building-permission fee', 'भवन अनुज्ञा फीस निकालें', 'calculators', 'Enter built-up area and choose residential or not.', 'निर्मित क्षेत्रफल डालें और आवासीय/अन्य चुनें।'],
    ['Read the full text of a rule', 'किसी नियम का पूरा पाठ पढ़ें', 'rules', 'Search a word or rule number, then click the rule.', 'शब्द या नियम संख्या खोजें, फिर नियम पर क्लिक करें।'],
    ['Check if a rule was amended', 'नियम में संशोधन हुआ या नहीं', 'rules', 'Open the rule: amendments show in an orange box with the date and source.', 'नियम खोलें: संशोधन नारंगी बॉक्स में तारीख और स्रोत के साथ दिखता है।'],
    ['Get a short summary to brief someone', 'किसी को समझाने के लिए छोटा सारांश', 'summaries', 'Pick the rule and language → Summarise.', 'नियम और भाषा चुनें → Summarise।'],
    ['See how much the tool is being used', 'टूल का कितना उपयोग हो रहा है', 'dashboard', 'Charts by day, language, provider and most-asked rules.', 'दिन, भाषा, सेवा और सबसे पूछे गए नियमों के चार्ट।'],
    ['Prove the answers are accurate', 'जवाबों की सटीकता साबित करें', 'reports', 'See the score on 17 official questions; click “Run evaluation”.', '17 आधिकारिक सवालों पर स्कोर देखें; “Run evaluation” दबाएं।'],
    ['Download all questions asked', 'पूछे गए सभी सवाल डाउनलोड करें', 'reports', 'Click “Export CSV”.', '“Export CSV” दबाएं।'],
    ['Turn on AI answers / add my key', 'AI जवाब चालू करें / कुंजी डालें', 'settings', 'Paste your Cerebras key → “Save & test connection”.', 'Cerebras कुंजी डालें → “सेव करके जांचें”।'],
    ['Connect another portal or app', 'दूसरे पोर्टल/ऐप को जोड़ें', 'integrate', 'Copy the API example or the one-line widget.', 'API उदाहरण या एक-लाइन विजेट कॉपी करें।'],
  ];
  const badges = [
    ['<span class="badge bg-brand-600 text-white">Rule 56(1)(a)</span>', 'The rule the answer comes from. Click to open it.', 'जवाब किस नियम से है। खोलने के लिए क्लिक करें।'],
    ['<span class="text-xs underline text-brand-600">PDF p.77 ↗</span>', 'Opens the official PDF at that page.', 'आधिकारिक PDF उसी पेज पर खुलेगी।'],
    ['<span class="badge bg-emerald-100 text-emerald-700">✓ verified quote</span>', 'The quoted text was found word-for-word in the rulebook.', 'उद्धृत पाठ नियम-पुस्तिका में शब्दशः मिला।'],
    ['<span class="badge bg-emerald-100 text-emerald-700">high confidence</span>', 'High = rule + number found; medium = related rule; low = check manually.', 'High = नियम और संख्या मिली; medium = संबंधित नियम; low = खुद जांचें।'],
    ['<span class="badge bg-slate-800 text-white">NOT FOUND IN RULES</span>', 'The Rules do not cover this (e.g. property tax). Nothing is made up.', 'यह विषय नियमों में नहीं है (जैसे संपत्ति कर)। कुछ भी गढ़ा नहीं जाता।'],
    ['<span class="badge bg-amber-100 text-amber-700">⚠ Amendment</span>', 'A later change affects this rule; read it before deciding.', 'बाद के संशोधन से यह नियम बदला है; निर्णय से पहले पढ़ें।'],
    ['<span class="badge bg-slate-100">cerebras · gpt-oss-120b</span>', 'Which AI wrote the wording (or “offline”).', 'किस AI ने शब्द लिखे (या “offline”)।'],
  ];
  const faq = [
    ['Is the AI deciding my case?', 'क्या AI मेरे मामले का फ़ैसला करता है?', 'No. It points to the rule; the officer decides. Numbers come from code, not from the AI.', 'नहीं। यह नियम बताता है, निर्णय अधिकारी लेते हैं। संख्याएं कोड से आती हैं, AI से नहीं।'],
    ['Why does it say “offline mode”?', '“offline mode” क्यों दिख रहा है?', 'No AI key is set or the AI is down. Answers still come from rule text and calculators. Add a key in Settings.', 'AI कुंजी नहीं है या AI बंद है। जवाब फिर भी नियम-पाठ और कैलकुलेटर से आते हैं। सेटिंग्स में कुंजी डालें।'],
    ['How current are the rules?', 'नियम कितने ताज़ा हैं?', 'Consolidated to 6 March 2025, plus tracked amendments such as 28 August 2026 (Rule 2(5)(c)), marked “verify with Gazette”.', '6 मार्च 2025 तक समेकित, साथ में ट्रैक किए संशोधन जैसे 28 अगस्त 2026 (नियम 2(5)(c)), “गज़ट से जांचें” चिह्नित।'],
    ['Can I ask in Hindi?', 'क्या हिंदी में पूछ सकते हैं?', 'Yes. Ask in Hindi and the answer comes back in Hindi with the same rule citations.', 'हाँ। हिंदी में पूछें, जवाब हिंदी में उन्हीं नियम हवालों के साथ आएगा।'],
    ['Is citizen data stored?', 'क्या नागरिक का डेटा सेव होता है?', 'Only the question text and answer metadata, for the dashboard. Do not type names, phone or Aadhaar numbers.', 'सिर्फ़ सवाल का पाठ और जवाब की जानकारी, डैशबोर्ड के लिए। नाम, फ़ोन या आधार नंबर न लिखें।'],
  ];
  view.innerHTML = `<div class="space-y-6">
    <div class="card hero p-6"><h2 class="text-2xl font-extrabold tracking-tight">${t('How to use Bhumi Vikas Sahayak', 'भूमि विकास सहायक कैसे उपयोग करें')}</h2>
      <p class="text-sm text-slate-600 dark:text-slate-300 mt-1">${t('Pick what you want to do; the button takes you to the right page.', 'जो काम करना है चुनें; बटन आपको सही पेज पर ले जाएगा।')}</p>
      <div class="mt-4 flex flex-wrap gap-2">${[['en', 'English'], ['hi', 'हिंदी'], ['both', 'Both · दोनों']].map(([k, l]) => `<button class="chip ${SETTINGS.uiLang === k ? 'chip-on' : ''}" data-setlang="${k}">${l}</button>`).join('')}</div></div>

    <div class="card p-5"><div class="font-semibold mb-3">🎯 ${t('I want to… → go here', 'मुझे यह करना है… → यहाँ जाएं')}</div>
      <div class="grid md:grid-cols-2 gap-3">${tasks.map(([en, hi, r, how, howHi]) => `<a href="#/${r}" class="task-tile">
        <div class="text-2xl">${ROUTES[r][3]}</div><div class="flex-1"><div class="font-semibold text-sm">${t(en, hi)}</div>
        <div class="text-xs text-slate-500 mt-1">${t(how, howHi)}</div></div>
        <span class="badge bg-brand-100 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300 self-center whitespace-nowrap">${SETTINGS.uiLang === 'hi' ? ROUTES[r][2] : ROUTES[r][0]} →</span></a>`).join('')}</div></div>

    <div class="card p-5"><div class="font-semibold mb-3">🗺 ${t('Every page, explained', 'हर पेज की जानकारी')}</div>
      <div class="grid md:grid-cols-3 gap-3">${Object.keys(PAGE_HELP).filter((k) => k !== 'guide').map((k) => `<a href="#/${k}" class="rounded-xl p-4 bg-slate-50 dark:bg-white/5 hover:ring-2 ring-brand-300 block">
        <div class="font-semibold">${ROUTES[k][3]} ${t(ROUTES[k][0], ROUTES[k][2])}</div><div class="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">${t(PAGE_HELP[k][0], PAGE_HELP[k][1])}</div></a>`).join('')}</div></div>

    <div class="grid lg:grid-cols-2 gap-4">
      <div class="card p-5"><div class="font-semibold mb-3">🔎 ${t('Reading an answer card', 'जवाब कार्ड कैसे पढ़ें')}</div>
        <div class="space-y-3">${badges.map(([b, en, hi]) => `<div class="flex gap-3 items-start"><div class="w-44 shrink-0">${b}</div><div class="text-sm">${t(en, hi)}</div></div>`).join('')}</div>
        <p class="text-xs text-slate-500 mt-4">${t('Open “Agent trace” under an answer to see each of the 7 agent steps and their timings.', 'जवाब के नीचे “Agent trace” खोलें: 7 एजेंट चरण और उनका समय दिखेगा।')}</p></div>
      <div class="card p-5"><div class="font-semibold mb-3">⚙️ ${t('Turn on AI in 4 steps', '4 कदमों में AI चालू करें')}</div>
        <ol class="space-y-3">${[
          ['Open cloud.cerebras.ai and sign in (free).', 'cloud.cerebras.ai खोलें और साइन इन करें (मुफ़्त)।'],
          ['Go to API Keys → Create key, then copy it (starts with csk-).', 'API Keys → Create key, फिर कॉपी करें (csk- से शुरू)।'],
          ['Here, open ⚙️ Settings and paste it in Cerebras → API key.', 'यहाँ ⚙️ सेटिंग्स खोलें और Cerebras → API key में पेस्ट करें।'],
          ['Click “Save & test connection”. A ✅ means AI answers are on.', '“सेव करके जांचें” दबाएं। ✅ मतलब AI जवाब चालू।'],
        ].map(([en, hi], i) => `<li class="flex gap-3"><div class="step-num">${i + 1}</div><div class="text-sm">${t(en, hi)}</div></li>`).join('')}</ol>
        <a href="#/settings" class="btn btn-primary mt-4">⚙️ ${t('Open Settings', 'सेटिंग्स खोलें')}</a></div>
    </div>

    <div class="card p-5"><div class="font-semibold mb-3">❓ ${t('Common questions', 'आम सवाल')}</div>
      <div class="space-y-2">${faq.map(([q, qh, a, ah]) => `<details class="rounded-xl p-3 bg-slate-50 dark:bg-white/5"><summary class="cursor-pointer font-medium text-sm">${t(q, qh)}</summary><div class="text-sm text-slate-600 dark:text-slate-300 mt-2">${t(a, ah)}</div></details>`).join('')}</div></div>

    <div class="card p-5 text-sm"><div class="font-semibold mb-2">⌨️ ${t('Shortcuts & tips', 'शॉर्टकट व सुझाव')}</div>
      <ul class="list-disc pl-5 space-y-1 text-slate-600 dark:text-slate-300">
        <li>${t('Enter sends a question; Shift+Enter adds a new line.', 'Enter से सवाल भेजें; Shift+Enter से नई लाइन।')}</li>
        <li>${t('Give numbers in the question (plot area, road width, height) to get an exact calculation.', 'सटीक गणना के लिए सवाल में संख्या दें (प्लॉट क्षेत्रफल, सड़क चौड़ाई, ऊंचाई)।')}</li>
        <li>${t('🌗 in the sidebar switches dark mode; the EN / हिं buttons switch the interface language.', 'साइडबार में 🌗 से डार्क मोड; EN / हिं बटन से इंटरफ़ेस भाषा बदलें।')}</li>
        <li>${t('Hidden a 💡 tip? Click “Show page tips again” below.', '💡 सुझाव छिपा दिया? नीचे “सुझाव फिर दिखाएं” दबाएं।')}</li>
      </ul>
      <div class="mt-3 flex gap-2"><button class="btn btn-ghost" id="reset-tips">💡 ${t('Show page tips again', 'सुझाव फिर दिखाएं')}</button><button class="btn btn-ghost" id="replay-welcome">👋 ${t('Replay welcome tour', 'स्वागत टूर फिर देखें')}</button></div></div>
  </div>`;
  view.querySelectorAll('[data-setlang]').forEach((b) => (b.onclick = () => { saveSettings({ uiLang: b.dataset.setlang }); renderNav(); router(); }));
  $('#reset-tips').onclick = () => { Object.keys(PAGE_HELP).forEach((k) => localStorage.removeItem('bvs-hide-help-' + k)); router(); };
  $('#replay-welcome').onclick = () => showWelcome();
}

initShell();
