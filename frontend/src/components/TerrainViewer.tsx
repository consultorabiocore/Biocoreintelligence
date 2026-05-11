/**
 * TerrainViewer — R3F component for rendering terrain mesh.
 *
 * Renders the DTM grid as a colored mesh with elevation gradient.
 * Supports click-to-place radar via raycasting.
 * Uses OrbitControls for camera manipulation.
 */import { useRef, useMemo, useEffect } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, GizmoHelper, GizmoViewport } from "@react-three/drei";
import * as THREE from "three";
import { getTerrainExtent, getMinElevation } from "../utils/terrain";
import { useTerrainStore } from "../store/terrainStore";
import { useAnalysisStore } from "../store/analysisStore";
import { ShadowOverlay } from "./ShadowOverlay";

/** Lógica de color biológico para BioCore Intelligence */
const getBioColor = (saviValue: number) => {
  if (saviValue > 0.5) return new THREE.Color("#2d6a4f"); // Verde (Saludable)
  if (saviValue > 0.2) return new THREE.Color("#95d5b2"); // Verde claro (Normal)
  return new THREE.Color("#bc4749");                     // Rojo (Alerta de estrés)
};

interface TerrainMeshProps {
  grid: number[][];
  resolution: number;
  showShadowOverlay: boolean;
  onTerrainClick?: (point: { x: number; y: number; z: number }) => void;
}

function TerrainMesh({
  grid,
  resolution,
  showShadowOverlay,
  onTerrainClick,
}: TerrainMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const minElev = useMemo(() => getMinElevation(grid), [grid]);

  const geometry = useMemo(() => {
    const rows = grid.length;
    const cols = grid[0]?.length ?? 0;
    const vertexCount = rows * cols;

    const pos = new Float32Array(vertexCount * 3);
    const colors = new Float32Array(vertexCount * 3); // Capa de color biológico
    
    let pIdx = 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = grid[r]![c]!;
        
        // 1. Posición
        pos[pIdx] = c * resolution;
        pos[pIdx + 1] = (isNaN(val) ? 0 : val) - minElev;
        pos[pIdx + 2] = -(r * resolution);

        // 2. Color (Prototipo de BioCore)
        // Simulamos una zona de alerta en una sección del mapa
        const isStressZone = r > rows/3 && r < rows/2 && c > cols/3 && c < cols/2;
        const simulatedSavi = isStressZone ? 0.1 : 0.6; 
        const color = getBioColor(simulatedSavi);

        colors[pIdx] = color.r;
        colors[pIdx + 1] = color.g;
        colors[pIdx + 2] = color.b;

        pIdx += 3;
      }
    }

    const ind: number[] = [];
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const valTL = grid[r]![c]!;
        const valTR = grid[r]![c + 1]!;
        const valBL = grid[r + 1]![c]!;
        const valBR = grid[r + 1]![c + 1]!;

        if (isNaN(valTL) || isNaN(valTR) || isNaN(valBL) || isNaN(valBR)) continue;

        const tl = r * cols + c;
        const tr = tl + 1;
        const bl = tl + cols;
        const br = bl + 1;
        ind.push(tl, tr, bl, tr, br, bl);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3)); // Inyectamos colores
    geo.setIndex(new THREE.BufferAttribute(new Uint32Array(ind), 1));
    geo.computeVertexNormals();
    return geo;
  }, [grid, resolution, minElev]);

  return (
    <group>
      <mesh
        ref={meshRef}
        geometry={geometry}
        onClick={(e) => {
          e.stopPropagation();
          if (onTerrainClick) onTerrainClick(e.point);
        }}
      >
        {/* Cambiamos el color gris por vertexColors */}
        <meshStandardMaterial vertexColors={true} side={THREE.DoubleSide} />
      </mesh>
      {showShadowOverlay && <ShadowOverlay grid={grid} resolution={resolution} />}
    </group>
  );
}

