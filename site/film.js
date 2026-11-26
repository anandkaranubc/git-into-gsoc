// The home page film. Without this script the <video> has its own controls and works as is.
// With it, the poster shows one play button in the site's style, and the hero's "watch" link
// scrolls to the film and starts it. Nothing loads before play (preload="none"), and the film
// comes from this site, so pressing play asks no other site for anything (docs/privacy.md).
// It counts four moments, each answering a question in CONTRIBUTING.md ("Measuring the site").
(function () {
  var box = document.querySelector("[data-film]");
  if (!box) return;
  var video = box.querySelector("video");
  var button = box.querySelector("button[data-film-play]");
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var sent = {};
  function count(name) {
    if (sent[name]) return;
    sent[name] = true;
    if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: name, event: true });
  }

  video.controls = false;
  button.hidden = false;

  function play() {
    box.classList.add("playing");
    video.controls = true;
    var started = video.play();
    // A browser that refuses to start (data saver, an old engine) still leaves the controls.
    if (started && started.catch) started.catch(function () {});
    video.focus();
  }

  button.addEventListener("click", play);
  video.addEventListener("play", function () { box.classList.add("playing"); video.controls = true; count("film/play"); });
  video.addEventListener("timeupdate", function () {
    if (video.duration && video.currentTime > video.duration / 2) count("film/half");
  });
  video.addEventListener("ended", function () { count("film/end"); });

  var transcript = document.querySelector("[data-film-transcript]");
  if (transcript) transcript.addEventListener("toggle", function () { if (transcript.open) count("film/transcript"); });

  // The hero link: scroll to the film and start it. Its click is counted by track.js (data-out).
  document.querySelectorAll("a[data-film-play]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      box.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "center" });
      play();
    });
  });
})();
