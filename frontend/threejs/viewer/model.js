/**
 * model.js — IFC 模型加载（JSON 转 Three.js Mesh）
 *
 * 用 Python 转换好的 ifc.json（本质是 IFC 几何体三角化结果）。
 * 提供：loadIFC(scene, url) → 加到场景，返回 guidMap
 */

import * as THREE from 'three';

const IFC_COLORS = {
  'IfcWall':                 0xc8b89a,
  'IfcSlab':                 0x8a9aa8,
  'IfcRoof':                 0x6a5a4a,
  'IfcSpace':                0x4a8a5c,
  'IfcFurniture':            0x9a7a5a,
  'IfcBuildingElementProxy': 0x6b8cae,
  'IfcFurnishingElement':    0x9a7a5a,
  'IfcSpatialZone':          0x4a8a5c,
};

export async function loadIFC(scene, url = './ifc.json') {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`fetch ifc.json: ${resp.status}`);
  const data = await resp.json();
  if (!data.meshes || !data.meshes.length) throw new Error('empty meshes');

  const guidMap = new Map();

  // Compute scene center
  let count = 0;
  const center = new THREE.Vector3();
  for (const m of data.meshes) {
    for (let i = 0; i < m.vertices.length; i += 3) {
      center.x += m.vertices[i];
      center.y += m.vertices[i+1];
      center.z += m.vertices[i+2];
      count++;
    }
  }
  if (count > 0) center.divideScalar(count);

  for (const m of data.meshes) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(m.vertices), 3));
    geo.setIndex(m.faces);
    geo.computeVertexNormals();

    const color = IFC_COLORS[m.type] || 0x4a6fa5;
    const mat = new THREE.MeshStandardMaterial({
      color, roughness: 0.6, metalness: 0.2,
      side: THREE.DoubleSide,
    });

    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(center.clone().negate());
    mesh.userData.guid = m.guid;
    mesh.userData.name = m.name;
    mesh.castShadow = true;
    mesh.receiveShadow = true;

    scene.add(mesh);
    guidMap.set(m.guid, mesh);
  }

  console.log(`IFC loaded: ${data.meshes.length} meshes, ${guidMap.size} GUIDs`);
  return guidMap;
}

export function setMeshColor(guidMap, guid, color) {
  const mesh = guidMap.get(guid);
  if (!mesh) { console.warn('mesh not found:', guid); return false; }
  mesh.material.color.setHex(color);
  mesh.visible = true;
  if (color !== 0x4ade80) {
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = 0.2;
  } else {
    mesh.material.emissive.setHex(0x000000);
    mesh.material.emissiveIntensity = 0;
  }
  mesh.material.needsUpdate = true;
  return true;
}
