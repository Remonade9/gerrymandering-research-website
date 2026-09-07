/* API keys for the two map pages (index.html, changes.html).
 *
 * Both services are free. If you are running your own copy of this site,
 * replace these with your own keys before deploying (see README.md):
 *
 *   maptiler  basemap tiles + address search   https://cloud.maptiler.com/
 *             (lock the key to your domain in the MapTiler dashboard)
 *   ors       routes + travel times            https://openrouteservice.org/dev/
 *             (cannot be domain-locked; rotate it if usage looks wrong)
 *
 * The pages read window.BSD_KEYS; keep the property names as they are. */
window.BSD_KEYS = {
  /* Where the keys below are meant to be used: the official site's hostname(s).
   * Anywhere else, a copy still carrying these shipped keys is asked to swap in
   * its own (they would otherwise spend the original author's free allowance).
   * LEAVE EMPTY to switch that prompt off entirely. */
  home: ["gerrymandering-research.up.railway.app"],

  maptiler: "z7fBe8Wbh3urlylwknlf",
  ors: "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImNhN2RjM2VjYzkzNDAzZTRmY2NkYjUwODM2MzdjNTRkODA1ODJiY2ZhMzM0MjQ2NGQxMzliYTc2IiwiaCI6Im11cm11cjY0In0="
};
