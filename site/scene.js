// The hall of doors on the home page: a first-person pixel corridor, drawn by a
// raycaster in a fragment shader on the brand's own grid (every cell is one fragment).
// One door per Google Summer of Code organization lines the walls, veterans first,
// and the pixel G at the far end is the lit doorway out. Typing languages in the
// hero prompt lights the doors whose official listing names them; Enter runs through
// the G. The cursor is the visitor: a lime block at the bottom of the view. The G
// itself never moves. No WebGL means the still SVG mark stays in place.
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
    "uniform vec2 u_res;uniform float u_time;uniform vec3 u_cam;uniform float u_bob;",
    "uniform sampler2D u_doors;uniform float u_count;uniform float u_spacing;uniform float u_zend;",
    "uniform float u_in;uniform float u_power;",
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
    // 4x4 ordered dither: M2(x,y)=2x+3y-4xy, M4 = 4*M2(x%2,y%2) + M2(x/2%2,y/2%2).
    "float m2(vec2 p){return 2.*p.x+3.*p.y-4.*p.x*p.y;}",
    "float bayer(vec2 c){return (4.*m2(mod(c,2.))+m2(mod(floor(c/2.),2.)))/16.;}",
    "vec3 ramp(float i,float h){",
    " vec3 v=i<.5?INK:i<1.5?INK2:i<2.5?INK3:i<3.5?MDEEP:i<4.5?MERGE:i<5.5?MSOFT:PAPER;",
    " vec3 l=i<.5?INK:i<1.5?INK2:i<2.5?INK3:i<3.5?ODEEP:i<4.5?OMID:i<5.5?OPEN:PAPER;",
    " return mix(v,l,h);}",
    // One texel per door: r = lit by the typed languages, g = years in the program.
    "vec2 door(float i){return texture2D(u_doors,vec2((i+.5)/256.,.5)).rg;}",
    "void main(){",
    " vec2 cell=floor(gl_FragCoord.xy);",
    " vec2 uv=(cell+.5-u_res*.5)/(u_res.y*.5);",
    " vec3 rd=normalize(vec3(uv.x,uv.y,1.5));",
    " float cy=cos(u_cam.y),sy=sin(u_cam.y);rd=vec3(rd.x*cy+rd.z*sy,rd.y,-rd.x*sy+rd.z*cy);",
    " vec3 ro=vec3(u_cam.x,u_bob,u_cam.z);const float W=1.,H=1.;",
    // The nearest of the two walls, the floor, the ceiling, and the end wall.
    " float t=1e9;int side=0;float tt;",
    " if(rd.x<0.){tt=(-W-ro.x)/rd.x;if(tt<t){t=tt;side=1;}}",
    " if(rd.x>0.){tt=(W-ro.x)/rd.x;if(tt<t){t=tt;side=2;}}",
    " if(rd.y<0.){tt=(-H-ro.y)/rd.y;if(tt<t){t=tt;side=3;}}",
    " if(rd.y>0.){tt=(H-ro.y)/rd.y;if(tt<t){t=tt;side=4;}}",
    " if(rd.z>0.){tt=(u_zend-ro.z)/rd.z;if(tt<t){t=tt;side=5;}}",
    " vec3 p=ro+rd*t;float L=0.,h=0.;bool mark=false,frame=false;",
    " float fog=exp(-t*.075);",
    " if(side==1||side==2){",
    "  float slot=floor(p.z/u_spacing);float i=slot*2.+float(side-1);float zl=fract(p.z/u_spacing);",
    "  bool inZ=zl>.22&&zl<.78&&i>=0.&&i<u_count;",
    "  vec2 d=door(i);",
    "  if(inZ&&p.y<.5){frame=zl<.3||zl>.7||p.y>.42;",
    "   if(!frame){L=.12+.08*d.g;if(p.y<-.92)L+=.25*d.g;if(d.r>.5){L=.92;h=1.;}}",
    "  }else{L=.2+.04*step(.5,fract(p.y*3.+.5*step(.5,fract(p.z*1.5))));}",
    "  if(side==1)L*=.85;",
    " }else if(side==3){L=.2;if(fract(p.z)<.06||fract(p.x+.5)<.06)L+=.1;}",
    " else if(side==4){L=.1;}",
    " else{vec2 q=floor((vec2(p.x,-p.y)+vec2(W,H))/(2.*W)*26.-vec2(3.,3.));",
    "  if(isG(q))mark=true;else{bool room=rect(q,4.,4.,19.,11.)||rect(q,4.,12.,9.,15.);L=room?.95:.12;h=room?u_in:0.;}",
    "  fog=exp(-t*.02);}",
    // Light from the doorway at the end reaches down the hall, lime once you are through.
    " float E=exp(-(u_zend-p.z)*.09);L+=.55*E;h+=u_in*E*1.5;",
    // Lit doors spill onto the floor and the opposite wall.
    " float spill=0.;float near=floor(p.z/u_spacing);",
    " for(int k=-2;k<=2;k++){float slot=near+float(k);for(int s=0;s<2;s++){float i=slot*2.+float(s);",
    "  if(i<0.||i>=u_count)continue;vec2 dd=door(i);if(dd.r>.5){vec3 dp=vec3(s==0?-W:W,-.2,(slot+.5)*u_spacing);float r=length(p-dp);spill+=.4*exp(-r*1.3);}}}",
    " L+=spill;h+=spill*1.6;",
    " L*=fog*u_power;",
    " float idx=floor(clamp(L,0.,1.)*6.+bayer(cell));vec3 col=ramp(idx,clamp(h,0.,1.));",
    " if(frame)col=MERGE*(.3+.7*fog*u_power);",
    " if(mark)col=MERGE;",
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
  ["u_res", "u_time", "u_cam", "u_bob", "u_doors", "u_count", "u_spacing", "u_zend", "u_in", "u_power"].forEach(function (n) {
    U[n] = gl.getUniformLocation(prog, n);
  });
  var tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  var texels = new Uint8Array(256 * 4);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 256, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, texels);
  gl.uniform1i(U.u_doors, 0);

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

  var SPACING = 1.4;                 // hall units between door slots; doors sit on both sides
  var doors = [], count = 0, zend = 12, longest = 1, lit = 0;
  var cam = { x: 0, yaw: 0, z: 0 }, lookX = 0, lookYaw = 0, cell = 4, cols = 0, rows = 0, band = false;
  var sprint = 0, inside = 0, entered = false, lastSlot = -1;
  var start = performance.now() / 1000, last = start, visible = true, raf = 0, cut = 0;
  var listeners = [];

  function size() {
    var W = scene.clientWidth, H = scene.clientHeight;
    if (lost || !W || !H) return;
    // Beside the copy on wide screens (the camera hugs the left wall so the hall opens on
    // the right), in a band above it on narrow ones (see styles.css).
    band = getComputedStyle(scene).position !== "absolute";
    cell = band ? 3 : 4;
    cols = Math.ceil(W / cell); rows = Math.ceil(H / cell);
    canvas.width = cols; canvas.height = rows;
    canvas.style.width = cols * cell + "px"; canvas.style.height = rows * cell + "px";
    cam.x = band ? 0 : -0.55;
    gl.viewport(0, 0, cols, rows);
    gl.uniform2f(U.u_res, cols, rows);
    draw();                           // a frame even in a background tab, so nothing is ever blank
  }

  function upload() {
    for (var i = 0; i < 256; i++) {
      var d = doors[i];
      texels[i * 4] = d && d.lit ? 255 : 0;
      texels[i * 4 + 1] = d ? Math.round(255 * d.y / longest) : 0;
    }
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 256, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, texels);
    lastSlot = -1;
  }
  function setDoors(list) {
    doors = list.slice(0, 256);
    count = doors.length;
    longest = Math.max(1, Math.max.apply(null, doors.map(function (d) { return d.y || 0; })));
    zend = (Math.ceil(count / 2) + 1) * SPACING;
    gl.uniform1f(U.u_count, count);
    gl.uniform1f(U.u_zend, zend);
    upload();
    wake();
  }
  gl.uniform1f(U.u_spacing, SPACING);
  gl.uniform1f(U.u_count, 0);
  gl.uniform1f(U.u_zend, zend);

  // A door opens for a typed word when its official listing names that word.
  function light(text) {
    var words = String(text || "").toLowerCase().split(/[,\s]+/).filter(function (w) { return w.length > 1; });
    lit = 0;
    doors.forEach(function (d) {
      d.lit = words.length > 0 && d.t.some(function (tag) {
        return words.some(function (w) { return tag === w || (w.length > 2 && tag.indexOf(w) !== -1); });
      });
      if (d.lit) lit += 1;
    });
    upload();
    wake();
    return lit;
  }

  function power(t) {
    if (still) return 1;
    if (cut > 0 && t - cut < 0.14) return 0;
    return Math.min(1, t / 0.5);
  }
  function tell() {
    var slot = Math.floor(cam.z / SPACING);
    if (slot === lastSlot) return;
    lastSlot = slot;
    var info = { slot: slot, left: doors[slot * 2] || null, right: doors[slot * 2 + 1] || null, lit: lit, count: count, entered: entered };
    listeners.forEach(function (fn) { fn(info); });
  }
  function draw() {
    var now = performance.now() / 1000, t = now - start, dt = Math.min(0.05, now - last);
    last = now;
    if (still) {
      cam.z = Math.min(cam.z, zend - 2.5);
      cam.yaw = 0;
    } else if (sprint) {
      // Run to the doorway in about a second and a half, whatever the distance.
      var k = Math.min(1, (now - sprint) / 1.5), e = k * k * (3 - 2 * k);
      cam.z = sprintFrom + (zend - 0.9 - sprintFrom) * e;
      cam.yaw += (0 - cam.yaw) * Math.min(1, dt * 6);
      if (k >= 1) { entered = true; inside = Math.min(1, inside + dt * 4); }
    } else {
      cam.z += 0.8 * dt;
      cam.yaw += (lookYaw - cam.yaw) * Math.min(1, dt * 5);
      if (cam.z > zend - 2.2) { cam.z = 0; cut = t; }
    }
    gl.uniform1f(U.u_time, t);
    gl.uniform3f(U.u_cam, cam.x, cam.yaw, cam.z);
    gl.uniform1f(U.u_bob, still || sprint ? 0 : 0.03 * Math.sin(cam.z * 4));
    gl.uniform1f(U.u_in, inside);
    gl.uniform1f(U.u_power, power(t));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    tell();
  }
  var sprintFrom = 0;
  function loop() {
    raf = 0;
    if (lost || !visible || still || document.hidden) return;
    draw();
    raf = requestAnimationFrame(loop);
  }
  function wake() { if (!raf) raf = requestAnimationFrame(loop); if (still) draw(); }

  // The pointer turns your head; the hero copy is not part of the hall.
  function point(e) {
    if (lost || still || sprint || (e.target.closest && e.target.closest(".hero-copy"))) return;
    var r = canvas.getBoundingClientRect();
    var x = (e.clientX - r.left) / r.width;
    lookYaw = (0.5 - x) * (band ? 0.9 : 0.7) + (band ? 0 : -0.12);
  }
  hero.addEventListener("pointermove", point);
  hero.addEventListener("pointerleave", function () { lookYaw = band ? 0 : -0.12; });
  lookYaw = -0.12;

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
    step: function () { if (!lost && !sprint && !still) { cam.z += 0.6; wake(); } },
    enter: function (done) {
      if (lost || entered) { done(); return; }
      if (still) { entered = true; inside = 1; draw(); setTimeout(done, 80); return; }
      sprint = performance.now() / 1000; sprintFrom = cam.z;
      wake();
      setTimeout(done, 1900);
    },
    onDoor: function (fn) { listeners.push(fn); },
    still: still
  };
})();
