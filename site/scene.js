// The doorway on the home page, in three dimensions: the pixel G stands as a monument in
// a dark field, a lit room behind its open front and its door gap, light pouring out
// across the floor and through the air. Drawn by a raymarcher in a fragment shader on
// the brand's grid, so every cell is one fragment and the light is dithered into the
// seven brand tones, as the flat scene was. The camera drifts and follows the pointer.
// The lime cursor is the visitor: it walks to the threshold on its own, walks as you
// type, and steps in on Enter, when the camera follows it through. The G never moves.
// No WebGL means the still SVG mark stays in place.
(function () {
  "use strict";
  // Compiling the shader is synchronous and would delay the first paint of the copy, so
  // the scene starts once the page has loaded.
  if (document.readyState !== "complete") { window.addEventListener("load", arguments.callee); return; }
  var scene = document.querySelector(".scene");
  var hero = document.querySelector(".hero");
  if (!scene || !hero) return;
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canvas = document.createElement("canvas");
  var gl = canvas.getContext("webgl", { antialias: false, alpha: false, depth: false, powerPreference: "high-performance" });
  if (!gl) return;

  var VERT = "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}";
  var FRAG = [
    "precision highp float;",
    "uniform vec2 u_res;uniform float u_time;uniform vec3 u_eye;uniform vec3 u_at;",
    "uniform vec3 u_cursor;uniform float u_alpha;uniform float u_in;uniform float u_power;uniform float u_motion;",
    "const vec3 INK=vec3(.082,.071,.118),INK2=vec3(.129,.110,.180),INK3=vec3(.200,.173,.278);",
    "const vec3 MDEEP=vec3(.298,.184,.851),MERGE=vec3(.478,.353,.973),MSOFT=vec3(.761,.710,1.);",
    "const vec3 PAPER=vec3(.957,.945,.980),ODEEP=vec3(.247,.416,0.),OPEN=vec3(.776,.957,.196),OMID=vec3(.49,.70,.06);",
    "float m2(vec2 p){return 2.*p.x+3.*p.y-4.*p.x*p.y;}",
    "float bayer(vec2 c){return (4.*m2(mod(c,2.))+m2(mod(floor(c/2.),2.)))/16.;}",
    "vec3 ramp(float i,float h){",
    " vec3 v=i<.5?INK:i<1.5?INK2:i<2.5?INK3:i<3.5?MDEEP:i<4.5?MERGE:i<5.5?MSOFT:PAPER;",
    " vec3 l=i<.5?INK:i<1.5?INK2:i<2.5?INK3:i<3.5?ODEEP:i<4.5?OMID:i<5.5?OPEN:PAPER;",
    " return mix(v,l,h);}",
    "float sdBox(vec3 p,vec3 c,vec3 b){vec3 d=abs(p-c)-b;return length(max(d,0.))+min(max(d.x,max(d.y,d.z)),0.);}",
    // The G from scripts/brand/build.py as six bars, 20 units tall, 6 deep, standing on the floor.
    "float bar(vec3 p,float x0,float y0,float x1,float y1){return sdBox(p,vec3((x0+x1)*.5,16.-(y0+y1)*.5,0.),vec3((x1-x0)*.5,(y1-y0)*.5,3.));}",
    "float sdG(vec3 p){float d=bar(p,0.,0.,4.,20.);d=min(d,bar(p,0.,0.,20.,4.));d=min(d,bar(p,16.,4.,20.,6.));",
    " d=min(d,bar(p,10.,12.,20.,16.));d=min(d,bar(p,16.,12.,20.,20.));return min(d,bar(p,0.,16.,20.,20.));}",
    "float sdPlate(vec3 p){return sdBox(p,vec3(10.,6.,-3.6),vec3(10.,10.,.6));}",
    "float sdCursor(vec3 p){return sdBox(p,u_cursor,vec3(1.5,2.,1.5));}",
    // 1 the G, 2 the back wall of the room, 3 the floor, 4 the cursor
    "float map(vec3 p,out int m){float d=sdG(p);m=1;float e=sdPlate(p);if(e<d){d=e;m=2;}e=p.y;if(e<d){d=e;m=3;}",
    " if(u_alpha>.01){e=sdCursor(p);if(e<d){d=e;m=4;}}return d;}",
    "float mapd(vec3 p){int m;return map(p,m);}",
    "vec3 normal(vec3 p){vec2 e=vec2(.02,0.);return normalize(vec3(mapd(p+e.xyy)-mapd(p-e.xyy),mapd(p+e.yxy)-mapd(p-e.yxy),mapd(p+e.yyx)-mapd(p-e.yyx)));}",
    "float shadow(vec3 o,vec3 l,float k){vec3 d=l-o;float L=length(d);d/=L;float t=.3,r=1.;",
    " for(int i=0;i<24;i++){float h=sdG(o+d*t);h=min(h,sdPlate(o+d*t));if(h<.01)return 0.;r=min(r,k*h/t);t+=max(h,.15);if(t>L)break;}return clamp(r,0.,1.);}",
    "const vec3 LAMP=vec3(9.,7.,-1.);",
    "float lamp(vec3 p,vec3 n){vec3 d=LAMP-p;float L=length(d);d/=L;return max(dot(n,d),0.)*95./(L*L+30.)*shadow(p+n*.1,LAMP,10.);}",
    "void main(){",
    " vec2 cell=floor(gl_FragCoord.xy);vec2 uv=(cell+.5-u_res*.5)/u_res.y;",
    " vec3 f=normalize(u_at-u_eye),r=normalize(cross(f,vec3(0.,1.,0.))),u=cross(r,f);",
    " vec3 rd=normalize(f*1.35+uv.x*r+uv.y*u);vec3 ro=u_eye;",
    " float t=0.;int m=0;bool hit=false;",
    " for(int i=0;i<72;i++){int mm;float h=map(ro+rd*t,mm);if(h<.02){m=mm;hit=true;break;}t+=h;if(t>140.)break;}",
    " float L=0.,h=0.;vec3 col;vec3 p=ro+rd*t;",
    " if(hit&&m==4){col=OPEN;gl_FragColor=vec4(mix(col,PAPER,u_in*.3),1.);return;}",
    " if(hit){vec3 n=normal(p);",
    "  if(m==1&&n.z>.7){col=MERGE;gl_FragColor=vec4(col,1.);return;}",    // the face of the mark, flat, in its own colour
    "  if(m==1){col=MDEEP*(.35+.65*lamp(p,n)*u_power);gl_FragColor=vec4(col,1.);return;}",
    "  L=.03+lamp(p,n)*u_power;",
    "  if(m==2)L+=.25*u_power;",   // the room's back wall is close to the lamp
    // the cursor's own small lime light on the floor
    "  float cd=length(p-u_cursor);L+=u_alpha*.9*exp(-cd/3.);h+=u_alpha*1.2*exp(-cd/3.);",
    " }else{L=0.;}",
    // light in the air: the room's open front and its door gap throw beams, so air inside
    // those two volumes glows with the lamp's falloff (no shadow march, which cost 2 fps)
    " float glow=0.;float tmax=min(t,80.);float step=tmax/12.;",
    " for(int i=0;i<12;i++){float ti=(float(i)+.5+.5*bayer(cell))*step;vec3 q=ro+rd*ti;",
    "  float front=step*0.;",
    "  bool room=q.x>4.&&q.x<16.&&q.y>0.&&q.y<12.&&abs(q.z)<3.;",
    "  float f=q.z-3.;bool beamF=f>0.&&q.x>4.-f*.35&&q.x<16.+f*.35&&q.y>-.5&&q.y<12.+f*.3;",
    "  float g=q.x-20.;bool beamG=g>0.&&q.y>2.-g*.25&&q.y<8.+g*.35&&abs(q.z)<3.+g*.45;",
    "  if(!(room||beamF||beamG))continue;float d=length(LAMP-q);glow+=step*(beamG?14.:9.)/(d*d+40.);}",
    " L+=glow*u_power;h+=glow*u_in*2.;",
    " h+=u_in*.9;",
    " L*=1.+u_motion*(.03*sin(u_time*1.3)+.02*sin(u_time*3.7+1.));",
    " float idx=floor(clamp(L,0.,1.)*6.+bayer(cell));",
    " col=ramp(idx,clamp(h,0.,1.));",
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
  ["u_res", "u_time", "u_eye", "u_at", "u_cursor", "u_alpha", "u_in", "u_power", "u_motion"].forEach(function (n) {
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

  var cols = 0, rows = 0, cell = 4, band = false;
  // World units are the G's own cells; the door gap is at x = 20, y 8..14. Outside, the
  // threshold, and inside, along the floor in front of the gap.
  var OUTSIDE = 40, THRESHOLD = 23, IN = 10;
  var cur = { x: THRESHOLD, z: 0 }, alpha = 1, target = null;
  var start = performance.now() / 1000, idleStart = start, followUntil = 0, lastStep = 0;
  var typedUntil = 0, typedX = OUTSIDE, entering = false, entered = false, enterAt = 0;
  var visible = true, raf = 0;
  var lookX = 0, lookY = 0, yaw = 0, pitch = 0;

  function size() {
    var W = scene.clientWidth, H = scene.clientHeight;
    if (lost || !W || !H) return;
    band = getComputedStyle(scene).position !== "absolute";
    cell = band ? 3 : 4;
    cols = Math.ceil(W / cell); rows = Math.ceil(H / cell);
    canvas.width = cols; canvas.height = rows;
    canvas.style.width = cols * cell + "px"; canvas.style.height = rows * cell + "px";
    gl.viewport(0, 0, cols, rows);
    gl.uniform2f(U.u_res, cols, rows);
    draw();                           // a frame even in a background tab, so nothing is ever blank
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
    if (s < 1.8) x = OUTSIDE;
    else if (s < 5.2) x = OUTSIDE - Math.floor((s - 1.8) / 3.4 * (OUTSIDE - THRESHOLD));
    else if (s < 6.6) x = THRESHOLD;
    else if (s < 7.8) x = THRESHOLD - Math.floor((s - 6.6) / 1.2 * (THRESHOLD - IN));
    else x = IN;
    cur.x = x;
  }
  function follow(now) {
    alpha = 1;
    if (!target || now - lastStep < 0.05) return;
    lastStep = now;
    cur.x += Math.sign(target - cur.x);
  }

  function draw() {
    var now = performance.now() / 1000, t = now - start;
    if (still) { cur.x = entered ? IN : THRESHOLD; alpha = 1; }
    else if (entering || entered) { alpha = 1; if (now - lastStep > 0.06 && cur.x > IN) { lastStep = now; cur.x -= 1; } if (cur.x <= IN) { entering = false; entered = true; } }
    else if (now < typedUntil) { alpha = 1; cur.x = typedX; }
    else if (now < followUntil) follow(now);
    else idle(now - idleStart);

    // The camera: front and to the right of the G, drifting, leaning with the pointer. On
    // Enter it flies to the gap and through into the room.
    var drift = 0;   // the mark holds still; only the pointer leans the view and Enter moves it
    yaw += ((band ? 0.55 : 0.42) + lookX * 0.18 + drift - yaw) * 0.06;
    pitch += (0.3 + lookY * 0.1 - pitch) * 0.06;
    // the look-at point sits left of the G on wide screens, so the G stands in the open
    // right half beside the copy
    var R = band ? 66 : 54;
    var at = [band ? 10 : -3, 8, 0], eye = [at[0] + R * Math.sin(yaw) * Math.cos(pitch), at[1] + R * Math.sin(pitch), at[2] + R * Math.cos(yaw) * Math.cos(pitch)];
    var inside = 0;
    if (entering || entered) {
      var k = Math.min(1, (now - enterAt) / 1.7), e = k * k * (3 - 2 * k);
      var gap = [24, 5, 0], room = [12, 5, -1];
      var dest = e < 0.6 ? gap : room;
      var ee = e < 0.6 ? e / 0.6 : (e - 0.6) / 0.4;
      var from = e < 0.6 ? eye : gap;
      eye = [from[0] + (dest[0] - from[0]) * ee, from[1] + (dest[1] - from[1]) * ee, from[2] + (dest[2] - from[2]) * ee];
      at = [room[0] - 4, 5, -1];
      inside = Math.max(0, (e - 0.55) / 0.45);
    }
    gl.uniform1f(U.u_time, t);
    gl.uniform3f(U.u_eye, eye[0], eye[1], eye[2]);
    gl.uniform3f(U.u_at, at[0], at[1], at[2]);
    gl.uniform3f(U.u_cursor, cur.x, 2, cur.z);
    gl.uniform1f(U.u_alpha, alpha);
    gl.uniform1f(U.u_in, inside);
    gl.uniform1f(U.u_power, power(t));
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

  // The pointer leans the camera; over the copy it does nothing.
  function point(e) {
    if (lost || still || entering || entered || (e.target.closest && e.target.closest(".hero-copy"))) return;
    var r = canvas.getBoundingClientRect();
    lookX = ((e.clientX - r.left) / r.width - 0.5) * 2;
    lookY = ((e.clientY - r.top) / r.height - 0.5) * -2;
    // a pointer in the field also calls the cursor over, a step at a time
    var x = (e.clientX - r.left) / r.width;
    if (x > 0.55) { target = Math.round(THRESHOLD + (x - 0.55) / 0.45 * (OUTSIDE - THRESHOLD)); var now = performance.now() / 1000; if (now >= followUntil) alpha = 1; followUntil = now + 2.5; idleStart = followUntil; }
  }
  hero.addEventListener("pointermove", point);
  hero.addEventListener("pointerleave", function () { lookX = 0; lookY = 0; });

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
      typedX = OUTSIDE - Math.round(Math.max(0, Math.min(1, fraction)) * (OUTSIDE - THRESHOLD));
      typedUntil = performance.now() / 1000 + 6;
      idleStart = typedUntil;
      wake();
    },
    enter: function (done) {
      if (lost || entered) { done(); return; }
      entering = true;
      enterAt = performance.now() / 1000;
      lastStep = 0;
      wake();
      if (still) draw();
      setTimeout(done, still ? 80 : 1900);
    },
    still: still
  };
})();
