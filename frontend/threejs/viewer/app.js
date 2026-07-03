/**
 * app.js — Three.js 数字孪生场景
 *
 * 契约：
 *   1. 连接 ws://localhost:8000/ws/twin
 *   2. 收到 SNAPSHOT → 为每个资产建 Box Mesh，按 GUID 索引
 *   3. 收到 INCREMENT → 根据 status 切换材质颜色
 *   4. 零轮询，全量由 WebSocket 驱动
 *
 * 颜色映射（Architecture.md §7）：
 *   Normal → 绿 (#4ade80)
 *   Warning → 黄 (#facc15)
 *   Critical → 红 (#ef4444)
 *   Offline → 灰 (#6b7280)
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

// ── 常量 ──────────────────────────────────────
const STATUS_COLORS = {
  Normal:   0x4ade80,
  Warning:  0xfacc15,
  Critical: 0xef4444,
  Alarm:    0xef4444,   // state.py 用 Critical, 兼容两种
  Offline:  0x6b7280,
};
const DEFAULT_COLOR = 0x4ade80;
const WS_URL = `ws://${location.hostname}:8000/ws/twin`;

// ── DOM refs ──────────────────────────────────
const container = document.getElementById('scene-container');
const dot = document.getElementById('conn-dot');
const connLabel = document.getElementById('conn-label');
const tooltip = document.getElementById('tooltip');
const tipGuid = document.getElementById('tip-guid');
const tipDetail = document.getElementById('tip-detail');

// ── Three.js 场景 ─────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0e17);

const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
camera.position.set(12, 8, 12);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;
container.appendChild(renderer.domElement);

const labelRenderer = new CSS2DRenderer();
labelRenderer.setSize(container.clientWidth, container.clientHeight);
labelRenderer.domElement.style.position = 'absolute';
labelRenderer.domElement.style.top = '0';
labelRenderer.domElement.style.left = '0';
labelRenderer.domElement.style.pointerEvents = 'none'; // 点击穿透
container.appendChild(labelRenderer.domElement);

// ── 控制器 ────────────────────────────────────
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 3;
controls.maxDistance = 40;
controls.target.set(0, 0, 0);

// ── 灯光 ──────────────────────────────────────
const ambientLight = new THREE.AmbientLight(0x404060, 0.6);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xffeedd, 2.5);
dirLight.position.set(15, 20, 10);
dirLight.castShadow = true;
dirLight.shadow.mapSize.width = 1024;
dirLight.shadow.mapSize.height = 1024;
scene.add(dirLight);

const fillLight = new THREE.DirectionalLight(0x4488ff, 0.4);
fillLight.position.set(-10, 5, -10);
scene.add(fillLight);

// 地面网格
const gridHelper = new THREE.GridHelper(30, 20, 0x2a3a5c, 0x1a2a4c);
scene.add(gridHelper);

// 地面圆盘
const groundGeo = new THREE.CircleGeometry(15, 64);
const groundMat = new THREE.MeshStandardMaterial({
  color: 0x0d1120,
  roughness: 0.9,
  metalness: 0.0,
  transparent: true,
  opacity: 0.6,
  side: THREE.DoubleSide,
});
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.05;
ground.receiveShadow = true;
scene.add(ground);

// ── 资产地图 ──────────────────────────────────
const assetMeshes = new Map(); // guid → { mesh, label, data }

function createLabel(text) {
  const div = document.createElement('div');
  div.textContent = text;
  div.style.color = 'rgba(255,255,255,0.6)';
  div.style.fontSize = '10px';
  div.style.fontWeight = '500';
  div.style.fontFamily = 'monospace';
  div.style.textShadow = '0 1px 4px rgba(0,0,0,0.8)';
  div.style.pointerEvents = 'none';
  return new CSS2DObject(div);
}

function buildScene(snapshot) {
  // 清除旧资产
  for (const [, entry] of assetMeshes) {
    scene.remove(entry.mesh);
    scene.remove(entry.label);
  }
  assetMeshes.clear();

  const entries = Object.entries(snapshot);
  const count = entries.length;
  if (count === 0) return;

  // 自动布局：环形或网格
  const cols = Math.ceil(Math.sqrt(count));
  const spacing = 3.5;
  const offset = (cols - 1) * spacing / 2;

  entries.forEach(([guid, data], i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = col * spacing - offset;
    const z = row * spacing - offset;

    // 随机高度变化，看起来不呆板
    const h = 1.0 + Math.random() * 1.5;
    const color = STATUS_COLORS[data.status] || DEFAULT_COLOR;

    const geo = new THREE.BoxGeometry(1.8, h, 1.8);
    const mat = new THREE.MeshStandardMaterial({
      color,
      roughness: 0.3,
      metalness: 0.4,
      emissive: color,
      emissiveIntensity: 0.08,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(x, h / 2, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.guid = guid;
    scene.add(mesh);

    // 标签
    const label = createLabel(guid.length > 20 ? guid.slice(0, 18) + '…' : guid);
    label.position.set(x, h + 0.4, z);
    scene.add(label);

    assetMeshes.set(guid, { mesh, label, data: { ...data } });
  });
}

function applyIncrement(data) {
  const guid = data.guid || data.asset_id;
  const entry = assetMeshes.get(guid);
  if (!entry) return;

  const status = data.status || 'Normal';
  const value = data.value;
  const color = STATUS_COLORS[status] || DEFAULT_COLOR;

  entry.mesh.material.color.setHex(color);
  entry.mesh.material.emissive.setHex(color);
  entry.mesh.material.emissiveIntensity = status === 'Critical' || status === 'Alarm' ? 0.4 : 0.08;

  entry.data.status = status;
  entry.data.value = value;
  entry.data.timestamp = data.timestamp;

  // 报警时轻微脉冲动画
  if (status === 'Critical' || status === 'Alarm') {
    entry.mesh.userData.pulse = true;
  } else {
    entry.mesh.userData.pulse = false;
    entry.mesh.scale.set(1, 1, 1);
  }

  updateHUD();
}

// ── HUD 更新 ─────────────────────────────────
function updateHUD() {
  let n = 0, w = 0, c = 0, o = 0;
  for (const [, entry] of assetMeshes) {
    switch (entry.data.status) {
      case 'Normal': n++; break;
      case 'Warning': w++; break;
      case 'Critical':
      case 'Alarm': c++; break;
      case 'Offline': o++; break;
      default: n++;
    }
  }
  document.getElementById('c-normal').textContent = n;
  document.getElementById('c-warning').textContent = w;
  document.getElementById('c-alarm').textContent = c;
  document.getElementById('c-offline').textContent = o;
}

// ── WebSocket ────────────────────────────────
let ws = null;
let reconnectTimer = null;

function setConnState(state) {
  dot.className = state;
  if (state === 'connected') {
    connLabel.textContent = '已连接';
  } else if (state === 'connecting') {
    connLabel.textContent = '连接中…';
  } else {
    connLabel.textContent = '未连接';
  }
}

function connectWS() {
  setConnState('connecting');

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setConnState('connected');
  };

  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === 'SNAPSHOT') {
        buildScene(msg.data);
        updateHUD();
        console.log(`SNAPSHOT loaded: ${Object.keys(msg.data).length} assets`);
      } else if (msg.type === 'INCREMENT') {
        applyIncrement(msg.data);
        console.log('INCREMENT:', msg.data.guid, msg.data.status, msg.data.value);
      }
    } catch (err) {
      console.warn('WS parse error:', err);
    }
  };

  ws.onclose = () => {
    setConnState('disconnected');
    // 3 秒后重连
    reconnectTimer = setTimeout(connectWS, 3000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

// ── 动画循环 ─────────────────────────────────
function animate() {
  requestAnimationFrame(animate);

  // 脉冲动画：Alarm 资产周期性缩放
  const t = Date.now() * 0.003;
  for (const [, entry] of assetMeshes) {
    if (entry.mesh.userData.pulse) {
      const s = 1 + Math.sin(t) * 0.05;
      entry.mesh.scale.set(s, 1, s);
    }
  }

  controls.update();
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}

// ── Raycaster 悬停 tooltip ───────────────────
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

renderer.domElement.addEventListener('pointermove', (event) => {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

  raycaster.setFromCamera(pointer, camera);
  const meshes = Array.from(assetMeshes.values()).map(e => e.mesh);
  const intersects = raycaster.intersectObjects(meshes);

  if (intersects.length > 0) {
    const hit = intersects[0].object;
    const guid = hit.userData.guid;
    const entry = assetMeshes.get(guid);
    if (entry) {
      tipGuid.textContent = guid;
      tipDetail.textContent = `${entry.data.status} · ${entry.data.value?.toFixed(1) ?? '-'} ${entry.data.metric || ''}`.trim();
      tooltip.style.display = 'block';
      tooltip.style.left = (event.clientX + 14) + 'px';
      tooltip.style.top = (event.clientY + 14) + 'px';
      // 边界检测
      const tr = tooltip.getBoundingClientRect();
      if (tr.right > window.innerWidth) {
        tooltip.style.left = (event.clientX - tr.width - 14) + 'px';
      }
      if (tr.bottom > window.innerHeight) {
        tooltip.style.top = (event.clientY - tr.height - 14) + 'px';
      }
    }
  } else {
    tooltip.style.display = 'none';
  }
});

// ── 自适应 ────────────────────────────────────
window.addEventListener('resize', () => {
  const w = container.clientWidth;
  const h = container.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  labelRenderer.setSize(w, h);
});

// ── 启动 ──────────────────────────────────────
connectWS();
animate();
