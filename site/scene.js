// The town on the home page: every Google Summer of Code organization is a small pixel
// house at night, in rows of streets, with the pixel G as the gate at the top of the hill.
// Typing languages in the hero prompt turns on the lights of the houses whose official
// listing names them, and the cursor (you) walks the streets to the lit houses that fit,
// then up to the gate. Drawn on a canvas at the brand's cell size, so every edge is a
// whole pixel; the G itself never moves. Without a canvas the still SVG mark stays.
(function () {
  "use strict";
  var scene = document.querySelector(".scene");
  var hero = document.querySelector(".hero");
  if (!scene || !hero) return;
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canvas = document.createElement("canvas");
  var ctx = canvas.getContext("2d", { alpha: false });
  if (!ctx) return;
  var buffer = document.createElement("canvas");
  var g = buffer.getContext("2d", { alpha: false });

  var C = {
    ink: "#15121E", ink2: "#211C2E", ink3: "#332C47", mdeep: "#4C2FD9", merge: "#7A5AF8", msoft: "#C2B5FF",
    paper: "#F4F1FA", odeep: "#3F6A00", omid: "#7DB30F", open: "#C6F432", mute: "#67607A"
  };
  // The G from scripts/brand/build.py: six bars, four softened corners, two added cells.
  var G = [];
  (function () {
    function rect(q, x0, y0, x1, y1) { return q[0] >= x0 && q[0] <= x1 && q[1] >= y0 && q[1] <= y1; }
    for (var y = 0; y < 20; y++) for (var x = 0; x < 20; x++) {
      var q = [x, y];
      var on = rect(q, 0, 0, 3, 19) || rect(q, 0, 0, 19, 3) || rect(q, 16, 4, 19, 5) || rect(q, 10, 12, 19, 15) || rect(q, 16, 12, 19, 19) || rect(q, 0, 16, 19, 19);
      if ((x <= 1 && y === 0) || (x === 0 && y <= 1) || (x >= 18 && y === 0) || (x === 19 && y <= 1)) on = false;
      if ((x <= 1 && y === 19) || (x === 0 && y >= 18) || (x >= 18 && y === 19) || (x === 19 && y >= 18)) on = false;
      if ((x === 4 && y === 4) || (x === 4 && y === 15)) on = true;
      var room = !on && (rect(q, 4, 4, 19, 11) || rect(q, 4, 12, 9, 15));
      G.push(on ? 1 : room ? 2 : 0);
    }
  })();
  // 4x4 ordered dither, the same matrix as the brand's light.
  var BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];

  var TW = 7, TH = 4, COLP = 9, ROWP = 12;   // a house is 7 cells wide; the pitch between houses
  var SIDE = 14;                                 // houses per row
  var doors = [], count = 0, lit = 0, longest = 1;
  var cell = 4, cols = 0, rows = 0, band = false, gateScale = 2;
  var cur = { x: 0, y: 0 }, home = { x: 0, y: 0 }, path = [], walkAt = 0, speed = 14;   // cells per second
  var lookX = 0, lookY = 0, sprint = false, entered = false, inside = 0;
  var start = performance.now() / 1000, last = start, visible = true, raf = 0;
  var listeners = [];
  var GATE = { x: 0, y: 0 };

  // Town coordinates: house (a, b) stands at column a, row b; streets run between rows and
  // in the two-cell gaps between columns. The gate is above the top row, you start below
  // the bottom one.
  function layout() {
    var small = rows < 205 || band;
    TW = 7; COLP = 9; ROWP = band ? 6 : small ? 10 : 12;
    gateScale = small ? 1 : 2;
    doors.forEach(function (d, n) {
      d.a = n % SIDE; d.b = Math.floor(n / SIDE);
      d.sx = d.a * COLP + Math.floor(TW / 2); d.sy = d.b * ROWP;
      d.h = 3 + Math.round(3 * (d.y || 0) / longest);
    });
    var rowsUsed = Math.ceil(count / SIDE) || 14;
    GATE.x = Math.round((SIDE * COLP - 2) / 2); GATE.y = -gateScale * 20 - 8;
    home.x = GATE.x; home.y = rowsUsed * ROWP + 2;
    if (!path.length && !entered) { cur.x = home.x; cur.y = home.y; }
  }
  function townWidth() { return SIDE * COLP - 2; }
  function townHeight() { return (Math.ceil(count / SIDE) || 14) * ROWP + 6 - GATE.y; }

  function size() {
    var W = scene.clientWidth, H = scene.clientHeight;
    if (!W || !H) return;
    band = getComputedStyle(scene).position !== "absolute";
    cell = band ? 3 : 4;
    cols = Math.ceil(W / cell); rows = Math.ceil(H / cell);
    canvas.width = cols * cell; canvas.height = rows * cell;
    canvas.style.width = cols * cell + "px"; canvas.style.height = rows * cell + "px";
    buffer.width = cols; buffer.height = rows;
    ctx.imageSmoothingEnabled = false;
    layout();
    draw(true);
  }

  function setDoors(list) {
    doors = list.slice(0, SIDE * 14);
    count = doors.length;
    longest = Math.max(1, Math.max.apply(null, doors.map(function (d) { return d.y || 0; })));
    doors.forEach(function (d, n) { d.win = (n * 7919) % 3; });   // which house shows a late light
    layout();
    draw(true); wake();
    tellNear(null);
  }

  // A house lights for a typed word when its official listing names that word.
  function light(text) {
    var words = String(text || "").toLowerCase().split(/[,\s]+/).filter(function (w) { return w.length > 1; });
    lit = 0;
    doors.forEach(function (d) {
      d.lit = words.length > 0 && d.t.some(function (tag) {
        return words.some(function (w) { return tag === w || (w.length > 2 && tag.indexOf(w) !== -1); });
      });
      if (d.lit) lit += 1;
    });
    if (!entered && !sprint) plan(false);
    draw(true); wake();
    return lit;
  }

  // The cursor walks the streets: along its row to the gap beside the target column, up
  // or down that gap to the target's street, then along it to the door. It visits up to
  // three lit houses, nearest first; the gate only when you press Enter.
  function route(from, to) {
    var steps = [], x = from.x, y = from.y;
    var gap = Math.round((to.x + 1) / COLP) * COLP - 1;   // the gap right of the target column
    while (x !== gap) { x += gap > x ? 1 : -1; steps.push({ x: x, y: y }); }
    while (y !== to.y) { y += to.y > y ? 1 : -1; steps.push({ x: x, y: y }); }
    while (x !== to.x) { x += to.x > x ? 1 : -1; steps.push({ x: x, y: y }); }
    return steps;
  }
  function plan(toGate) {
    var stops = [], at = { x: cur.x, y: cur.y };
    var pool = doors.filter(function (d) { return d.lit; });
    for (var n = 0; n < 3 && pool.length; n++) {
      pool.sort(function (p, q) { return (Math.abs(p.sx - at.x) + Math.abs(p.sy + 2 - at.y)) - (Math.abs(q.sx - at.x) + Math.abs(q.sy + 2 - at.y)); });
      var d = pool.shift();
      stops.push({ x: d.sx, y: d.sy + 2, door: d });
      at = { x: d.sx, y: d.sy + 2 };
    }
    if (toGate) stops.push({ x: GATE.x, y: GATE.y + gateScale * 20 + 1, gate: true });
    path = [];
    var here = { x: cur.x, y: cur.y };
    stops.forEach(function (st) {
      var legs = route(here, st);
      if (legs.length) legs[legs.length - 1].stop = st;
      path = path.concat(legs);
      here = { x: st.x, y: st.y };
    });
    walkAt = performance.now() / 1000;
  }

  function fillCells(x, y, w, h, color) { g.fillStyle = color; g.fillRect(x, y, w, h); }
  // Scanline fill of an integer polygon, so edges stay whole cells.
  function poly(points, color) {
    var minY = Infinity, maxY = -Infinity;
    points.forEach(function (p) { minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]); });
    g.fillStyle = color;
    for (var y = minY; y < maxY; y++) {
      var xs = [];
      for (var k = 0; k < points.length; k++) {
        var a = points[k], b = points[(k + 1) % points.length];
        if ((a[1] <= y && b[1] > y) || (b[1] <= y && a[1] > y)) xs.push(a[0] + (y + 0.5 - a[1]) * (b[0] - a[0]) / (b[1] - a[1]));
      }
      xs.sort(function (p, q) { return p - q; });
      for (var m = 0; m + 1 < xs.length; m += 2) g.fillRect(Math.round(xs[m]), y, Math.max(1, Math.round(xs[m + 1]) - Math.round(xs[m])), 1);
    }
  }
  function dither(x, y, amount) { return amount * 16 > BAYER[(y & 3) * 4 + (x & 3)]; }

  function house(d, ox, oy, t) {
    var x = d.sx + ox, y = d.sy + oy, h = d.h;   // x: centre column, y: the ground line
    if (x < -TW || x > cols + TW || y < -h - 5 || y > rows + 2) return;
    // ground glow for a lit house, dithered into the dark
    if (d.lit) {
      for (var gy = -1; gy <= 3; gy++) for (var gx = -7; gx <= 7; gx++) {
        var r = Math.abs(gx) / 8 + Math.abs(gy - 1) / 3;
        if (r < 1 && dither(x + gx, y + gy, (1 - r) * 0.8)) fillCells(x + gx, y + gy, 1, 1, C.odeep);
      }
    }
    var body = d.lit ? C.ink3 : C.ink2, roof = d.lit ? C.merge : C.ink3, edge = d.lit ? C.mdeep : C.mute;
    fillCells(x - 3, y - h, 7, h, body);                       // walls
    fillCells(x - 3, y - h, 1, h, edge);                       // the lit edge of the wall
    for (var r = 0; r < 4; r++) fillCells(x - r, y - h - 4 + r, 2 * r + 1, 1, roof);   // the roof, point first
    if (d.win === 0) fillCells(x + 2, y - h - 3, 1, 2, roof);  // a chimney on some
    fillCells(x, y - 2, 1, 2, d.lit ? C.open : C.ink);        // the door
    var late = !d.lit && ((t * 0.5 + d.win) % 9 < 1);        // somebody still up
    fillCells(x - 2, y - h + 1, 2, 1, d.lit ? C.open : late ? C.msoft : C.ink);   // the window
  }

  function gate(ox, oy) {
    var k = gateScale, x = GATE.x + ox, Y = GATE.y + oy, X = x - 10 * k;
    for (var yy = 0; yy < 20; yy++) for (var xx = 0; xx < 20; xx++) {
      var v = G[yy * 20 + xx];
      if (!v) continue;
      fillCells(X + xx * k, Y + yy * k, k, k, v === 1 ? C.merge : inside > 0 ? C.open : C.paper);
    }
    // light on the ground in front of the gate
    var gy0 = Y + 20 * k;
    for (var gy = 0; gy <= 12; gy++) for (var gx = -12 - gy; gx <= 12 + gy; gx++) {
      var r = Math.abs(gx) / (12 + gy) * 0.5 + gy / 12;
      if (r < 1 && dither(x + gx, gy0 + gy, (1 - r) * 0.6)) fillCells(x + gx, gy0 + gy, 1, 1, inside > 0 ? C.odeep : C.mdeep);
    }
  }

  function draw(force) {
    var now = performance.now() / 1000, t = now - start, dt = Math.min(0.05, now - last);
    last = now;
    if (!still) {
      // walk the planned path, a cell per step; a sprint takes the whole road at once
      var rate = sprint ? 70 : speed;
      while (path.length && now - walkAt > 1 / rate) {
        var step = path.shift();
        cur.x = step.x; cur.y = step.y;
        walkAt += 1 / rate;
        if (step.stop) {
          if (step.stop.gate) entered = true;
          else { walkAt += sprint ? 0 : 0.6; tellNear(step.stop.door); }
        }
      }
      if (entered) inside = Math.min(1, inside + dt * 3);
    }
    // framing: the whole town, centred in the right part on wide screens; the pointer leans it
    var ox = Math.round(cols * (band ? 0.5 : 0.64) - townWidth() / 2 + lookX * 5);
    var oy = Math.round((rows - townHeight()) / 2 - GATE.y + lookY * 3);

    fillCells(0, 0, cols, rows, C.ink);
    // the ground: a faint dither so the town reads as a hill
    for (var yy = 0; yy < rows; yy++) for (var xx = 0; xx < cols; xx++) {
      var tx = xx - ox, ty = yy - oy;
      if (tx > -6 && tx < townWidth() + 6 && ty > -4 && ty < home.y + 6 && dither(xx, yy, 0.08)) fillCells(xx, yy, 1, 1, C.ink2);
    }
    gate(ox, oy);
    for (var n = 0; n < doors.length; n++) house(doors[n], ox, oy, t);   // rows top to bottom: back to front
    // the road ahead, dotted lime
    for (var k = 0; k < path.length; k += 2) {
      if (dither(path[k].x + ox, path[k].y + oy, 0.5)) fillCells(path[k].x + ox, path[k].y + oy, 1, 1, C.omid);
    }
    // you
    var blink = still || Math.floor(t / 0.55) % 2 === 0 || path.length;
    if (blink) fillCells(cur.x + ox - 1, cur.y + oy - 3, 3, 4, inside > 0 ? C.paper : C.open);
    if (inside > 0) {
      // through the gate: the town goes lime from the top down
      var line = Math.round(rows * inside * 1.2);
      for (var y2 = 0; y2 < Math.min(rows, line); y2++) for (var x2 = 0; x2 < cols; x2++) if (dither(x2, y2, inside * 0.9)) fillCells(x2, y2, 1, 1, C.open);
    }
    ctx.drawImage(buffer, 0, 0, cols, rows, 0, 0, cols * cell, rows * cell);
    if (entered && !told) { told = true; tellNear(null); }
  }
  var told = false;
  function tellNear(door) {
    listeners.forEach(function (fn) { fn({ count: count, lit: lit, near: door, entered: entered }); });
  }
  function loop() {
    raf = 0;
    if (!visible || still || document.hidden) return;
    draw(false);
    raf = requestAnimationFrame(loop);
  }
  function wake() { if (!raf) raf = requestAnimationFrame(loop); if (still) draw(true); }

  // The pointer leans the camera a little; the hero copy is not part of the town.
  function point(e) {
    if (still || (e.target.closest && e.target.closest(".hero-copy"))) return;
    var r = canvas.getBoundingClientRect();
    lookX = ((e.clientX - r.left) / r.width - 0.5) * -2;
    lookY = ((e.clientY - r.top) / r.height - 0.5) * -2;
  }
  hero.addEventListener("pointermove", point);
  hero.addEventListener("pointerleave", function () { lookX = 0; lookY = 0; });

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

  // What the hero prompt drives (home.js).
  window.gigScene = {
    doors: setDoors,
    light: light,
    step: function () { if (!still && !sprint && path.length) { walkAt -= 2 / speed; wake(); } },
    enter: function (done) {
      if (entered) { done(); return; }
      if (still) { entered = true; inside = 1; draw(true); setTimeout(done, 80); return; }
      sprint = true;
      plan(true);
      wake();
      setTimeout(done, 1900);
    },
    onDoor: function (fn) { listeners.push(fn); },
    still: still
  };
})();
