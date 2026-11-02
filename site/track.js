// A few actions that page views cannot show: which install route a visitor takes, whether the
// start page gets as far as results, and which links are followed off an organization page.
// Each name answers one question listed in CONTRIBUTING.md ("Measuring the site"). Nothing a
// visitor typed is ever sent.
(function () {
  function count(name) {
    // count.js loads async; a click before it arrives is dropped, not queued.
    if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: name, event: true });
  }
  document.addEventListener("click", function (event) {
    var hit = event.target.closest ? event.target.closest("a[href], button[data-copy]") : null;
    if (!hit) return;
    if (hit.hasAttribute("data-copy")) {
      var term = hit.closest(".term");
      var shown = term && term.querySelector("pre:not([hidden])");
      count("copy/" + (shown && shown.id ? shown.id.replace("panel-", "") : "setup"));
      return;
    }
    var out = hit.getAttribute("data-out");
    if (out) count(out);
    else if (hit.host && hit.host !== location.host) count("out/" + hit.host.replace(/^www\./, ""));
  });
  var form = document.getElementById("start-form");
  var results = document.getElementById("start-results");
  if (form) form.addEventListener("submit", function () { count("start/submit"); });
  if (results) {
    // hidden flips once per visit: the first time the matcher answers.
    new MutationObserver(function () { if (!results.hidden) count("start/results"); })
      .observe(results, { attributes: true, attributeFilter: ["hidden"] });
  }
})();
