"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { FieldAtlasFallback } from "./FieldAtlasFallback";

const PLOTS: Array<[number, number, number, number, string]> = [
  [-2.4, -1.5, 2.2, 1.35, "#315c2b"],
  [0.2, -1.7, 2.35, 1.2, "#689454"],
  [2.55, -1.42, 1.7, 1.45, "#3f6f35"],
  [-2.55, 0.05, 1.85, 1.35, "#96bb84"],
  [-0.25, -0.05, 2.15, 1.5, "#c2d8b6"],
  [2.25, 0.18, 1.95, 1.5, "#689454"],
  [-2.15, 1.62, 2.5, 1.28, "#3f6f35"],
  [0.62, 1.62, 2.3, 1.3, "#96bb84"],
  [2.78, 1.72, 1.45, 1.18, "#315c2b"],
];

function FieldLandscape() {
  const root = useRef<THREE.Group>(null);
  const { pointer } = useThree();

  useFrame((state, delta) => {
    if (!root.current) return;
    root.current.rotation.y = THREE.MathUtils.damp(root.current.rotation.y, pointer.x * 0.1, 4, delta);
    root.current.rotation.x = THREE.MathUtils.damp(root.current.rotation.x, -pointer.y * 0.045, 4, delta);
    root.current.position.y = Math.sin(state.clock.elapsedTime * 0.34) * 0.025;
  });

  const stalks = useMemo(
    () =>
      Array.from({ length: 54 }, (_, index) => ({
        x: -3.15 + ((index * 1.37) % 6.2),
        z: -2.25 + ((index * 1.91) % 4.45),
        scale: 0.78 + ((index * 7) % 9) / 20,
      })),
    [],
  );

  return (
    <group ref={root} rotation={[-0.1, -0.18, 0]} position={[0, -0.25, 0]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.16, 0]}>
        <planeGeometry args={[8, 6.5]} />
        <meshStandardMaterial color="#e7e8cb" roughness={1} />
      </mesh>

      {PLOTS.map(([x, z, width, depth, color], index) => (
        <mesh
          key={`${x}-${z}`}
          rotation={[-Math.PI / 2, 0, index % 2 ? 0.025 : -0.02]}
          position={[x, 0, z]}
        >
          <boxGeometry args={[width, depth, 0.12]} />
          <meshStandardMaterial color={color} roughness={0.92} />
        </mesh>
      ))}

      <mesh rotation={[-Math.PI / 2, 0, 0.28]} position={[0.25, 0.16, -0.05]}>
        <torusGeometry args={[3.15, 0.34, 12, 80, 2.15]} />
        <meshStandardMaterial color="#7fb6bf" roughness={0.55} metalness={0.04} />
      </mesh>

      <group>
        {stalks.map((stalk, index) => (
          <group
            key={index}
            position={[stalk.x, 0.1, stalk.z]}
            scale={stalk.scale}
            rotation={[0, (index % 8) * 0.3, index % 2 ? 0.06 : -0.05]}
          >
            <mesh position={[0, 0.25, 0]}>
              <cylinderGeometry args={[0.012, 0.018, 0.52, 5]} />
              <meshStandardMaterial color="#254a24" />
            </mesh>
            <mesh position={[0.035, 0.5, 0]} rotation={[0, 0, -0.4]}>
              <sphereGeometry args={[0.055, 6, 5]} />
              <meshStandardMaterial color="#d9c28f" />
            </mesh>
          </group>
        ))}
      </group>

      <mesh position={[2.25, 2.25, -2.3]}>
        <sphereGeometry args={[0.48, 24, 24]} />
        <meshStandardMaterial color="#d9c28f" emissive="#ab8b50" emissiveIntensity={0.12} />
      </mesh>
    </group>
  );
}

export default function FieldAtlasScene() {
  const [reduced, setReduced] = useState(true);

  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  if (reduced) return <FieldAtlasFallback />;

  return (
    <div className="relative h-full min-h-[420px]" aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        orthographic
        camera={{ position: [5, 6.5, 7], zoom: 72 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      >
        <color attach="background" args={["#edf2df"]} />
        <ambientLight intensity={1.65} />
        <directionalLight position={[4, 8, 6]} intensity={2.1} color="#fff7da" />
        <FieldLandscape />
      </Canvas>
      <div className="pointer-events-none absolute inset-x-5 bottom-5 flex items-center justify-between rounded-full border border-paper-50/70 bg-paper-50/80 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-field-800 backdrop-blur">
        <span>Delta field study</span>
        <span>Move to survey</span>
      </div>
    </div>
  );
}

