// The video pages (scripts/build_videos.py) show a thumbnail that links to YouTube. Pressing it
// swaps in YouTube's player, so nothing loads from YouTube until the visitor asks for the video
// (docs/privacy.md). A chapter or transcript time starts the player there. Without this script
// every one of those links still opens the video on YouTube at the right moment.
(function () {
  var box = document.querySelector(".player[data-video]");
  if (!box) return;
  var id = box.getAttribute("data-video");
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function play(at) {
    var frame = document.createElement("iframe");
    // youtube-nocookie.com is YouTube's privacy-enhanced embed. The player refuses to start
    // (error 153) without a Referer, so the policy names the one browsers send by default.
    frame.src = "https://www.youtube-nocookie.com/embed/" + id + "?autoplay=1&rel=0" + (at ? "&start=" + at : "");
    frame.title = box.getAttribute("data-title");
    frame.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
    frame.referrerPolicy = "strict-origin-when-cross-origin";
    frame.allowFullscreen = true;
    box.replaceChildren(frame);
    frame.focus();
  }

  function plain(event) {
    return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
  }

  box.addEventListener("click", function (event) {
    if (!plain(event) || !event.target.closest(".facade")) return;
    event.preventDefault();
    play(0);
  });

  document.addEventListener("click", function (event) {
    var link = event.target.closest ? event.target.closest("a[data-seek]") : null;
    if (!link || !plain(event)) return;
    event.preventDefault();
    play(Number(link.getAttribute("data-seek")) || 0);
    box.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "center" });
  });
})();
