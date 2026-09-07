/* Map-tool tutorial: a slideshow popup shown over the map (index.html only).
 *
 * Opens automatically on a fresh entry to the map page, right after the entry
 * screens are dismissed (intro.js fires "bsd-intro-done"), and any time from the
 * Tutorial button beside "More tabs". Close with the X (top right), Esc, or a
 * click on the dark backdrop. Left/right arrow keys move between slides.
 *
 * Bilingual: every string is [en, zh]; the open card re-renders on the shared
 * "bsd-lang" event.
 *
 * Slides: { img: "tutorial/xx.png" | null, title: [en, zh], body: [en, zh] }.
 * Images are optional — a slide with img: null is text-only. To add one, drop
 * a screenshot into Website/tutorial/ and set its path here.
 *
 * To show the tour only on a visitor's FIRST entry instead of every entry,
 * gate the "bsd-intro-done" listener at the bottom on a localStorage flag. */
(function () {
  /* Open by itself on a fresh visit. OFF while the slide text is still being
   * written, so visitors are not shown a draft; the Tutorial button beside
   * "More tabs" opens it either way. Set to true to switch the automatic tour
   * back on. */
  const AUTO_OPEN = false;

  const SLIDES = [
    {
      img: null,
      title: ["Welcome to the map tool", "欢迎使用地图工具"],
      body: [
        "<p>This map shows the Bellevue School District's attendance zones in three periods: <b>pre-2018</b>, <b>2018&ndash;2023</b>, and <b>2023&ndash;now</b>. Every number is computed once per period from the same fixed 2020 population, so what changes between periods is the <b>boundaries</b>, not the people.</p>" +
        "<p>This short tour shows where everything is. Press <b>Next</b> (or &rarr;) to continue. Close with &#10005; at any time and come back through the <b>Tutorial</b> button at the top left.</p>",
        "<p>这张地图展示贝尔维尤学区在三个时期的入学分区：<b>2018 年前</b>、<b>2018&ndash;2023</b>、<b>2023 至今</b>。每个数字都用同一份固定的 2020 年人口在每个时期各算一遍，所以时期之间变的是<b>边界</b>，而不是人。</p>" +
        "<p>这个简短导览带你认识各项功能。点「下一步」（或按 &rarr;）继续；随时可以点 &#10005; 关闭，之后通过左上角的「使用教程」按钮回来。</p>"
      ]
    },
    {
      img: null,
      title: ["Pick a period and a school level", "选择时期和学段"],
      body: [
        "<p>The <b>panel down the left side</b> holds the controls. Its top two rows are tabs: the first switches the <b>period</b> (pre-2018 &middot; 2018&ndash;2023 &middot; 2023&ndash;now), and the one below it switches the <b>school level</b> (Elementary &middot; Middle &middot; High).</p>" +
        "<p>Only elementary boundaries changed in 2018 and 2023. Middle and high school zones are identical in every period.</p>",
        "<p><b>左侧面板</b>是各项控件所在。最上面两排是选项卡：第一排切换<b>时期</b>（2018 年前 &middot; 2018&ndash;2023 &middot; 2023 至今），下面一排切换<b>学段</b>（小学 &middot; 初中 &middot; 高中）。</p>" +
        "<p>2018 和 2023 年只有小学边界变了。初中和高中分区在各时期完全相同。</p>"
      ]
    },
    {
      img: null,
      title: ["Click any zone", "点击任意分区"],
      body: [
        "<p>Click a zone and a panel opens on the <b>right</b> with everything measured for it: enrollment and building capacity; who lives there (race, age, income, language); how far children travel to school; and the distance to the nearest Advanced Learning, dual-language, and special-education programs.</p>" +
        "<p>The small round <span class='tut-i'>i</span> buttons open a plain-words explanation of the measure beside them. Where a measure is built up from many smaller pieces, a <b>distribution</b> button appears as well &mdash; on travel to the assigned school, and on each program distance &mdash; showing how the zone's individual blocks spread out instead of only their average.</p>",
        "<p>点击一个分区，<b>右侧</b>会打开面板，列出为它测量的全部内容：在校人数与校舍容量；居民构成（族裔、年龄、收入、语言）；孩子上学要走多远；以及到最近的高阶学习、双语沉浸和特殊教育项目的距离。</p>" +
        "<p>圆形的 <span class='tut-i'>i</span> 按钮会用平实的语言解释旁边那项指标。当一项指标由许多小块汇总而成时，还会出现<b>分布</b>按钮 &mdash; 例如「到指定学校的通勤」和各个项目的距离 &mdash; 显示该分区各街区的分布情况，而不只是平均值。</p>"
      ]
    },
    {
      img: null,
      title: ["Click a school pin", "点击学校图钉"],
      body: [
        "<p><b>Red</b> pins are attendance-area schools; <b>yellow</b> pins are choice schools, which have no zone of their own. Click a pin for the school's enrollment, the makeup of its enrolled students (from the state's OSPI report card), and the programs it hosts.</p>" +
        "<p>Keep in mind: a <b>pin</b> describes the students enrolled at a school, while a <b>zone</b> describes the people who live in it. Those are different groups.</p>",
        "<p><b>红色</b>图钉是划片入学学校；<b>黄色</b>图钉是选校制学校，没有自己的分区。点击图钉可查看该校在校人数、在校学生的构成（来自州 OSPI 报告卡）以及设有的项目。</p>" +
        "<p>请记住：<b>图钉</b>描述的是在该校就读的学生，<b>分区</b>描述的是住在其中的居民，两者是不同的群体。</p>"
      ]
    },
    {
      img: null,
      title: ["Color the whole map by any measure", "按任意指标给整张地图着色"],
      body: [
        "<p>In a zone's panel, most measures have a small <b>checkbox</b> beside them. Tick one and every zone is shaded by that measure, with a legend in the <b>left panel</b>. Tick a count (like the number of children) and the zones get sized circles instead of shading.</p>" +
        "<p>Green ramps mean <i>more of something</i>. Yellow-to-red ramps are used only for travel and distance. Two-tone brown&ndash;teal ramps show values above or below a midpoint, such as a building over or under capacity. <b>No color means good or bad.</b></p>",
        "<p>在分区面板里，大多数指标旁有一个小<b>方框</b>。勾选后，每个分区都按该指标着色，图例显示在<b>左侧面板</b>中。勾选人数类指标（如儿童数）时，各分区改用大小不同的圆圈而不是着色。</p>" +
        "<p>绿色渐变表示<i>某项更多</i>；黄到红的渐变只用于通勤与距离；棕&ndash;青双色渐变表示高于或低于某个中点，例如校舍超出或未达容量。<b>颜色不代表好坏。</b></p>"
      ]
    },
    {
      img: null,
      title: ["Layers: neighborhoods and race", "图层：社区与族裔"],
      body: [
        "<p>Under <b>Layers</b> in the <b>left panel</b> are two extra views. <b>Neighborhoods</b> shades each City of Bellevue neighborhood by how many attendance zones its school-age children are split across (light = kept whole). <b>Racial composition</b> colors the 2020 census blocks by their largest group.</p>" +
        "<p>While Neighborhoods is on, the school pins are hidden for a cleaner read.</p>",
        "<p><b>左侧面板</b>的<b>图层</b>下有两个额外视图。<b>社区</b>按各社区学龄儿童被分进几个入学分区来着色（浅色 = 保持完整）；<b>族裔构成</b>把 2020 年普查街区按最大群体着色。</p>" +
        "<p>开启「社区」时，学校图钉会隐藏，方便阅读。</p>"
      ]
    },
    {
      img: null,
      title: ["Explore: what's my school?", "查一查：我家属于哪所学校？"],
      body: [
        "<p>Type an address (or click anywhere on the map) to drop a pin. The pin tells you which zone it falls in for each period, and the road distance and travel time to that school.</p>" +
        "<p>Drop a second pin and press <b>Measure a route</b> to see the route between them. <b>Travel mode</b> switches between driving and walking; <b>Distance units</b> switches between miles and kilometers.</p>",
        "<p>输入地址（或在地图任意处点击）放置图钉。图钉会告诉你它在各时期属于哪个分区，以及到该校的道路距离和通勤时间。</p>" +
        "<p>放置第二个图钉并点击<b>测量路线</b>，可查看两点之间的路线。<b>出行方式</b>在驾车与步行之间切换；<b>距离单位</b>在英里与公里之间切换。</p>"
      ]
    },
    {
      img: null,
      title: ["Zoom out: the District overview", "放大视野：学区总览"],
      body: [
        "<p><b>District overview</b>, at the top of the <b>left panel</b>, leaves individual zones behind and summarizes the whole district for the period you have selected: how evenly groups are spread across schools, the district-wide mix gap, and rankings of the schools by the makeup of their enrolled students.</p>" +
        "<p>Switch the period tabs while it is open and those district-wide figures change with them, which is the quickest way to see what each rezoning did overall.</p>",
        "<p><b>学区总览</b>位于<b>左侧面板</b>顶部。它不再看单个分区，而是汇总你所选时期的全学区情况：各群体在各校之间分布得有多均匀、全学区的构成差距，以及按在校学生构成对学校的排名。</p>" +
        "<p>打开它时切换时期选项卡，这些全学区数字会随之变化 &mdash; 这是看清每次重划整体影响最快的方式。</p>"
      ]
    },
    {
      img: null,
      title: ["Graph mode: build your own charts", "图表模式：自己动手做图"],
      body: [
        "<p><b>Graph mode</b>, the button just below District overview, opens a board that starts <b>empty</b> on purpose. Nothing is charted until you add something, using the two buttons in the dashed tile.</p>" +
        "<p><b>+ Zone chart</b> follows a single measure for the zones you choose across all three periods, so you can see whether a zone's travel time, enrollment, or demographics moved when its boundary did. You pick the school level, the zones (several can share one chart), and the measure.</p>" +
        "<p><b>+ All-zones scatter</b> takes one rezoning and plots every zone at once, with the <i>change</i> in one measure on each axis. It answers whether two things moved together &mdash; for example, whether the zones that gained students also gained travel time.</p>" +
        "<p>Each chart has an &times; to remove it, and your board is remembered in this browser, so the charts are still waiting when you come back.</p>",
        "<p><b>图表模式</b>的按钮就在「学区总览」下方。它打开的面板一开始是<b>空的</b>，这是有意为之：要先用虚线方块里的两个按钮添加图表。</p>" +
        "<p><b>+ 分区图</b>跟踪你选定的分区在三个时期里某一项指标的变化，从而看出边界变动时，该分区的通勤时间、在校人数或人口构成是否也跟着变了。可以选择学段、分区（同一张图里可以放多个）和指标。</p>" +
        "<p><b>+ 全分区散点</b>针对某一次重划，把所有分区同时画出来，两个坐标轴分别是两项指标的<i>变化量</i>。它回答的是两件事是否同步变化 &mdash; 例如，学生增加的分区，通勤时间是否也变长了。</p>" +
        "<p>每张图都有 &times; 可以移除；你的面板会记在这个浏览器里，下次回来图还在。</p>"
      ]
    },
    {
      img: null,
      title: ["Beyond the map", "地图之外"],
      body: [
        "<p>The <b>More tabs</b> menu (top left) opens the rest of the site. <b>Boundary changes</b> animates exactly which areas moved between schools in 2018 and 2023. <b>Analysis</b> walks through what was found. <b>Methods &amp; sources</b> shows how every number was computed, and <b>Definitions &amp; references</b> explains each term with a yardstick for how big is big.</p>" +
        "<p>The <b>中文</b> button at the bottom of the <b>left panel</b> switches the whole site to Chinese. Enjoy exploring.</p>",
        "<p>左上角的<b>更多页面</b>菜单通向网站的其余部分。<b>边界变更</b>动态展示 2018 和 2023 年到底哪些区域换了学校；<b>分析</b>介绍研究发现；<b>方法与来源</b>说明每个数字是怎么算出来的；<b>定义与参考</b>解释每个术语，并给出「多大算大」的参照。</p>" +
        "<p><b>左侧面板</b>底部的 <b>English</b> 按钮可将全站切换回英文。祝你探索愉快。</p>"
      ]
    }
  ];

  const UI = {
    back:  ["Back", "上一步"],
    next:  ["Next", "下一步"],
    done:  ["Done", "完成"],
    close: ["Close tutorial", "关闭教程"],
    step:  ["Step {i} of {n}", "第 {i} 步，共 {n} 步"]
  };
  const isZH = () => (localStorage.getItem("bsd_lang") || "en") === "zh";
  const t = (pair) => pair[isZH() ? 1 : 0];

  document.body.insertAdjacentHTML("beforeend", `
  <div id="tut" class="tut" hidden role="dialog" aria-modal="true" aria-labelledby="tut-title">
    <div class="tut-card">
      <div class="tut-head">
        <span class="tut-step" id="tut-step"></span>
        <button class="tut-x" id="tut-x" aria-label="Close">&times;</button>
      </div>
      <div class="tut-img" id="tut-img" hidden></div>
      <h2 class="tut-title" id="tut-title"></h2>
      <div class="tut-body" id="tut-body"></div>
      <div class="tut-foot">
        <div class="tut-dots" id="tut-dots"></div>
        <div class="tut-nav">
          <button class="tut-btn ghost" id="tut-back"></button>
          <button class="tut-btn" id="tut-next"></button>
        </div>
      </div>
    </div>
  </div>`);

  const el = (id) => document.getElementById(id);
  const tut = el("tut");
  let i = 0;

  function render() {
    const s = SLIDES[i], n = SLIDES.length;
    el("tut-step").textContent = t(UI.step).replace("{i}", i + 1).replace("{n}", n);
    const im = el("tut-img");
    if (s.img) { im.innerHTML = `<img src="${s.img}" alt="">`; im.hidden = false; }
    else { im.innerHTML = ""; im.hidden = true; }
    el("tut-title").innerHTML = t(s.title);
    el("tut-body").innerHTML = t(s.body);
    el("tut-dots").innerHTML = SLIDES.map((_, k) =>
      `<button class="tut-dot${k === i ? " is-on" : ""}" data-k="${k}" aria-label="${k + 1}"></button>`).join("");
    const back = el("tut-back"), next = el("tut-next");
    back.textContent = t(UI.back); back.disabled = i === 0;
    next.textContent = t(i === n - 1 ? UI.done : UI.next);
    el("tut-x").title = t(UI.close);
    el("tut-x").setAttribute("aria-label", t(UI.close));
    tut.querySelector(".tut-card").scrollTop = 0;
  }
  function open(k) {
    i = k || 0; render();
    tut.hidden = false;
    requestAnimationFrame(() => tut.classList.add("is-open"));
  }
  function close() {
    tut.classList.remove("is-open");
    setTimeout(() => { tut.hidden = true; }, 220);
  }
  function go(k) {
    if (k >= SLIDES.length) { close(); return; }   // "Done" on the last slide
    if (k < 0) return;
    i = k; render();
  }

  el("tut-x").addEventListener("click", close);
  el("tut-back").addEventListener("click", () => go(i - 1));
  el("tut-next").addEventListener("click", () => go(i + 1));
  el("tut-dots").addEventListener("click", (e) => {
    const d = e.target.closest(".tut-dot"); if (d) go(+d.dataset.k);
  });
  tut.addEventListener("click", (e) => { if (e.target === tut) close(); });   // backdrop
  document.addEventListener("keydown", (e) => {
    if (tut.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowRight") go(i + 1);
    else if (e.key === "ArrowLeft") go(i - 1);
  });

  // manual entry: the Tutorial button beside "More tabs"
  const btn = el("tut-btn");
  if (btn) btn.addEventListener("click", () => open(0));

  // language switch while open: redraw the current slide
  document.addEventListener("bsd-lang", () => { if (!tut.hidden) render(); });

  // automatic entry: fresh visit to the map page, once the entry screens close
  if (AUTO_OPEN) document.addEventListener("bsd-intro-done", () => { if (!window.BSD_KEY_ALERT) open(0); });
})();
