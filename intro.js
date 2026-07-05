/* Entry screens (title page + descriptive-use notice), shared by every page.
 *
 * Shown whenever the visitor ENTERS the site — on whichever page they land —
 * but not when they navigate between the site's own tabs. Internal links carry
 * the class .tabs-link; clicking one sets a one-shot sessionStorage flag that
 * the next page load consumes to skip the intro.
 *
 * Also owns the shared language preference ("bsd_lang"): the intro's toggle and
 * the map tool's panel toggle both route through here. */
(function () {
  // mark internal navigation (links exist before this script runs)
  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a.tabs-link");
    if (a) sessionStorage.setItem("bsd_internal_nav", "1");
  });

  /* ---- shared language state (always wired, intro or not) ---- */
  let lang = localStorage.getItem("bsd_lang") || "en";
  const btnLabel = () => lang === "en" ? "中文" : "English";
  const panelLangBtn = document.getElementById("panel-lang");   // map tool only
  let applyIntro = null;                                        // set when intro exists
  function setLang(l) {
    lang = l;
    localStorage.setItem("bsd_lang", lang);
    document.documentElement.lang = lang === "en" ? "en" : "zh-Hans";
    if (panelLangBtn) panelLangBtn.textContent = btnLabel();
    if (applyIntro) applyIntro();
  }
  const toggleLang = () => setLang(lang === "en" ? "zh" : "en");
  if (panelLangBtn) {
    panelLangBtn.textContent = btnLabel();
    panelLangBtn.addEventListener("click", toggleLang);
  }

  /* ---- intro screens: only on a fresh entry to the site ---- */
  // DEV: entry screens disabled while building — set to true to disable again.
  const INTRO_DISABLED = false; if (INTRO_DISABLED) return;

  const cameFromInside = sessionStorage.getItem("bsd_internal_nav");
  sessionStorage.removeItem("bsd_internal_nav");
  if (cameFromInside) return;                       // tab switch: no start page

  // fresh entry: the changes-tab entrance animation may play again
  sessionStorage.removeItem("bsd_changes_played");

  document.body.insertAdjacentHTML("beforeend", `
  <div id="intro" class="intro">
    <button class="intro-lang" id="intro-lang" title="Switch language">中文</button>
    <div class="intro-card" id="intro-front">
      <p class="intro-kicker" data-i18n="kicker"></p>
      <h1 class="intro-title" data-i18n="title"></h1>
      <p class="intro-sub" data-i18n="sub"></p>
      <div class="intro-byline">
        <span data-i18n="by1"></span><br />
        <span data-i18n="by2"></span>
      </div>
      <div><button class="intro-btn" id="intro-start" data-i18n="start"></button></div>
    </div>
    <div class="intro-card intro-card-notice" id="intro-notice" hidden>
      <h2 class="intro-h2" data-i18n="nHead"></h2>
      <p class="intro-p" data-i18n="n1"></p>
      <p class="intro-p" data-i18n="n2"></p>
      <p class="intro-p intro-fine" data-i18n="n3"></p>
      <button class="intro-btn" id="intro-ok" data-i18n="ok"></button>
    </div>
    <!-- version stamp, mirrored from the homepage's #site-version (empty on other pages) -->
    <div class="intro-version" style="position:absolute;left:14px;bottom:10px;font-size:11px;color:#2c3338;opacity:0.55;pointer-events:none;">${(document.getElementById("site-version") || {}).textContent || ""}</div>
  </div>`);

  const I18N = {
    en: {
      kicker: "An interactive atlas",
      title: "One District, Three Maps",
      sub: "How the Bellevue School District's attendance boundaries changed before, during, and after the 2023 elementary consolidation &mdash; and what measurably changed with them.",
      by1: "Created by Lucas Xue",
      by2: "Mentored by Prof. Bo Zhao &middot; Humanistic GIS Laboratory, University of Washington",
      start: "Start",
      nHead: "Before you start",
      n1: "<b>This tool describes; it does not judge.</b> It maps the district's attendance boundaries across three periods and reports what measurably changed with them: zone shape, enrollment and capacity, demographics, travel, and access to programs.",
      n2: "None of these numbers is a fairness score. No color on the map means good or bad, and no metric rates any school, neighborhood, or decision as right or wrong. Compactness, segregation indices, travel times, and demographic mixes are descriptive measurements; reasonable people weigh them differently, and many things that mattered in the real decision &mdash; safety, budgets, building condition, community input &mdash; are not on a map.",
      n3: "Two notes for reading the numbers: demographics in every era use the same fixed 2020 census snapshot, so differences between eras reflect boundary changes only, not population change. And the pre-2018 boundaries come from a different (federal) source and carry extra uncertainty. Full sources and methods are documented on the site.",
      ok: "I understand"
    },
    zh: {
      kicker: "交互式地图集",
      title: "一个学区，三张地图",
      sub: "贝尔维尤学区（Bellevue School District）的入学分区边界在 2023 年小学合并前后如何变化，以及随之发生了哪些可测量的改变。",
      by1: "作者：Lucas Xue",
      by2: "指导：Bo Zhao 教授 &middot; 华盛顿大学人文 GIS 实验室",
      start: "开始",
      nHead: "使用前请阅读",
      n1: "<b>本工具只做描述，不做评判。</b>它呈现学区在三个时期的入学分区边界，并报告随之可测量的变化：分区形状、招生与容量、人口构成、通勤，以及项目可达性。",
      n2: "这里没有任何数字是“公平分数”。地图上的颜色不代表好坏，任何指标都不对学校、社区或决策作出对错评价。紧凑度、隔离指数、通勤时间和人口构成都是描述性测量；不同的人对它们的权重看法不同，而真实决策中许多重要因素——安全、预算、校舍状况、社区意见——并不在地图上。",
      n3: "阅读数据的两点提示：所有时期的人口数据都使用同一份 2020 年人口普查快照，因此时期之间的差异只反映边界变化，而非人口变化；2018 年前的边界来自另一个（联邦）数据源，不确定性更高。完整的数据来源与方法在网站中另有说明。",
      ok: "我已了解"
    }
  };

  const intro = document.getElementById("intro");
  const introLangBtn = document.getElementById("intro-lang");

  applyIntro = () => {
    const t = I18N[lang] || I18N.en;
    intro.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t[el.dataset.i18n] || ""; });
    introLangBtn.textContent = btnLabel();
  };

  introLangBtn.addEventListener("click", toggleLang);
  document.getElementById("intro-start").addEventListener("click", () => {
    document.getElementById("intro-front").hidden = true;
    document.getElementById("intro-notice").hidden = false;
  });
  document.getElementById("intro-ok").addEventListener("click", () => {
    intro.classList.add("intro-fading");
    setTimeout(() => { intro.remove(); applyIntro = null; }, 500);
  });

  applyIntro();
})();
