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
  var STEPS_TO_DOOR = 12;   // characters typed before the cursor reaches the threshold
  if (ask) {
    var input = ask.elements.know;
    function scene() { return window.gigScene; }
    // The invite is a live region, so screen readers hear the message; the count beside
    // it changes several times a second and stays out of what they read.
    var count = document.createElement("span"), message = document.createElement("span");
    count.setAttribute("aria-hidden", "true");
    if (invite) invite.append(count, message);
    var said = null;
    function say(html, counted) {
      count.innerHTML = counted || "";
      if (html !== said) { said = html; message.innerHTML = html; }
    }
    function greet() {
      if (!scene()) return;
      var touch = window.matchMedia("(pointer: coarse)").matches;
      var base = scene().still ? "Every grain is a contributor looking for the way in." : "Every grain is a contributor looking for the way in. " + (touch ? "Tap the field to add people. " : "Drag through a pile to move it. ") + "Type, and more arrive. <b>Enter</b> opens the floor.";
      say(base);
      // the count inside, as the room fills: honest grains, not people
      scene().onCount(function (info) {
        if (info.entered) return;
        var n = "<b>" + info.inside.toLocaleString() + "</b>";
        if (info.full) say("The door is open. <b>Enter</b> steps in.", n + " in. ");
        else say(base, info.inside ? n + " in so far. " : "");
      });
    }
    // scene.js starts on the load event, after this deferred script has run.
    if (scene()) greet(); else window.addEventListener("load", greet);
    input.addEventListener("input", function () {
      var n = input.value.trim().length;
      if (scene()) scene().walk(n / STEPS_TO_DOOR);
      if (n >= STEPS_TO_DOOR && scene() && !scene().still) say("<b>Enter</b> to git in.");
    });
    // The first answer travels in the URL fragment, which browsers never send to a
    // server, so "your answers stay on your computer" holds. Without JavaScript the
    // form falls back to a query string.
    ask.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = input.value.trim();
      var href = ask.getAttribute("action") + (v ? "#know=" + encodeURIComponent(v) : "");
      var go = function () { location.href = href; };
      if (scene()) { say("git in."); scene().enter(go); } else go();
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
