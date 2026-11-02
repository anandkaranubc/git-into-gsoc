// The doorway on the home page as sand: the pixel G stands in a dark field and a crowd
// of lime grains, one per would-be contributor, pours in from the right, piles against
// the G, slides round it, and finds the way in through the door until the room is full.
// A falling-sand automaton on the brand's own grid (every cell is one pixel), with
// gravity pointing at the door. The pointer stirs the grains, typing adds to the flow,
// and Enter opens the floor so everything drains down into the page. The G never moves.
// Without a canvas the still SVG mark stays in place.
(function init() {
  "use strict";
  if (document.readyState !== "complete") { window.addEventListener("load", init); return; }
  var scene = document.querySelector(".scene");
  var hero = document.querySelector(".hero");
  if (!scene || !hero) return;
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canvas = document.createElement("canvas");
  var ctx = canvas.getContext("2d", { alpha: false });
  if (!ctx) return;

  var EMPTY = 0, WALL = 1, SAND = 2, SAND2 = 3, YOU = 4;   // two sand tones for texture; you, a 3 by 4 block
  var cols = 0, rows = 0, cell = 4, band = false, UNIT = 4;
  var grid, next, img, g = { x: 0, y: 0 };
  var gravity = "left", flow = 3, grains = 0, stir = null, entered = false, enterAt = 0;
  var start = performance.now() / 1000, last = start, visible = true, raf = 0, burst = 0;
  var roomCells = 0, inRoom = 0, you = { x: 0, y: 0, tx: 0, at: 0 }, cheer = 0, listeners = [], told = -1;
  function doorX() { return g.x + 20 * UNIT; }
  function doorY() { return g.y + 9 * UNIT; }

  // The G from scripts/brand/build.py, on the grid: six bars, four softened corners, two added cells.
  function isG(x, y) {
    if (x < 0 || y < 0 || x > 19 || y > 19) return false;
    function r(x0, y0, x1, y1) { return x >= x0 && x <= x1 && y >= y0 && y <= y1; }
    var on = r(0, 0, 3, 19) || r(0, 0, 19, 3) || r(16, 4, 19, 5) || r(10, 12, 19, 15) || r(16, 12, 19, 19) || r(0, 16, 19, 19);
    if ((x <= 1 && y === 0) || (x === 0 && y <= 1) || (x >= 18 && y === 0) || (x === 19 && y <= 1)) on = false;
    if ((x <= 1 && y === 19) || (x === 0 && y >= 18) || (x >= 18 && y === 19) || (x === 19 && y >= 18)) on = false;
    if ((x === 4 && y === 4) || (x === 4 && y === 15)) on = true;
    return on;
  }
  function inRoomUnit(x, y) { return !isG(x, y) && ((x >= 4 && x <= 19 && y >= 4 && y <= 11) || (x >= 4 && x <= 9 && y >= 12 && y <= 15)); }

  function size() {
    var W = scene.clientWidth, H = scene.clientHeight;
    if (!W || !H) return;
    band = getComputedStyle(scene).position !== "absolute";
    cell = band ? 3 : 4;
    // a resize notice with the same size (the pane scaling, a scrollbar) keeps the field
    if (Math.ceil(W / cell) === cols && Math.ceil(H / cell) === rows && grid) return;
    cols = Math.ceil(W / cell); rows = Math.ceil(H / cell);
    canvas.width = cols; canvas.height = rows;
    canvas.style.width = cols * cell + "px"; canvas.style.height = rows * cell + "px";
    ctx.imageSmoothingEnabled = false;
    UNIT = band ? 3 : 4;
    // room to the right of the door for the crowd: at least ten units of field
    g.x = band ? Math.round(cols * 0.5 - 10 * UNIT) : Math.min(cols - 32 * UNIT, Math.round(cols * 0.54));
    g.y = Math.round((rows - 20 * UNIT) / 2);
    grid = new Uint8Array(cols * rows);
    next = new Uint8Array(cols * rows);
    img = ctx.createImageData(cols, rows);
    roomCells = 0;
    for (var y = 0; y < rows; y++) for (var x = 0; x < cols; x++) {
      var ux = Math.floor((x - g.x) / UNIT), uy = Math.floor((y - g.y) / UNIT);
      if (isG(ux, uy)) grid[y * cols + x] = WALL;
      else if (inRoomUnit(ux, uy)) roomCells += 1;
    }
    grains = 0; inRoom = 0; entered = false; gravity = "left"; cheer = 0;
    // you wait outside the door, in the stream's path, until typing walks you to it
    you.x = Math.min(cols - 4 * UNIT, doorX() + 7 * UNIT); you.tx = you.x; you.y = doorY() - 2 * UNIT;
    placeYou();
    if (still) { for (var i = 0; i < 900; i++) { emit(flow); step(); } countRoom(); }   // a settled pile for a still frame
    draw();
  }

  // Grains arrive in a stream aimed at the door, not across the whole field: a band of
  // rows around the door's height, so the piles outside stay a crowd and not a flood.
  function placeYou() {
    for (var y = 0; y < rows; y++) for (var x = 0; x < cols; x++) { var i = y * cols + x; if (grid[i] === YOU) grid[i] = EMPTY; }
    for (var yy = you.y; yy < you.y + 4 * UNIT; yy++) for (var xx = you.x; xx < you.x + 3 * UNIT; xx++) {
      if (xx < 0 || yy < 0 || xx >= cols || yy >= rows) continue;
      var k = yy * cols + xx;
      if (grid[k] >= SAND) grains -= 1;
      if (grid[k] !== WALL) grid[k] = YOU;
    }
  }
  function moveYou(now) {
    if (you.x === you.tx || now - you.at < (entered ? 0.01 : 0.03)) return;
    you.at = now;
    you.x += you.tx > you.x ? 1 : -1;
    placeYou();
  }
  // A handful of grains around a point: what a tap or click drops into the field.
  function emitAt(cx, cy, n) {
    for (var k = 0; k < n * 4 && n > 0; k++) {
      var x = cx + Math.round((Math.random() - 0.5) * 10), y = cy + Math.round((Math.random() - 0.5) * 10);
      if (x < 0 || y < 0 || x >= cols || y >= rows) continue;
      var i = y * cols + x;
      if (grid[i] === EMPTY) { grid[i] = Math.random() < 0.12 ? SAND2 : SAND; grains += 1; n -= 1; }
    }
  }
  function emit(n) {
    var tries = n * 3, mid = g.y + 9 * UNIT, half = 11 * UNIT;
    while (n > 0 && tries-- > 0) {
      var y = mid + Math.floor((Math.random() + Math.random() - 1) * half), x = cols - 1 - Math.floor(Math.random() * 3);
      if (y < 0 || y >= rows) continue;
      var i = y * cols + x;
      if (grid[i] === EMPTY) { grid[i] = Math.random() < 0.12 ? SAND2 : SAND; grains += 1; n -= 1; }
    }
  }
  // One pass of the automaton. Gravity left: a grain moves left, else diagonally left,
  // else stays. Gravity down (after Enter): the same, turned a quarter.
  function step() {
    var dx = gravity === "left" ? -1 : 0, dy = gravity === "left" ? 0 : 1;
    var sx = gravity === "left" ? 1 : 0, sy = gravity === "left" ? 0 : 1;   // the sideways axis
    next.set(grid);
    var flip = (Math.random() < 0.5) ? 1 : -1;
    for (var y = 0; y < rows; y++) {
      for (var x = 0; x < cols; x++) {
        var i = y * cols + x, v = grid[i];
        if (v < SAND) continue;
        if (Math.random() < 0.18) continue;          // a crowd does not march in step
        var tx = x + dx, ty = y + dy;
        if (tx < 0 || ty >= rows) { next[i] = EMPTY; grains -= 1; continue; }   // out of the field
        var ti = ty * cols + tx;
        if (next[ti] === EMPTY && grid[ti] === EMPTY) { next[ti] = v; next[i] = EMPTY; continue; }
        var ax = x + dx + sx * flip, ay = y + dy + sy * flip, bx = x + dx - sx * flip, by = y + dy - sy * flip;
        if (ax >= 0 && ax < cols && ay >= 0 && ay < rows) { var ai = ay * cols + ax; if (next[ai] === EMPTY && grid[ai] === EMPTY) { next[ai] = v; next[i] = EMPTY; continue; } }
        if (bx >= 0 && bx < cols && by >= 0 && by < rows) { var bi = by * cols + bx; if (next[bi] === EMPTY && grid[bi] === EMPTY) { next[bi] = v; next[i] = EMPTY; continue; } }
      }
    }
    var t = grid; grid = next; next = t;
    // grains past the copy's edge on wide screens leave the field
    if (!band) { var edge = Math.max(0, g.x - 14 * UNIT); for (var yy = 0; yy < rows; yy++) for (var xx = 0; xx < edge; xx++) { var k = yy * cols + xx; if (grid[k] >= SAND) { grid[k] = EMPTY; grains -= 1; } } }
  }
  // The pointer pushes grains away, so a visitor can dig through a pile.
  function stirAt() {
    if (!stir) return;
    var cx = stir.x, cy = stir.y, R = 6;
    for (var y = cy - R; y <= cy + R; y++) for (var x = cx - R; x <= cx + R; x++) {
      if (x < 0 || y < 0 || x >= cols || y >= rows) continue;
      var i = y * cols + x;
      if (grid[i] < SAND) continue;
      var ddx = x - cx, ddy = y - cy, d = Math.sqrt(ddx * ddx + ddy * ddy);
      if (d > R || d === 0) continue;
      var nx = x + Math.round(ddx / d * 2), ny = y + Math.round(ddy / d * 2);
      if (nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
      var j = ny * cols + nx;
      if (grid[j] === EMPTY) { grid[j] = grid[i]; grid[i] = EMPTY; }
    }
  }
  function tell() {
    var n = Math.round(inRoom / 4) * 4;
    if (n === told) return;
    told = n;
    listeners.forEach(function (fn) { fn({ inside: inRoom, full: inRoom >= roomCells * 0.97, entered: entered }); });
  }
  function countRoom() {
    var n = 0;
    for (var y = g.y; y < g.y + 20 * UNIT; y++) for (var x = g.x; x < g.x + 20 * UNIT; x++) {
      var ux = Math.floor((x - g.x) / UNIT), uy = Math.floor((y - g.y) / UNIT);
      if (inRoomUnit(ux, uy) && grid[y * cols + x] >= SAND) n += 1;
    }
    inRoom = n;
  }

  // Dithered glow of the sand on the dark: a cell near many grains brightens a tone.
  var BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
  var INK = [21, 18, 30], INK2 = [33, 28, 46], INK3 = [51, 44, 71], MERGE = [122, 90, 248], OPEN = [198, 244, 50], ODEEP = [63, 106, 0], PAPER = [244, 241, 250], OMID = [125, 179, 15];
  function nearYou(x, y) { return x >= you.x - 1 && x <= you.x + 3 * UNIT && y >= you.y - 1 && y <= you.y + 4 * UNIT; }
  function draw() {
    var d = img.data, now = performance.now() / 1000, t = now - start;
    var fill = roomCells ? Math.min(1, inRoom / (roomCells * 0.97)) : 0;
    var cheering = cheer && now - cheer < 0.7, blink = still || Math.floor(t / 0.55) % 2 === 0;
    var dx0 = doorX(), dy0 = doorY();
    for (var y = 0; y < rows; y++) for (var x = 0; x < cols; x++) {
      var i = y * cols + x, v = grid[i], c = INK;
      var ux = Math.floor((x - g.x) / UNIT), uy = Math.floor((y - g.y) / UNIT);
      // the door's light: a cone to the right of the gap, stronger as the room fills
      var L = 0;
      if (fill > 0.02 && v !== WALL) {
        var bx = x - dx0, by = Math.abs(y - dy0);
        if (bx > 0) { var w = (3 + 0.62 * bx / UNIT) * UNIT; if (by < w) L = (1 - by / w) * 0.9 / (1 + bx * 0.03) * fill; }
        else if (inRoomUnit(ux, uy)) L = 0.35 * fill;
      }
      if (v === WALL) c = MERGE;
      else if (v === YOU) c = blink ? OPEN : PAPER;
      else if (nearYou(x, y)) c = INK;                      // a little room around you, so you read in the crowd
      else if (v >= SAND) c = ((entered || cheering) && inRoomUnit(ux, uy)) || L > 0.45 ? PAPER : v === SAND ? OPEN : PAPER;
      else {
        // light from grains next to this cell, dithered into the two dark tones
        var n = 0;
        if (x > 0 && grid[i - 1] >= SAND) n += 1;
        if (x < cols - 1 && grid[i + 1] >= SAND) n += 1;
        if (y > 0 && grid[i - cols] >= SAND) n += 1;
        if (y < rows - 1 && grid[i + cols] >= SAND) n += 1;
        if (n) c = n > 1 ? ODEEP : (BAYER[(y & 3) * 4 + (x & 3)] < 8 ? ODEEP : INK3);
        else if (L > 0) { var lv = Math.floor(L * 4 + BAYER[(y & 3) * 4 + (x & 3)] / 16); c = lv >= 4 ? MERGE : lv === 3 ? MDEEP : lv === 2 ? INK3 : lv === 1 ? INK2 : INK; }
      }
      var o = i * 4; d[o] = c[0]; d[o + 1] = c[1]; d[o + 2] = c[2]; d[o + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
  }
  function frame() {
    var now = performance.now() / 1000, dt = Math.min(0.05, now - last);
    last = now;
    if (!still) {
      var full = inRoom >= roomCells * 0.97;
      var rate = entered ? 0 : full ? 0 : flow + burst;
      burst = Math.max(0, burst - dt * 60);
      if (grains < 4500) emit(Math.round(rate));
      stirAt();
      step(); step();
      moveYou(now);
      if (Math.floor(now * 4) !== Math.floor((now - dt) * 4)) { countRoom(); if (full && !cheer) cheer = now; tell(); }
      if (entered && now - enterAt > 0.9 && gravity !== "down") gravity = "down";
    }
    draw();
  }
  function loop() {
    raf = 0;
    if (!visible || still || document.hidden) return;
    frame();
    raf = requestAnimationFrame(loop);
  }
  function wake() { if (!raf) raf = requestAnimationFrame(loop); }

  function point(e) {
    if (still || (e.target.closest && e.target.closest(".hero-copy"))) { stir = null; return; }
    var r = canvas.getBoundingClientRect();
    stir = { x: Math.floor((e.clientX - r.left) / cell), y: Math.floor((e.clientY - r.top) / cell) };
  }
  hero.addEventListener("pointermove", point);
  hero.addEventListener("pointerdown", function (e) {
    if (still || (e.target.closest && e.target.closest(".hero-copy"))) return;
    var r = canvas.getBoundingClientRect();
    emitAt(Math.floor((e.clientX - r.left) / cell), Math.floor((e.clientY - r.top) / cell), 30);
    wake();
  });
  hero.addEventListener("pointerleave", function () { stir = null; });

  scene.appendChild(canvas);
  scene.classList.add("live");
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      visible = entries[0].isIntersecting;
      if (visible) wake();
    }).observe(scene);
  }
  document.addEventListener("visibilitychange", wake);
  if ("ResizeObserver" in window) new ResizeObserver(size).observe(scene);
  else window.addEventListener("resize", size);
  size();
  wake();

  // What the hero prompt drives (home.js): typing adds grains to the flow; Enter opens the
  // floor and the field drains before the page moves on.
  window.gigScene = {
    walk: function (fraction) {
      burst = 30 + 90 * fraction;
      var f = Math.max(0, Math.min(1, fraction));
      you.tx = Math.round(Math.min(cols - 4 * UNIT, doorX() + 7 * UNIT) - f * 7 * UNIT) + 1;
      wake();
    },
    enter: function (done) {
      if (entered) { done(); return; }
      entered = true; enterAt = performance.now() / 1000;
      you.tx = doorX() - 12 * UNIT;   // through the door, into the room, first
      you.at = 0;
      if (still) { you.x = you.tx; placeYou(); gravity = "down"; draw(); setTimeout(done, 80); return; }
      wake();
      setTimeout(done, 1900);
    },
    onCount: function (fn) { listeners.push(fn); },
    // runs the automaton ahead: what a still frame uses, and what a check can call
    advance: function (n) { for (var i = 0; i < n; i++) { if (!entered && grains < 4500 && inRoom < roomCells * 0.97) emit(flow); step(); if (i % 60 === 0) countRoom(); } countRoom(); draw(); var youCells = 0; for (var k = 0; k < grid.length; k++) if (grid[k] === YOU) youCells += 1; return { grains: grains, inRoom: inRoom, roomCells: roomCells, band: band, cols: cols, rows: rows, gx: g.x, gy: g.y, unit: UNIT, you: [you.x, you.y, you.tx, youCells] }; },
    still: still
  };
})();
