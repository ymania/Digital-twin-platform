/**
 * model.js — IFC 模型加载与 GUID 解析
 *
 * 当前阶段：无 IFC 模型文件，保留接口。
 * Phase 3 后期接入 web-ifc-three 或 IFC.js 后实现。
 *
 * 接口：
 *   loadIFC(url)       → 加载 IFC 模型，返回 Promise<{scene, guidMap}>
 *   getMeshByGuid(guid) → 通过 GUID 获取对应的 Three.js Mesh
 */

export async function loadIFC(url) {
  // TODO: Phase 3 后期接入 web-ifc-three
  // const { IFCLoader } = await import('three/examples/jsm/loaders/IFCLoader.js');
  // const loader = new IFCLoader();
  // const scene = await loader.loadAsync(url);
  // const guidMap = extractGUIDs(scene);
  // return { scene, guidMap };
  console.warn('model.js: IFC loading not yet implemented — using geometric placeholder');
  return { scene: null, guidMap: new Map() };
}

export function getMeshByGuid(guid) {
  // TODO: 从 guidMap 查找 Mesh
  return null;
}
