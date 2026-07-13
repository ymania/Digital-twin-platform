/**
 * app.js — Three.js 数字孪生场景
 * IFC 模型加载失败时自动降级为彩色盒子 + 标签
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { loadIFC, setMeshColor } from './model.js';

const STATUS_COLORS = {
  Normal:   0x4ade80,
  Warning:  0xfacc15,
  Alarm:    0xef4444,
  Critical: 0xef4444,
  Offline:  0x6b7280,
};
const WS_URL = `ws://${location.hostname}:8000/ws/twin`;
const container = document.getElementById('scene-container');

// Scene setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0e17);
const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
camera.position.set(12, 8, 12);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
container.appendChild(renderer.domElement);
const labelRenderer = new CSS2DRenderer();
labelRenderer.setSize(container.clientWidth, container.clientHeight);
labelRenderer.domElement.style.position = 'absolute';
labelRenderer.domElement.style.top = '0';
labelRenderer.domElement.style.left = '0';
labelRenderer.domElement.style.pointerEvents = 'none';
container.appendChild(labelRenderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
scene.add(new THREE.AmbientLight(0x404060, 0.6));
const dl = new THREE.DirectionalLight(0xffeedd, 2.5);
dl.position.set(15, 20, 10); scene.add(dl);
const fl = new THREE.DirectionalLight(0x4488ff, 0.4);
fl.position.set(-10, 5, -10); scene.add(fl);
scene.add(new THREE.GridHelper(30, 20, 0x2a3a5c, 0x1a2a4c));

// ── GUID→Mesh map ──────────────────────────
let guidMap = null;
const pendingStates = [];

// Try IFC first, fallback to boxes
loadIFC(scene)
  .then(gm => { guidMap = gm; flushPending(); })
  .catch(err => {
    console.warn('IFC fallback:', err.message);
    guidMap = createFallbackBoxes();
    flushPending();
  });

function createFallbackBoxes() {
  const map = new Map();
  // 10 default GUIDs matching PG seed data
  const defaults = [
    '3zR0BOEcLADRKln4HYporH', '1AQAupaRP1txwK1AGiN61V',
    '3wdauVJT5Fx9drrREiDqA$', '0OfZwWc8j9QP5uX8xPTxDH',
    '1uS5vfZPn9R8PlAaVd73on', '0ZTBBPo6f6bxqV2K7Oelrq',
    '12UVOn4wvAJPMUExKdZLb8', '2e9pghUJbBqR4jTInsONQT',
    '0xY$LvXaDEswJDk_VU74C_', '18QhMtUIXBvQktPHXXxs7H',
  ];
  const colors = [0xc8b89a, 0x8a9aa8, 0x6a5a4a, 0x4a8a5c, 0x9a7a5a, 0x6b8cae, 0x7a9a8a, 0xb89a7a, 0x5a8a6a, 0x8a7a5a];
  defaults.forEach((guid, i) => {
    const box = new THREE.Mesh(
      new THREE.BoxGeometry(0.8, 0.8, 0.8),
      new THREE.MeshStandardMaterial({
        color: colors[i % colors.length],
        roughness: 0.5, metalness: 0.1,
      })
    );
    const angle = (i / defaults.length) * Math.PI * 2;
    box.position.set(Math.cos(angle) * 4, 0.4, Math.sin(angle) * 4);
    box.userData.guid = guid;
    scene.add(box);
    map.set(guid, box);

    // Label
    const div = document.createElement('div');
    div.textContent = guid.slice(0, 10) + '…';
    div.style.color = 'rgba(255,255,255,0.5)';
    div.style.fontSize = '10px';
    div.style.fontFamily = 'monospace';
    div.style.textShadow = '0 1px 4px rgba(0,0,0,0.8)';
    const label = new CSS2DObject(div);
    label.position.copy(box.position);
    label.position.y += 0.8;
    scene.add(label);
  });
  console.log(`Fallback: ${defaults.length} boxes`);
  return map;
}

function applyState(guid, status, value) {
  if (!guidMap) { pendingStates.push({ guid, status, value }); return; }
  const color = STATUS_COLORS[status] || 0x4ade80;
  setMeshColor(guidMap, guid, color);
}

function flushPending() {
  console.log(`Flushing ${pendingStates.length} pending states`);
  pendingStates.forEach(s => applyState(s.guid, s.status, s.value));
  updateHUD();
}

function updateHUD() {
  let normal = 0, warning = 0, alarm = 0, offline = 0;
  guidMap && guidMap.forEach((mesh, guid) => {
    const c = mesh.material.color.getHex();
    if (c === STATUS_COLORS.Normal) normal++;
    else if (c === STATUS_COLORS.Warning) warning++;
    else if (c === STATUS_COLORS.Alarm || c === STATUS_COLORS.Critical) alarm++;
    else offline++;
  });
  document.getElementById('c-normal').textContent = normal;
  document.getElementById('c-warning').textContent = warning;
  document.getElementById('c-alarm').textContent = alarm;
  document.getElementById('c-offline').textContent = offline;
}

// ── WebSocket ──────────────────────────────
let ws = null;
function connectWS() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    document.getElementById('conn-dot').className = 'connected';
    document.getElementById('conn-label').textContent = '已连接';
  };
  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === 'SNAPSHOT') {
        for (const [guid, info] of Object.entries(msg.data)) {
          applyState(guid, info.status, info.value);
        }
        updateHUD();
      } else if (msg.type === 'INCREMENT') {
        applyState(msg.data.guid, msg.data.status, msg.data.value);
        updateHUD();
      }
    } catch (e) {}
  };
  ws.onclose = () => setTimeout(connectWS, 3000);
}

// ── Animation ──────────────────────────────
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}
window.addEventListener('resize', () => {
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
  labelRenderer.setSize(container.clientWidth, container.clientHeight);
});

connectWS();
animate();
