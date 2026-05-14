import { createElement } from '../engine/renderer';
import { placeElement } from '../engine/placement';
import { board, type BoardCommand } from '../engine/state';

export async function renderScene3dCommand(cmd: BoardCommand): Promise<void> {
  const code = (cmd as { code?: string }).code;
  if (!code) return;

  const el = createElement('div', cmd, 'bd-scene3d');
  el.style.minHeight = '320px';
  placeElement(el, cmd.placement ?? 'below', cmd);

  const THREE = await import('three');
  const orbitMod = await import('three/examples/jsm/controls/OrbitControls.js');

  const rect = el.getBoundingClientRect();
  const w = Math.max(rect.width || 480, 240);
  const h = Math.max(rect.height || 320, 200);

  const scene = new THREE.Scene();
  scene.background = null;
  const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 1000);
  camera.position.set(3, 3, 5);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(w, h);
  el.appendChild(renderer.domElement);
  const controls = new orbitMod.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  const ambient = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(ambient);
  const point = new THREE.PointLight(0xffffff, 1, 100);
  point.position.set(5, 5, 5);
  scene.add(point);

  type Scene3dInit = (
    THREE: typeof import('three'),
    scene: import('three').Scene,
    camera: import('three').PerspectiveCamera,
  ) => void;
  try {
    // eslint-disable-next-line @typescript-eslint/no-implied-eval, no-new-func
    const userInit = new Function('THREE', 'scene', 'camera', code) as Scene3dInit;
    userInit(THREE, scene, camera);
  } catch (err) {
    el.innerHTML += `<pre class="text-bad text-xs">3D error: ${(err as Error).message}</pre>`;
  }

  let raf = 0;
  const tick = () => {
    controls.update();
    renderer.render(scene, camera);
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);

  board.animations.push({
    container: el,
    instance: {
      remove: () => {
        cancelAnimationFrame(raf);
        renderer.dispose();
        if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
      },
      loop: () => {
        if (!raf) raf = requestAnimationFrame(tick);
      },
      noLoop: () => {
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
      },
    },
  });
}
