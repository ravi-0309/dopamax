/* LightPillar — vanilla port of the React Bits component (Three.js).
   Usage: initLightPillar(containerEl, { topColor, bottomColor, ... }) */
(function () {
  function initLightPillar(container, opts) {
    opts = opts || {};
    if (!container || !window.THREE) return;
    var THREE = window.THREE;

    var topColor = opts.topColor || '#5227FF';
    var bottomColor = opts.bottomColor || '#FF9FFC';
    var intensity = opts.intensity != null ? opts.intensity : 1.0;
    var rotationSpeed = opts.rotationSpeed != null ? opts.rotationSpeed : 0.3;
    var glowAmount = opts.glowAmount != null ? opts.glowAmount : 0.005;
    var pillarWidth = opts.pillarWidth != null ? opts.pillarWidth : 3.0;
    var pillarHeight = opts.pillarHeight != null ? opts.pillarHeight : 0.4;
    var noiseIntensity = opts.noiseIntensity != null ? opts.noiseIntensity : 0.5;
    var pillarRotation = opts.pillarRotation || 0;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    var quality = isMobile ? 'low' : 'medium';
    var QS = {
      low:    { iterations: 24, waveIterations: 1, pixelRatio: 0.5,  precision: 'mediump', stepMultiplier: 1.5 },
      medium: { iterations: 40, waveIterations: 2, pixelRatio: 0.65, precision: 'mediump', stepMultiplier: 1.2 },
      high:   { iterations: 80, waveIterations: 4, pixelRatio: Math.min(window.devicePixelRatio, 2), precision: 'highp', stepMultiplier: 1.0 }
    };
    var s = QS[quality];

    var width = container.clientWidth || window.innerWidth;
    var height = container.clientHeight || window.innerHeight;

    var scene = new THREE.Scene();
    var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: 'low-power', precision: s.precision, stencil: false, depth: false });
    } catch (e) { return; }
    renderer.setSize(width, height);
    renderer.setPixelRatio(s.pixelRatio);
    container.appendChild(renderer.domElement);

    function pc(hex) { var c = new THREE.Color(hex); return new THREE.Vector3(c.r, c.g, c.b); }

    var vert = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position, 1.0); }';

    var frag =
      'precision ' + s.precision + ' float;' +
      'uniform float uTime; uniform vec2 uResolution; uniform vec2 uMouse;' +
      'uniform vec3 uTopColor; uniform vec3 uBottomColor; uniform float uIntensity;' +
      'uniform bool uInteractive; uniform float uGlowAmount; uniform float uPillarWidth;' +
      'uniform float uPillarHeight; uniform float uNoiseIntensity;' +
      'uniform float uRotCos; uniform float uRotSin; uniform float uPillarRotCos; uniform float uPillarRotSin;' +
      'uniform float uWaveSin; uniform float uWaveCos; varying vec2 vUv;' +
      'const float STEP_MULT = ' + s.stepMultiplier.toFixed(1) + ';' +
      'const int MAX_ITER = ' + s.iterations + ';' +
      'const int WAVE_ITER = ' + s.waveIterations + ';' +
      'void main(){' +
      '  vec2 uv = (vUv * 2.0 - 1.0) * vec2(uResolution.x / uResolution.y, 1.0);' +
      '  uv = vec2(uPillarRotCos * uv.x - uPillarRotSin * uv.y, uPillarRotSin * uv.x + uPillarRotCos * uv.y);' +
      '  vec3 ro = vec3(0.0, 0.0, -10.0);' +
      '  vec3 rd = normalize(vec3(uv, 1.0));' +
      '  float rotC = uRotCos; float rotS = uRotSin;' +
      '  if(uInteractive && (uMouse.x != 0.0 || uMouse.y != 0.0)) { float a = uMouse.x * 6.283185; rotC = cos(a); rotS = sin(a); }' +
      '  vec3 col = vec3(0.0); float t = 0.1;' +
      '  for(int i = 0; i < MAX_ITER; i++){' +
      '    vec3 p = ro + rd * t;' +
      '    p.xz = vec2(rotC * p.x - rotS * p.z, rotS * p.x + rotC * p.z);' +
      '    vec3 q = p; q.y = p.y * uPillarHeight + uTime;' +
      '    float freq = 1.0; float amp = 1.0;' +
      '    for(int j = 0; j < WAVE_ITER; j++){' +
      '      q.xz = vec2(uWaveCos * q.x - uWaveSin * q.z, uWaveSin * q.x + uWaveCos * q.z);' +
      '      q += cos(q.zxy * freq - uTime * float(j) * 2.0) * amp; freq *= 2.0; amp *= 0.5;' +
      '    }' +
      '    float d = length(cos(q.xz)) - 0.2;' +
      '    float bound = length(p.xz) - uPillarWidth;' +
      '    float k = 4.0; float h = max(k - abs(d - bound), 0.0);' +
      '    d = max(d, bound) + h * h * 0.0625 / k;' +
      '    d = abs(d) * 0.15 + 0.01;' +
      '    float grad = clamp((15.0 - p.y) / 30.0, 0.0, 1.0);' +
      '    col += mix(uBottomColor, uTopColor, grad) / d;' +
      '    t += d * STEP_MULT; if(t > 50.0) break;' +
      '  }' +
      '  float widthNorm = uPillarWidth / 3.0;' +
      '  col = tanh(col * uGlowAmount / widthNorm);' +
      '  col -= fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) / 15.0 * uNoiseIntensity;' +
      '  gl_FragColor = vec4(col * uIntensity, 1.0);' +
      '}';

    var pillarRotRad = (pillarRotation * Math.PI) / 180;
    var material = new THREE.ShaderMaterial({
      vertexShader: vert,
      fragmentShader: frag,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: new THREE.Vector2(width, height) },
        uMouse: { value: new THREE.Vector2(0, 0) },
        uTopColor: { value: pc(topColor) },
        uBottomColor: { value: pc(bottomColor) },
        uIntensity: { value: intensity },
        uInteractive: { value: false },
        uGlowAmount: { value: glowAmount },
        uPillarWidth: { value: pillarWidth },
        uPillarHeight: { value: pillarHeight },
        uNoiseIntensity: { value: noiseIntensity },
        uRotCos: { value: 1.0 },
        uRotSin: { value: 0.0 },
        uPillarRotCos: { value: Math.cos(pillarRotRad) },
        uPillarRotSin: { value: Math.sin(pillarRotRad) },
        uWaveSin: { value: Math.sin(0.4) },
        uWaveCos: { value: Math.cos(0.4) }
      },
      transparent: true, depthWrite: false, depthTest: false
    });

    var mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    scene.add(mesh);

    var time = 0, lastTime = performance.now();
    var targetFPS = quality === 'low' ? 30 : 60;
    var frameTime = 1000 / targetFPS;
    function animate(now) {
      var dt = now - lastTime;
      if (dt >= frameTime) {
        time += 0.016 * rotationSpeed;
        material.uniforms.uTime.value = time;
        material.uniforms.uRotCos.value = Math.cos(time * 0.3);
        material.uniforms.uRotSin.value = Math.sin(time * 0.3);
        renderer.render(scene, camera);
        lastTime = now - (dt % frameTime);
      }
      requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);

    var resizeT = null;
    window.addEventListener('resize', function () {
      if (resizeT) clearTimeout(resizeT);
      resizeT = setTimeout(function () {
        var w = container.clientWidth || window.innerWidth;
        var h = container.clientHeight || window.innerHeight;
        renderer.setSize(w, h);
        material.uniforms.uResolution.value.set(w, h);
      }, 150);
    }, { passive: true });
  }

  window.initLightPillar = initLightPillar;
})();
