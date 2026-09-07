/* Fallback API-key prompt for the two map pages (index.html, changes.html).
 *
 * Loads AFTER config.js and BEFORE the page reads the keys. It resolves the key
 * each service will actually use (a key the visitor pasted, kept in their own
 * browser, wins over the one shipped in config.js) and rewrites window.BSD_KEYS
 * so the pages pick it up with no change on their side.
 *
 * The dialog appears only when something is actually wrong:
 *   "missing"  no key at all (a fork that blanked config.js)
 *   "bad"      the service answered 401/403: invalid key, wrong origin, or a
 *              free-tier quota that has run out
 *   "default"  the key still matches the one this project ships with, and the
 *              page is not on an official host: a copy spending someone else's
 *              allowance. Works, but asks the visitor to swap in their own.
 * Rejections are caught by watching fetch, so no page code has to report them.
 *
 * Dismissing with the X leaves a warning badge at the top of the map naming what
 * is switched off; clicking the badge brings the dialog back.
 *
 * Everything else on the site is unaffected: the zones, the schools, and every
 * measured number are served from this site's own data files, not from an API. */
(function () {
  /* ---- DEBUG ---------------------------------------------------------------
   * Set to a state name to force that dialog on entry for both services, even
   * when the keys are fine, so the design can be previewed:
   *     "default"  the "these are the author's keys" prompt
   *     "missing"  no key at all
   *     "bad"      the key was refused
   * false = normal behaviour. SET THIS BACK TO false BEFORE PUSHING. */
  const DEBUG_FORCE_SHOW = false;

  const SHIPPED = window.BSD_KEYS || {};
  const LS = { maptiler: "bsd_key_maptiler", ors: "bsd_key_ors" };
  const mine = (k) => { try { return (localStorage.getItem(LS[k]) || "").trim(); } catch (e) { return ""; } };

  // a visitor's own key wins over the shipped one
  const keys = {
    maptiler: mine("maptiler") || (SHIPPED.maptiler || "").trim(),
    ors: mine("ors") || (SHIPPED.ors || "").trim()
  };
  window.BSD_KEYS = keys;

  /* ---- "still the original author's key" test -----------------------------
   * A downloaded copy inherits the keys in config.js. MapTiler refuses them on
   * a hosted fork (origin lock), but NOT on localhost, and ORS keys cannot be
   * origin-locked at all -- so a fork can quietly spend the original free
   * allowance. Fingerprints of the shipped keys are kept here: if the key in
   * use still matches, and the page is not being served from one of the
   * official hosts in config.js, the visitor is asked to swap in their own.
   * With config.js "home" left empty the check is off, so it can never nag
   * visitors to the real site. */
  const SHIPPED_FP = { maptiler: "d0hil5", ors: "1xm34xf" };
  const fp = (s) => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0; return h.toString(36); };
  const HOME = Array.isArray(SHIPPED.home) ? SHIPPED.home : [];
  const atHome = !HOME.length || HOME.some((h) => location.hostname === h || location.hostname.endsWith("." + h));
  const isDefault = (k) => !!keys[k] && fp(keys[k]) === SHIPPED_FP[k];

  const SVC = {
    maptiler: {
      name: "MapTiler",
      url: "https://cloud.maptiler.com/account/keys/",
      host: /api\.maptiler\.com/,
      what: ["the background street map and the address search box",
             "背景街道地图和地址搜索框"],
      lost: ["Without it the area behind the zones stays blank, and typing an address will not find it.",
             "缺少它时，分区背后是空白，输入地址也无法定位。"]
    },
    ors: {
      name: "openrouteservice",
      url: "https://openrouteservice.org/dev/#/signup",
      host: /openrouteservice\.org/,
      what: ["driving and walking routes for pins you place yourself",
             "你自己放置图钉后的驾车与步行路线"],
      lost: ["Without it a pin still names its zone and school, but draws no route and shows no travel time.",
             "缺少它时，图钉仍会显示所属分区和学校，但不会画出路线，也不显示通勤时间。"]
    }
  };

  const state = {};
  for (const k in SVC) {
    state[k] = !keys[k] ? "missing"
             : (!atHome && isDefault(k)) ? "default"
             : "ok";
  }

  if (DEBUG_FORCE_SHOW) for (const k in SVC) state[k] = DEBUG_FORCE_SHOW;

  const isZH = () => (localStorage.getItem("bsd_lang") || "en") === "zh";
  const t = (p) => p[isZH() ? 1 : 0];
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

  const TXT = {
    kicker:   ["One-time setup", "一次性设置"],
    h1:       ["This copy needs an API key", "此副本需要一个 API 密钥"],
    h2:       ["This copy needs two API keys", "此副本需要两个 API 密钥"],
    lede:     ["Part of this map runs on a free outside service, and no working key was found. Paste your own free key below to switch it back on. It is stored in this browser only.",
               "地图的部分功能依赖外部的免费服务，但没有找到可用的密钥。在下面粘贴你自己的免费密钥即可恢复该功能。密钥只保存在此浏览器中。"],
    missing:  ["No key was found.", "没有找到密钥。"],
    rejected: ["The shipped key was refused. It may be out of its daily free allowance, or not valid from this address.",
               "随附的密钥被拒绝。可能是免费额度已用完，或在此地址下无效。"],
    rej_mine: ["The key you entered was refused. Check it for stray spaces, or try another.",
               "你输入的密钥被拒绝。请检查是否有多余空格，或换一个试试。"],
    powers:   ["Powers", "用于"],
    ph:       ["Paste your {s} key", "粘贴你的 {s} 密钥"],
    save:     ["Save", "保存"],
    saving:   ["Saved, reloading&hellip;", "已保存，正在重新加载……"],
    get:      ["Get a free {s} key", "获取免费的 {s} 密钥"],
    fine:     ["Everything else works without these. The zones, the schools, and every measured number on this site come from its own data files, not from an API.",
               "网站的其余部分不需要这些密钥。分区、学校以及本站所有测量数值都来自自己的数据文件，而不是 API。"],
    skip:     ["Continue without it", "暂不设置，继续"],
    close:    ["Dismiss", "关闭"],
    w_map:    ["Background map is off, no MapTiler key", "背景地图已关闭，缺少 MapTiler 密钥"],
    w_ors:    ["Routes are off, no openrouteservice key", "路线功能已关闭，缺少 openrouteservice 密钥"],
    w_both:   ["Background map and routes are off, keys missing", "背景地图与路线功能已关闭，缺少密钥"],
    w_fix:    ["Fix", "去设置"],

    d_kicker: ["Please use your own key", "请使用你自己的密钥"],
    d_h1:     ["This copy is using the author's API key", "此副本正在使用作者的 API 密钥"],
    d_h2:     ["This copy is using the author's API keys", "此副本正在使用作者的 API 密钥"],
    d_lede:   ["This looks like a copy of the site, still carrying the keys it shipped with. It works, but every visit spends the free allowance on the original author's account. Your own keys are free and take about a minute to get. Paste them below, or write them into config.js to set them for good.",
               "看起来这是本站的一个副本，仍在使用随附的密钥。它可以正常运行，但每次访问都会消耗原作者账户的免费额度。你自己的密钥是免费的，大约一分钟就能拿到。可以在下面粘贴，或写入 config.js 永久生效。"],
    d_note:   ["Still the original key, so this page is drawing on the author's free allowance.",
               "仍是原作者的密钥，因此本页正在消耗作者的免费额度。"],
    d_skip:   ["Continue anyway", "仍然继续"],
    w_def:    ["Using the site author's API keys", "正在使用网站作者的 API 密钥"]
  };

  const needy = () => Object.keys(SVC).filter(k => state[k] !== "ok");
  // a broken key is the more urgent story; "default" only when nothing is broken
  const mode = () => needy().some(k => state[k] === "missing" || state[k] === "bad") ? "broken" : "default";

  document.body.insertAdjacentHTML("beforeend", `
  <div id="keyw" class="keyw" hidden role="dialog" aria-modal="true" aria-labelledby="keyw-title">
    <div class="keyw-card" id="keyw-card">
      <button class="keyw-x" id="keyw-x">&times;</button>
      <p class="keyw-kicker"></p>
      <h2 class="keyw-title" id="keyw-title"></h2>
      <p class="keyw-lede"></p>
      <div id="keyw-list"></div>
      <p class="keyw-fine"></p>
      <button class="keyw-skip" id="keyw-skip"></button>
    </div>
  </div>
  <button id="keyw-warn" class="keyw-warn" hidden></button>`);

  const el = (id) => document.getElementById(id);
  const box = el("keyw"), warn = el("keyw-warn");
  let open = false;

  function render() {
    const list = needy(), dflt = mode() === "default";
    box.querySelector(".keyw-kicker").innerHTML = t(dflt ? TXT.d_kicker : TXT.kicker);
    el("keyw-title").innerHTML = t(dflt ? (list.length > 1 ? TXT.d_h2 : TXT.d_h1)
                                        : (list.length > 1 ? TXT.h2 : TXT.h1));
    box.querySelector(".keyw-lede").innerHTML = t(dflt ? TXT.d_lede : TXT.lede);
    box.querySelector(".keyw-fine").innerHTML = t(TXT.fine);
    el("keyw-skip").innerHTML = t(dflt ? TXT.d_skip : TXT.skip);
    el("keyw-x").title = t(TXT.close);
    el("keyw-x").setAttribute("aria-label", t(TXT.close));
    el("keyw-list").innerHTML = list.map(k => {
      const s = SVC[k], st = state[k], bad = st === "bad";
      const why = st === "default" ? t(TXT.d_note)
                : (bad ? t(mine(k) ? TXT.rej_mine : TXT.rejected) : t(TXT.missing)) + " " + t(s.lost);
      return `<div class="keyw-svc">
        <div class="keyw-svc-head"><span class="keyw-tag">${s.name}</span>
          <span class="keyw-what"><b>${t(TXT.powers)}</b> ${t(s.what)}</span></div>
        <p class="keyw-note${bad ? " keyw-bad" : ""}">${why}</p>
        <div class="keyw-row">
          <input id="keyw-in-${k}" type="text" spellcheck="false" autocomplete="off"
                 placeholder="${esc(t(TXT.ph).replace("{s}", s.name))}" value="${esc(mine(k))}" />
          <button class="keyw-save" data-k="${k}">${t(TXT.save)}</button>
        </div>
        <a class="keyw-get" href="${s.url}" target="_blank" rel="noopener">${t(TXT.get).replace("{s}", s.name)} &rarr;</a>
      </div>`;
    }).join("");
  }

  function show() {
    if (open) return;
    open = true; render();
    warn.hidden = true;
    box.hidden = false;
    requestAnimationFrame(() => box.classList.add("is-open"));
  }
  function showWarn() {
    const list = needy();
    if (!list.length) { warn.hidden = true; return; }
    const msg = mode() === "default" ? t(TXT.w_def)
              : list.length > 1 ? t(TXT.w_both)
              : t(list[0] === "maptiler" ? TXT.w_map : TXT.w_ors);
    warn.innerHTML = `<span class="keyw-warn-i" aria-hidden="true">&#9888;</span>` +
                     `<span class="keyw-warn-t">${msg}</span>` +
                     `<span class="keyw-warn-fix">${t(TXT.w_fix)}</span>`;
    warn.hidden = false;
  }
  function hide() {
    open = false;
    box.classList.remove("is-open");
    setTimeout(() => { box.hidden = true; }, 200);
    showWarn();
  }

  el("keyw-x").addEventListener("click", hide);
  el("keyw-skip").addEventListener("click", hide);
  warn.addEventListener("click", show);
  box.addEventListener("click", (e) => { if (e.target === box) hide(); });
  document.addEventListener("keydown", (e) => { if (!box.hidden && e.key === "Escape") hide(); });
  el("keyw-card").addEventListener("click", (e) => {
    const b = e.target.closest(".keyw-save"); if (!b) return;
    const k = b.dataset.k, v = (el("keyw-in-" + k).value || "").trim();
    if (!v) return;
    try { localStorage.setItem(LS[k], v); } catch (err) {}
    b.innerHTML = t(TXT.saving); b.disabled = true;
    setTimeout(() => location.reload(), 500);   // simplest way to re-init the map with the new key
  });
  document.addEventListener("bsd-lang", () => {
    if (!box.hidden) render(); else if (!warn.hidden) showWarn();
  });

  /* ---- rejection watch: catch 401/403 from either service ---- */
  function fail(k) {
    if (!SVC[k] || state[k] === "bad") return;
    state[k] = "bad";
    window.BSD_KEY_ALERT = true;
    show();
  }
  window.bsdKeyFailed = fail;                    // pages may also report a failure directly
  const origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function (...a) {
      const u = typeof a[0] === "string" ? a[0] : (a[0] && a[0].url) || "";
      return origFetch.apply(this, a).then((res) => {
        if (res && (res.status === 401 || res.status === 403)) {
          for (const k in SVC) if (SVC[k].host.test(u)) fail(k);
        }
        return res;
      });
    };
  }

  /* ---- first appearance: wait for the entry screens, as the tutorial does ---- */
  if (needy().length) {
    window.BSD_KEY_ALERT = true;                 // tutorial.js stands down while this is up
    if (document.getElementById("intro")) document.addEventListener("bsd-intro-done", show);
    else show();
  }
})();
