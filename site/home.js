// The home page's own behaviour: the hero prompt that walks you through the door, the
// proof callouts that light the output lines they describe, the journey's pinned
// terminal, and the replay of a recorded run. Everything here is an enhancement: the
// page reads the same without it.
(function () {
  "use strict";
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- hero: typing walks the cursor in, Enter steps through, then start/ opens -------
  var ask = document.querySelector(".ask");
  var invite = document.querySelector("[data-invite]");
  var hud = document.querySelector("[data-hud]");
  if (ask) {
    var input = ask.elements.know;
    function scene() { return window.gigScene; }
    function say(html) { if (invite) invite.innerHTML = html; }
    var STEPS_TO_DOOR = 12;   // characters typed before the cursor reaches the threshold
    if (scene()) {
      say(scene().still ? "Type a language, and the organizations that name it light up." : "Type a language, and the organizations that name it light up. <b>Enter</b> walks you in.");
      // The names are the official organizations, written by the site build beside the page.
      fetch("doors.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
        if (j && j.doors) { scene().doors(j.doors); if (input.value) scene().light(input.value); }
      }).catch(function () {});
      // The caption under the scene counts what lit up and names the lit organization passing you.
      function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
      scene().onDoor(function (info) {
        if (!hud || !info.count) return;
        hud.hidden = false;
        var line = info.lit ? "<b>" + info.lit + "</b> of " + info.count + " organizations name what you typed" : info.count + " organizations, from the official list";
        var near = info.near ? '<br>passing <a href="orgs/' + encodeURIComponent(info.near.s) + '/">' + esc(info.near.n) + "</a>" + (info.near.y ? ' <span class="c">' + info.near.y + " year" + (info.near.y === 1 ? "" : "s") + " in GSoC</span>" : "") : "";
        hud.innerHTML = '<span class="c">' + line + "</span>" + near;
      });
    }
    input.addEventListener("input", function () {
      if (!scene()) return;
      var n = scene().light(input.value);
      scene().walk(input.value.trim().length / STEPS_TO_DOOR);
      if (!scene().still) say(n ? "<b>" + n + "</b> light up for that. <b>Enter</b> walks you in." : "Type a language, and the organizations that name it light up. <b>Enter</b> walks you in.");
    });
    // The first answer travels in the URL fragment, which browsers never send to a
    // server, so "your answers stay on your computer" holds. Without JavaScript the
    // form falls back to a query string.
    ask.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = input.value.trim();
      var href = ask.getAttribute("action") + (v ? "#know=" + encodeURIComponent(v) : "");
      var go = function () { location.href = href; };
      if (scene()) { say("git in."); if (hud) hud.hidden = true; scene().enter(go); } else go();
    });
  }

  // --- proof: a callout lights the lines it talks about --------------------------------
  var callouts = document.querySelectorAll(".callouts [data-hl]");
  var proofLines = document.querySelectorAll(".proof .ln[data-hl]");
  function light(key) {
    Array.prototype.forEach.call(proofLines, function (l) { l.classList.toggle("on", !!key && l.getAttribute("data-hl") === key); });
    Array.prototype.forEach.call(callouts, function (c) { c.classList.toggle("on", !!key && c.getAttribute("data-hl") === key); });
  }
  Array.prototype.forEach.call(callouts, function (c) {
    var key = c.getAttribute("data-hl");
    c.addEventListener("mouseenter", function () { light(key); });
    c.addEventListener("focus", function () { light(key); });
    c.addEventListener("mouseleave", function () { light(null); });
    c.addEventListener("blur", function () { light(null); });
  });

  // --- journey: one terminal stays put while the lit step's output changes inside it ---
  var steps = Array.prototype.slice.call(document.querySelectorAll(".journey > li"));
  var screenOut = document.querySelector("[data-screen-out]");
  var screenStep = document.querySelector("[data-screen-step]");
  var wide = window.matchMedia("(min-width: 1000px)");
  var shown = -1, ticking = false;
  function show(i) {
    if (i === shown || !screenOut) return;
    shown = i;
    var li = steps[i];
    var run = li.querySelector("[data-run] code");
    var name = li.querySelector("h3").textContent.toLowerCase();
    screenStep.textContent = (i < 9 ? "0" : "") + (i + 1) + " " + name;
    screenOut.innerHTML = run ? run.innerHTML : "";
    screenOut.parentNode.scrollTop = 0;
  }
  function current() {
    ticking = false;
    if (!wide.matches) return;
    var line = window.innerHeight * 0.45, pick = 0;
    for (var i = 0; i < steps.length; i++) {
      if (steps[i].getBoundingClientRect().top <= line) pick = i;
    }
    show(pick);
  }
  if (steps.length && screenOut) {
    window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(current); } }, { passive: true });
    wide.addEventListener("change", current);
    current();
  }

  // --- replay: the recorded run appears line by line, answers typed ---------------------
  var figure = document.querySelector(".replay figure");
  var out = document.querySelector("[data-replay-out]");
  var replayBtn = document.querySelector("[data-replay]");
  if (figure && out && !still) {
    var lines = Array.prototype.slice.call(out.querySelectorAll(".ln"));
    var timer = 0, played = false;
    function stop() { clearTimeout(timer); figure.classList.remove("playing"); lines.forEach(function (l) { l.classList.add("on", "done"); restore(l); }); }
    function restore(l) {
      var typed = l.querySelector(".typed");
      if (typed && typed.getAttribute("data-full")) typed.textContent = typed.getAttribute("data-full");
    }
    function play() {
      clearTimeout(timer);
      played = true;
      figure.classList.add("playing");
      lines.forEach(function (l) { l.classList.remove("on", "done"); var t = l.querySelector(".typed"); if (t) { if (!t.getAttribute("data-full")) t.setAttribute("data-full", t.textContent); t.textContent = ""; } });
      out.scrollTop = 0;
      var i = 0;
      function next() {
        if (i >= lines.length) { figure.classList.remove("playing"); return; }
        var l = lines[i++];
        l.classList.add("on");
        var typed = l.querySelector(".typed");
        if (!typed) { l.classList.add("done"); timer = setTimeout(next, 28); return; }
        var full = typed.getAttribute("data-full"), k = 0;
        function type() {
          typed.textContent = full.slice(0, ++k);
          if (k < full.length) timer = setTimeout(type, 70);
          else { l.classList.add("done"); timer = setTimeout(next, 360); }
        }
        timer = setTimeout(type, 420);
      }
      next();
    }
    if (replayBtn) { replayBtn.hidden = false; replayBtn.addEventListener("click", play); }
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting && !played) { play(); io.disconnect(); }
      }, { threshold: 0.35 });
      io.observe(figure);
    }
    document.addEventListener("visibilitychange", function () { if (document.hidden && figure.classList.contains("playing")) stop(); });
  }
})();
