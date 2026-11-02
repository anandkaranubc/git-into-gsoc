// The doorway on the home page: the pixel G as a lit door in a dark room, drawn by a
// fragment shader on the brand's own grid. Every cell is one fragment, so a hero
// of 200 by 130 cells costs the GPU almost nothing. The lime cursor is the visitor:
// it walks in on its own, follows the pointer when there is one, and the room turns
// lime when it is through. No WebGL means the static SVG mark stays in place.
(function () {
  "use strict";
  var scene = document.querySelector(".scene");
  var hero = document.querySelector(".hero");
  if (!scene || !hero) return;
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canvas = document.createElement("canvas");
  var gl = canvas.getContext("webgl", { antialias: false, alpha: false, depth: false, powerPreference: "low-power" });
  if (!gl) return;

  var VERT = "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}";
  var FRAG = [
    "precision mediump float;",
    "uniform vec2 u_res;uniform float u_time;uniform vec2 u_g;uniform float u_unit;",
    "uniform vec2 u_cursor;uniform float u_alpha;uniform float u_in;uniform float u_power;uniform float u_motion;",
    "const vec3 INK=vec3(.082,.071,.118),INK2=vec3(.129,.110,.180),INK3=vec3(.200,.173,.278);",
    "const vec3 MDEEP=vec3(.298,.184,.851),MERGE=vec3(.478,.353,.973),MSOFT=vec3(.761,.710,1.);",
    "const vec3 PAPER=vec3(.957,.945,.980),ODEEP=vec3(.247,.416,0.),OPEN=vec3(.776,.957,.196),OMID=vec3(.49,.70,.06);",
    "bool rect(vec2 p,float x0,float y0,float x1,float y1){return p.x>=x0&&p.x<=x1&&p.y>=y0&&p.y<=y1;}",
    // The G from scripts/brand/build.py: six bars, four softened corners, two added cells.
    "bool isG(vec2 q){if(q.x<0.||q.y<0.||q.x>19.||q.y>19.)return false;",
    " bool g=rect(q,0.,0.,3.,19.)||rect(q,0.,0.,19.,3.)||rect(q,16.,4.,19.,5.)||rect(q,10.,12.,19.,15.)||rect(q,16.,12.,19.,19.)||rect(q,0.,16.,19.,19.);",
    " if((q.x<=1.&&q.y==0.)||(q.x==0.&&q.y<=1.))g=false;if((q.x>=18.&&q.y==0.)||(q.x==19.&&q.y<=1.))g=false;",
    " if((q.x<=1.&&q.y==19.)||(q.x==0.&&q.y>=18.))g=false;if((q.x>=18.&&q.y==19.)||(q.x==19.&&q.y>=18.))g=false;",
    " if((q.x==4.&&q.y==4.)||(q.x==4.&&q.y==15.))g=true;return g;}",
    "bool inside(vec2 q){return !isG(q)&&(rect(q,4.,4.,19.,11.)||rect(q,4.,12.,9.,15.));}",
    // 4x4 ordered dither: M2(x,y)=2x+3y-4xy, M4 = 4*M2(x%2,y%2) + M2(x/2%2,y/2%2).
    "float m2(vec2 p){return 2.*p.x+3.*p.y-4.*p.x*p.y;}",
    "float bayer(vec2 c){return (4.*m2(mod(c,2.))+m2(mod(floor(c/2.),2.)))/16.;}",
    "float hash(float n){return fract(sin(n*127.1)*43758.5453);}",
    "vec3 ramp(float i,float h){",
    " vec3 v=i<.5?INK:i<1.5?INK2:i<2.5?INK3:i<3.5?MDEEP:i<4.5?MERGE:i<5.5?MSOFT:PAPER;",
    " vec3 l=i<.5?INK:i<1.5?INK2:i<2.5?INK3:i<3.5?ODEEP:i<4.5?OMID:i<5.5?OPEN:PAPER;",
    " return mix(v,l,h);}",
    "void main(){",
    " vec2 cell=floor(gl_FragCoord.xy);cell.y=u_res.y-1.-cell.y;",
    " vec2 p=(cell-u_g)/u_unit;vec2 q=floor(p);float t=u_time;",
    " float flick=1.+u_motion*(.035*sin(t*1.3)+.025*sin(t*3.7+1.)+.015*sin(t*9.1));",
    " float power=u_power*flick;",
    " vec2 d=p-vec2(20.,9.);float L=.2*exp(-length(d)/13.)*power;float h=0.;",
    " if(d.x>0.){float w=3.+.62*d.x;float across=1.-smoothstep(w*.45,w,abs(d.y));L+=across*1.05/(1.+d.x*.085)*power;}",
    " bool room=inside(q);",
    " if(room){L=(.72+.33*smoothstep(3.,19.,p.x))*power;h+=u_in*.9;}",
    // Dust in the beam: a few dozen cells drifting out of the door.
    " for(int i=0;i<28;i++){float f=float(i);float sp=.35+.55*hash(f+.3);",
    "  float x=21.+mod(hash(f)*30.+t*sp*u_motion,30.);float y=9.+(hash(f+.7)-.5)*(3.+.62*(x-20.))*1.3;",
    "  if(q.x==floor(x)&&q.y==floor(y)&&hash(f+.9)<power){L=max(L,.62+.3*hash(f+.5));}}",
    // The cursor's own faint light, lime.
    " vec2 cc=u_cursor+vec2(1.5,2.);float cd=length(p-cc);",
    " L+=u_alpha*.32*exp(-cd/2.6);h+=u_alpha*.9*exp(-cd/2.6);",
    " float idx=floor(clamp(L,0.,1.)*6.+bayer(cell));",
    " vec3 col=ramp(idx,clamp(h,0.,1.));",
    " if(isG(q))col=MERGE;",
    " if(rect(p,u_cursor.x,u_cursor.y,u_cursor.x+2.999,u_cursor.y+3.999))col=mix(col,OPEN,u_alpha);",
    " gl_FragColor=vec4(col,1.);}"
  ].join("\n");

  function shader(type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
  }
  var vs = shader(gl.VERTEX_SHADER, VERT), fs = shader(gl.FRAGMENT_SHADER, FRAG);
  if (!vs || !fs) return;
  var prog = gl.createProgram();
  gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
  gl.useProgram(prog);
  var buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  var a = gl.getAttribLocation(prog, "a");
  gl.enableVertexAttribArray(a);
  gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
  var U = {};
  ["u_res", "u_time", "u_g", "u_unit", "u_cursor", "u_alpha", "u_in", "u_power", "u_motion"].forEach(function (n) {
    U[n] = gl.getUniformLocation(prog, n);
  });

  scene.appendChild(canvas);
  scene.classList.add("live");
  var lost = false;
  // Mobile Safari drops WebGL contexts under memory pressure; the still mark comes back.
  canvas.addEventListener("webglcontextlost", function (e) {
    e.preventDefault();
    lost = true;
    scene.classList.remove("live");
    canvas.remove();
  });

  var UNIT = 3;                       // cells per grid unit; the G is 20 units = 60 cells tall
  var cols = 0, rows = 0, cell = 6, g = { x: 0, y: 0 };
  var THRESHOLD = { x: 18, y: 7 }, OUTSIDE = { x: 36, y: 7 }, IN = { x: 10, y: 7 };
  var cur = { x: THRESHOLD.x, y: THRESHOLD.y }, alpha = 1, target = null;
  var start = performance.now() / 1000, idleStart = start, followUntil = 0, lastStep = 0;
  var visible = true, raf = 0;
  // Typing in the hero prompt walks the cursor to the threshold; Enter steps it through.
  var typedUntil = 0, typedX = OUTSIDE.x, entering = false, entered = false;

  var copy = hero.querySelector(".hero-copy");
  function size() {
    var W = scene.clientWidth, H = scene.clientHeight;
    if (lost || !W || !H) return;
    // Beside the copy on wide screens, in a band above it on narrow ones (see styles.css).
    var band = getComputedStyle(scene).position !== "absolute";
    var copyRight = band ? 0 : copy.getBoundingClientRect().right - scene.getBoundingClientRect().left + 40;
    var room = band ? W : W - copyRight;
    cell = Math.max(band ? 3 : 4, Math.min(6, Math.round(H * (band ? 0.3 : 0.42) / 60), Math.floor(room / 72)));
    cols = Math.ceil(W / cell); rows = Math.ceil(H / cell);
    canvas.width = cols; canvas.height = rows;
    canvas.style.width = cols * cell + "px"; canvas.style.height = rows * cell + "px";
    g.x = band ? Math.round(cols * 0.18) : Math.min(cols - 64, Math.max(Math.round(cols * 0.56), Math.round(copyRight / cell)));
    g.y = Math.round((rows - 60) / 2);
    gl.viewport(0, 0, cols, rows);
    gl.uniform2f(U.u_res, cols, rows);
    gl.uniform2f(U.u_g, g.x, g.y);
    gl.uniform1f(U.u_unit, UNIT);
    draw();                           // a frame even in a background tab, so nothing is ever blank
  }

  function isIn(c) {
    var x = c.x + 1.5, y = c.y + 2;
    return (x >= 4 && x < 20 && y >= 4 && y < 12) || (x >= 4 && x < 10 && y >= 12 && y < 16);
  }
  // Switching the light on: dark, a stutter, then steady.
  function power(t) {
    if (still) return 1;
    if (t < 0.25) return 0;
    if (t < 0.4) return 0.55;
    if (t < 0.5) return 0.15;
    return Math.min(1, 0.4 + (t - 0.5) * 1.5);
  }
  // Stand outside, walk to the threshold, pause, step in, stay, fade; then again.
  function idle(t) {
    var s = t % 12;
    alpha = s < 0.5 ? s / 0.5 : s > 11.2 ? Math.max(0, (12 - s) / 0.8) : 1;
    var x;
    if (s < 1.8) x = OUTSIDE.x;
    else if (s < 5.2) x = OUTSIDE.x - Math.floor((s - 1.8) / 3.4 * (OUTSIDE.x - THRESHOLD.x));
    else if (s < 6.6) x = THRESHOLD.x;
    else if (s < 7.8) x = THRESHOLD.x - Math.floor((s - 6.6) / 1.2 * (THRESHOLD.x - IN.x));
    else x = IN.x;
    cur.x = x; cur.y = THRESHOLD.y;
  }
  function follow(now) {
    alpha = 1;
    if (!target || now - lastStep < 0.04) return;
    lastStep = now;
    cur.x += Math.sign(target.x - cur.x);
    cur.y += Math.sign(target.y - cur.y);
  }

  function draw() {
    var now = performance.now() / 1000;
    var t = now - start;
    if (still) { cur = { x: entered ? IN.x : THRESHOLD.x, y: THRESHOLD.y }; alpha = 1; }
    else if (entering || entered) { alpha = 1; if (now - lastStep > 0.06 && cur.x > IN.x) { lastStep = now; cur.x -= 1; } cur.y = THRESHOLD.y; if (cur.x <= IN.x) { entering = false; entered = true; } }
    else if (now < typedUntil) { alpha = 1; cur.x = typedX; cur.y = THRESHOLD.y; }
    else if (now < followUntil) follow(now);
    else idle(now - idleStart);
    gl.uniform1f(U.u_time, t);
    gl.uniform2f(U.u_cursor, cur.x, cur.y);
    gl.uniform1f(U.u_alpha, alpha);
    gl.uniform1f(U.u_in, isIn(cur) ? 1 : 0);
    gl.uniform1f(U.u_power, entered ? 1.25 : power(t));
    gl.uniform1f(U.u_motion, still ? 0 : 1);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  function loop() {
    raf = 0;
    if (lost || !visible || still || document.hidden) return;
    draw();
    raf = requestAnimationFrame(loop);
  }
  function wake() { if (!raf) raf = requestAnimationFrame(loop); }

  // The pointer moves the cursor, one cell step at a time; idle resumes a moment after it leaves.
  function point(e) {
    if (lost || still || entering || entered || (e.target.closest && e.target.closest(".hero-copy"))) return;
    var r = canvas.getBoundingClientRect();
    var x = (e.clientX - r.left) / cell, y = (e.clientY - r.top) / cell;
    target = { x: Math.round((x - g.x) / UNIT - 1.5), y: Math.round((y - g.y) / UNIT - 2) };
    var now = performance.now() / 1000;
    if (now >= followUntil) { alpha = 1; }
    followUntil = now + 2.5;
    idleStart = followUntil;
  }
  hero.addEventListener("pointermove", point);
  hero.addEventListener("pointerdown", point);

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

  // What the hero prompt drives (home.js): a fraction typed walks the cursor from outside
  // to the threshold, and enter() steps it through before the page moves on.
  window.gigScene = {
    walk: function (fraction) {
      if (lost || entering || entered) return;
      typedX = OUTSIDE.x - Math.round(Math.max(0, Math.min(1, fraction)) * (OUTSIDE.x - THRESHOLD.x));
      typedUntil = performance.now() / 1000 + 6;
      idleStart = typedUntil;
      wake();
    },
    enter: function (done) {
      if (lost || entered) { done(); return; }
      entering = true;
      if (!still) { cur.x = Math.min(cur.x, typedUntil > performance.now() / 1000 ? typedX : cur.x); }
      lastStep = 0;
      wake();
      if (still) draw();
      setTimeout(done, still ? 80 : 720);
    },
    still: still
  };
})();
