/**
 * app.js — Three.js 数字孪生场景
 * WS 消息队列：等 IFC 模型加载完后回放 SNAPSHOT
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { loadIFC, setMeshColor } from './model.js';

const STATUS_COLORS = {
  Normal:   0x4ade80,
  Warning:  0xfacc15,
  Critical: 0xef4444,
  Alarm:    0xef4444,
  Offline:  0x6b7280,
};
const WS_URL = `ws://${location.hostname}:8000/ws/twin`;

const container = document.getElementById('scene-container');

// Scene
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

// ── IFC 加载 ─────────────────────────────
let guidMap = null;
const pendingStates = [];  // 模型加载前的 WS 消息缓存

loadIFC(scene).then(gm => {
  guidMap = gm;
  console.log(`IFC ready, replaying ${pendingStates.length} pending states`);
  // 回放缓存的 WS 消息
  while (pendingStates.length) {
    const { guid, status, value } = pendingStates.shift();
    applyState(guid, status, value);
  }
  updateHUD();
});

// ── Asset labels ─────────────────────────
const assetLabels = new Map();

function createLabel(text) {
  const div = document.createElement('div');
  div.textContent = text;
  div.style.color = 'rgba(255,255,255,0.6)';
  div.style.fontSize = '10px';
  div.style.fontFamily = 'monospace';
  div.style.textShadow = '0 1px 4px rgba(0,0,0,0.8)';
  div.style.pointerEvents = 'none';
  return new CSS2DObject(div);
}

function applyState(guid, status, value) {
  if (!guidMap) {
    pendingStates.push({ guid, status, value });
    return;
  }
  const color = STATUS_COLORS[status] || 0x4ade80;
  setMeshColor(guidMap, guid, color);

  if (!assetLabels.has(guid)) {
    const label = createLabel(guid.length > 20 ? guid.slice(0, 18) + '…' : guid);
    const mesh = guidMap.get(guid);
    if (mesh) {
      label.position.copy(mesh.position);
      const bb = new THREE.Box3().setFromObject(mesh);
      label.position.y += bb.max.y + 0.5;
      scene.add(label);
    }
    assetLabels.set(guid, label);
  }
}

function updateHUD() {
  document.getElementById('c-normal').textContent = assetLabels.size;
  document.getElementById('c-warning').textContent = '0';
  document.getElementById('c-alarm').textContent = '0';
  document.getElementById('c-offline').textContent = '0';
}

// ── WebSocket ─────────────────────────────
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
        console.log(`SNAPSHOT: ${Object.keys(msg.data).length}`);
      } else if (msg.type === 'INCREMENT') {
        applyState(msg.data.guid, msg.data.status, msg.data.value);
        updateHUD();
      }
    } catch (e) {}
  };
  ws.onclose = () => setTimeout(connectWS, 3000);
}

// ── Animation ─────────────────────────────
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