function RadarMarkers() {
  const radarPosition = useAnalysisStore((s) => s.radarPosition);
  const deployedRadars = useAnalysisStore((s) => s.deployedRadars);
  const metadata = useTerrainStore((s) => s.metadata);

  if (!metadata) return null;
  const bounds = metadata.bounds;

  const toLocal = (pos: { x: number; y: number; z: number }) => ({
    lx: pos.x - bounds.min_x,
    ly: pos.z - bounds.min_z,
    lz: bounds.min_y - pos.y,
  });

  return (
    <>
      {radarPosition && (() => {
        const { lx, ly, lz } = toLocal(radarPosition);
        return (
          <mesh position={[lx, ly, lz]}>
            <sphereGeometry args={[3, 16, 16]} />
            <meshStandardMaterial color="white" emissive="white" emissiveIntensity={0.5} />
          </mesh>
        );
      })()}
      {deployedRadars.map((dr) => {
        const { lx, ly, lz } = toLocal(dr.position);
        return (
          <group key={dr.id} position={[lx, ly, lz]}>
            <mesh>
              <sphereGeometry args={[4, 16, 16]} />
              <meshStandardMaterial color={dr.color} emissive={dr.color} emissiveIntensity={0.4} />
            </mesh>
            <mesh position={[0, 6, 0]}>
              <cylinderGeometry args={[0.5, 0.5, 12, 8]} />
              <meshStandardMaterial color={dr.color} />
            </mesh>
          </group>
        );
      })}
    </>
  );
}

function Scene({ grid, resolution, showShadowOverlay, onTerrainClick }: TerrainMeshProps) {
  const { camera } = useThree();
  const controlsRef = useRef<any>(null);
 
  useEffect(() => {
    if (!grid || grid.length === 0 || !grid[0]) return;
    const extent = getTerrainExtent(grid, resolution);
    const maxDim = Math.max(extent.width, extent.depth);
    if (isNaN(maxDim) || maxDim <= 0) return;

    const targetX = extent.centerX;
    const targetY = extent.height / 2;
    const targetZ = extent.centerZ;

    camera.position.set(targetX + maxDim * 1.2, maxDim * 1.0, targetZ + maxDim * 1.2);
    if (controlsRef.current) {
      controlsRef.current.target.set(targetX, targetY, targetZ);
      controlsRef.current.update();
    }
    camera.lookAt(targetX, targetY, targetZ);
    camera.updateProjectionMatrix();
  }, [grid, resolution]);

  return (
    <>
      <color attach="background" args={["#111111"]} />
      <ambientLight intensity={0.25} />
      <directionalLight position={[1, 0.6, 0.5]} intensity={1.2} />
      <directionalLight position={[-1, 0.4, -0.5]} intensity={0.4} />
      <gridHelper args={[10000, 100, "#333", "#222"]} position={[0, -1, 0]} />
      <TerrainMesh grid={grid} resolution={resolution} showShadowOverlay={showShadowOverlay} onTerrainClick={onTerrainClick} />
      <RadarMarkers />
      <OrbitControls ref={controlsRef} makeDefault />
      <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
        <GizmoViewport axisColors={['#ff3653', '#0adb21', '#2c8fdf']} labelColor="white" labels={['E', 'Y', 'N']} />
      </GizmoHelper>
    </>
  );
}

export function TerrainViewer({ showShadowOverlay = false, onTerrainClick }: TerrainViewerProps) {
  const grid = useTerrainStore((s) => s.grid);
  const resolution = useTerrainStore((s) => s.metadata?.resolution ?? 2.0);

  if (!grid || grid.length === 0) {
    return (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#1a1a2e", color: "#aaa" }}>
        <p>No terrain loaded. Generate synthetic terrain or upload a DXF file.</p>
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <Canvas camera={{ fov: 50, near: 0.1, far: 500000 }} gl={{ preserveDrawingBuffer: true }}>
        <Scene grid={grid} resolution={resolution} showShadowOverlay={showShadowOverlay} onTerrainClick={onTerrainClick} />
      </Canvas>
    </div>
  );
}

