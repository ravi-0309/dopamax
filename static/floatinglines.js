/* FloatingLines — vanilla port of the React Bits component (Three.js).
   Usage: initFloatingLines(containerEl, { ...opts }) */
(function () {
  var vertexShader =
    'precision highp float; void main(){ gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }';

  var fragmentShader = [
    'precision highp float;',
    'uniform float iTime; uniform vec3 iResolution; uniform float animationSpeed;',
    'uniform bool enableTop; uniform bool enableMiddle; uniform bool enableBottom;',
    'uniform int topLineCount; uniform int middleLineCount; uniform int bottomLineCount;',
    'uniform float topLineDistance; uniform float middleLineDistance; uniform float bottomLineDistance;',
    'uniform vec3 topWavePosition; uniform vec3 middleWavePosition; uniform vec3 bottomWavePosition;',
    'uniform vec2 iMouse; uniform bool interactive; uniform float bendRadius; uniform float bendStrength;',
    'uniform float bendInfluence; uniform bool parallax; uniform float parallaxStrength; uniform vec2 parallaxOffset;',
    'uniform vec3 lineGradient[8]; uniform int lineGradientCount;',
    'const vec3 BLACK = vec3(0.0);',
    'const vec3 PINK = vec3(233.0,71.0,245.0)/255.0;',
    'const vec3 BLUE = vec3(47.0,75.0,162.0)/255.0;',
    'mat2 rotate(float r){ return mat2(cos(r),sin(r),-sin(r),cos(r)); }',
    'vec3 background_color(vec2 uv){ vec3 col=vec3(0.0); float y=sin(uv.x-0.2)*0.3-0.1; float m=uv.y-y;',
    '  col+=mix(BLUE,BLACK,smoothstep(0.0,1.0,abs(m))); col+=mix(PINK,BLACK,smoothstep(0.0,1.0,abs(m-0.8))); return col*0.5; }',
    'vec3 getLineColor(float t, vec3 baseColor){ if(lineGradientCount<=0){ return baseColor; } vec3 g;',
    '  if(lineGradientCount==1){ g=lineGradient[0]; } else { float ct=clamp(t,0.0,0.9999); float sc=ct*float(lineGradientCount-1);',
    '  int idx=int(floor(sc)); float f=fract(sc); int idx2=min(idx+1,lineGradientCount-1); g=mix(lineGradient[idx],lineGradient[idx2],f); } return g*0.5; }',
    'float wave(vec2 uv, float offset, vec2 screenUv, vec2 mouseUv, bool shouldBend){',
    '  float time=iTime*animationSpeed; float x_offset=offset; float x_movement=time*0.1;',
    '  float amp=sin(offset+time*0.2)*0.3; float y=sin(uv.x+x_offset+x_movement)*amp;',
    '  if(shouldBend){ vec2 d=screenUv-mouseUv; float influence=exp(-dot(d,d)*bendRadius);',
    '  float bendOffset=(mouseUv.y-screenUv.y)*influence*bendStrength*bendInfluence; y+=bendOffset; }',
    '  float m=uv.y-y; return 0.0175/max(abs(m)+0.01,1e-3)+0.01; }',
    'void mainImage(out vec4 fragColor, in vec2 fragCoord){',
    '  vec2 baseUv=(2.0*fragCoord-iResolution.xy)/iResolution.y; baseUv.y*=-1.0;',
    '  if(parallax){ baseUv+=parallaxOffset; }',
    '  vec3 col=vec3(0.0); vec3 b=lineGradientCount>0?vec3(0.0):background_color(baseUv);',
    '  vec2 mouseUv=vec2(0.0); if(interactive){ mouseUv=(2.0*iMouse-iResolution.xy)/iResolution.y; mouseUv.y*=-1.0; }',
    '  if(enableBottom){ for(int i=0;i<bottomLineCount;++i){ float fi=float(i); float t=fi/max(float(bottomLineCount-1),1.0);',
    '    vec3 lc=getLineColor(t,b); float angle=bottomWavePosition.z*log(length(baseUv)+1.0); vec2 ruv=baseUv*rotate(angle);',
    '    col+=lc*wave(ruv+vec2(bottomLineDistance*fi+bottomWavePosition.x,bottomWavePosition.y),1.5+0.2*fi,baseUv,mouseUv,interactive)*0.2; } }',
    '  if(enableMiddle){ for(int i=0;i<middleLineCount;++i){ float fi=float(i); float t=fi/max(float(middleLineCount-1),1.0);',
    '    vec3 lc=getLineColor(t,b); float angle=middleWavePosition.z*log(length(baseUv)+1.0); vec2 ruv=baseUv*rotate(angle);',
    '    col+=lc*wave(ruv+vec2(middleLineDistance*fi+middleWavePosition.x,middleWavePosition.y),2.0+0.15*fi,baseUv,mouseUv,interactive); } }',
    '  if(enableTop){ for(int i=0;i<topLineCount;++i){ float fi=float(i); float t=fi/max(float(topLineCount-1),1.0);',
    '    vec3 lc=getLineColor(t,b); float angle=topWavePosition.z*log(length(baseUv)+1.0); vec2 ruv=baseUv*rotate(angle); ruv.x*=-1.0;',
    '    col+=lc*wave(ruv+vec2(topLineDistance*fi+topWavePosition.x,topWavePosition.y),1.0+0.2*fi,baseUv,mouseUv,interactive)*0.1; } }',
    '  fragColor=vec4(col,1.0); }',
    'void main(){ vec4 c=vec4(0.0); mainImage(c, gl_FragCoord.xy); gl_FragColor=c; }'
  ].join('\n');

  function hexToVec3(THREE, hex) {
    var v = (hex || '').trim().replace('#', '');
    var r = 255, g = 255, b = 255;
    if (v.length === 3) { r = parseInt(v[0] + v[0], 16); g = parseInt(v[1] + v[1], 16); b = parseInt(v[2] + v[2], 16); }
    else if (v.length === 6) { r = parseInt(v.slice(0, 2), 16); g = parseInt(v.slice(2, 4), 16); b = parseInt(v.slice(4, 6), 16); }
    return new THREE.Vector3(r / 255, g / 255, b / 255);
  }

  function initFloatingLines(container, opts) {
    opts = opts || {};
    if (!container || !window.THREE) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var THREE = window.THREE;

    var enabledWaves = opts.enabledWaves || ['top', 'middle', 'bottom'];
    var lineCount = opts.lineCount != null ? opts.lineCount : [6];
    var lineDistance = opts.lineDistance != null ? opts.lineDistance : [5];
    var animationSpeed = opts.animationSpeed != null ? opts.animationSpeed : 1;
    var interactive = opts.interactive !== false;
    var bendRadius = opts.bendRadius != null ? opts.bendRadius : 5.0;
    var bendStrength = opts.bendStrength != null ? opts.bendStrength : -0.5;
    var mouseDamping = opts.mouseDamping != null ? opts.mouseDamping : 0.05;
    var parallax = opts.parallax !== false;
    var parallaxStrength = opts.parallaxStrength != null ? opts.parallaxStrength : 0.2;
    var linesGradient = opts.linesGradient || null;

    function has(w) { return enabledWaves.indexOf(w) > -1; }
    function perWave(val, w, dflt) {
      if (typeof val === 'number') return val;
      if (!has(w)) return dflt;
      var i = enabledWaves.indexOf(w);
      return (val[i] != null) ? val[i] : dflt;
    }
    var topLC = has('top') ? perWave(lineCount, 'top', 6) : 0;
    var midLC = has('middle') ? perWave(lineCount, 'middle', 6) : 0;
    var botLC = has('bottom') ? perWave(lineCount, 'bottom', 6) : 0;
    var topLD = has('top') ? perWave(lineDistance, 'top', 5) * 0.01 : 0.01;
    var midLD = has('middle') ? perWave(lineDistance, 'middle', 5) * 0.01 : 0.01;
    var botLD = has('bottom') ? perWave(lineDistance, 'bottom', 5) * 0.01 : 0.01;

    var scene = new THREE.Scene();
    var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    camera.position.z = 1;
    var renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false }); } catch (e) { return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    container.appendChild(renderer.domElement);

    var tp = opts.topWavePosition || {}, mp = opts.middleWavePosition || {}, bp = opts.bottomWavePosition || { x: 2.0, y: -0.7, rotate: -1 };
    var grad = [];
    for (var i = 0; i < 8; i++) grad.push(new THREE.Vector3(1, 1, 1));
    var gradCount = 0;
    if (linesGradient && linesGradient.length) {
      var stops = linesGradient.slice(0, 8);
      gradCount = stops.length;
      stops.forEach(function (hex, idx) { var c = hexToVec3(THREE, hex); grad[idx].set(c.x, c.y, c.z); });
    }

    var uniforms = {
      iTime: { value: 0 }, iResolution: { value: new THREE.Vector3(1, 1, 1) },
      animationSpeed: { value: animationSpeed },
      enableTop: { value: has('top') }, enableMiddle: { value: has('middle') }, enableBottom: { value: has('bottom') },
      topLineCount: { value: topLC }, middleLineCount: { value: midLC }, bottomLineCount: { value: botLC },
      topLineDistance: { value: topLD }, middleLineDistance: { value: midLD }, bottomLineDistance: { value: botLD },
      topWavePosition: { value: new THREE.Vector3(tp.x != null ? tp.x : 10.0, tp.y != null ? tp.y : 0.5, tp.rotate != null ? tp.rotate : -0.4) },
      middleWavePosition: { value: new THREE.Vector3(mp.x != null ? mp.x : 5.0, mp.y != null ? mp.y : 0.0, mp.rotate != null ? mp.rotate : 0.2) },
      bottomWavePosition: { value: new THREE.Vector3(bp.x != null ? bp.x : 2.0, bp.y != null ? bp.y : -0.7, bp.rotate != null ? bp.rotate : 0.4) },
      iMouse: { value: new THREE.Vector2(-1000, -1000) },
      interactive: { value: interactive }, bendRadius: { value: bendRadius }, bendStrength: { value: bendStrength }, bendInfluence: { value: 0 },
      parallax: { value: parallax }, parallaxStrength: { value: parallaxStrength }, parallaxOffset: { value: new THREE.Vector2(0, 0) },
      lineGradient: { value: grad }, lineGradientCount: { value: gradCount }
    };

    var material = new THREE.ShaderMaterial({ uniforms: uniforms, vertexShader: vertexShader, fragmentShader: fragmentShader });
    var mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    scene.add(mesh);
    var clock = new THREE.Clock();

    function setSize() {
      var w = container.clientWidth || window.innerWidth, h = container.clientHeight || window.innerHeight;
      renderer.setSize(w, h, false);
      uniforms.iResolution.value.set(renderer.domElement.width, renderer.domElement.height, 1);
    }
    setSize();
    if (typeof ResizeObserver !== 'undefined') { new ResizeObserver(setSize).observe(container); }
    window.addEventListener('resize', setSize, { passive: true });

    var targetMouse = new THREE.Vector2(-1000, -1000), curMouse = new THREE.Vector2(-1000, -1000);
    var targetInf = 0, curInf = 0, targetPar = new THREE.Vector2(0, 0), curPar = new THREE.Vector2(0, 0);
    if (interactive) {
      renderer.domElement.addEventListener('pointermove', function (e) {
        var rect = renderer.domElement.getBoundingClientRect();
        var x = e.clientX - rect.left, y = e.clientY - rect.top, dpr = renderer.getPixelRatio();
        targetMouse.set(x * dpr, (rect.height - y) * dpr);
        targetInf = 1.0;
        if (parallax) {
          var ox = (x - rect.width / 2) / rect.width, oy = -(y - rect.height / 2) / rect.height;
          targetPar.set(ox * parallaxStrength, oy * parallaxStrength);
        }
      });
      renderer.domElement.addEventListener('pointerleave', function () { targetInf = 0.0; });
    }

    (function loop() {
      uniforms.iTime.value = clock.getElapsedTime();
      if (interactive) {
        curMouse.lerp(targetMouse, mouseDamping); uniforms.iMouse.value.copy(curMouse);
        curInf += (targetInf - curInf) * mouseDamping; uniforms.bendInfluence.value = curInf;
      }
      if (parallax) { curPar.lerp(targetPar, mouseDamping); uniforms.parallaxOffset.value.copy(curPar); }
      renderer.render(scene, camera);
      requestAnimationFrame(loop);
    })();
  }

  window.initFloatingLines = initFloatingLines;
})();
