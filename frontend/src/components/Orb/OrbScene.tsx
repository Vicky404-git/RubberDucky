import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { getAudioLevel } from "../../lib/audioLevel";
import type { OrbState } from "../../lib/orb";

interface OrbSceneProps {
  state: OrbState;
  reducedMotion: boolean;
}

const VERTEX_SHADER = /* glsl */ `
  uniform float uTime;
  uniform float uAmplitude;
  varying vec3 vNormal;
  varying vec3 vView;
  varying float vPulse;

  void main() {
    vec3 displaced = position;
    float wave = sin(position.y * 7.0 + uTime * 1.1) * 0.012
               + sin(position.x * 6.0 - uTime * 0.8) * 0.010
               + sin(position.z * 9.0 + uTime * 1.6) * 0.008;
    float voice = uAmplitude * 0.09 * sin(position.y * 14.0 + uTime * 9.0);
    displaced += normal * (wave + voice);
    vPulse = wave + voice;

    vec4 mvPosition = modelViewMatrix * vec4(displaced, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mvPosition.xyz);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  uniform float uTime;
  uniform float uAmplitude;
  uniform float uDanger;
  varying vec3 vNormal;
  varying vec3 vView;
  varying float vPulse;

  void main() {
    float fresnel = pow(1.0 - clamp(dot(normalize(vNormal), normalize(vView)), 0.0, 1.0), 2.1);
    float bands = 0.5 + 0.5 * sin(vNormal.y * 6.0 + vNormal.x * 2.2 + uTime * 0.9);
    vec3 base = mix(uColorA, uColorB, clamp(bands * 0.5 + vPulse * 9.0, 0.0, 1.0));
    vec3 hot = mix(uColorB, vec3(1.0, 0.9, 0.62), 0.48);
    vec3 color = mix(base, hot, fresnel * 0.72);
    if (uDanger > 0.5) {
      color = mix(color, vec3(1.0, 0.36, 0.27), 0.34 + fresnel * 0.32);
    }
    float glow = 0.74 + fresnel * 0.9 + uAmplitude * 0.55;
    gl_FragColor = vec4(color * glow, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

function seeded(seed: number): number {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

function shellPositions(count: number, minRadius: number, maxRadius: number, seed = 1): Float32Array {
  const positions = new Float32Array(count * 3);
  for (let index = 0; index < count; index += 1) {
    const theta = seeded(index * 3.1 + seed) * Math.PI * 2;
    const phi = Math.acos(2 * seeded(index * 7.7 + seed + 11) - 1);
    const radius = minRadius + seeded(index * 5.3 + seed + 7) * (maxRadius - minRadius);
    positions[index * 3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[index * 3 + 1] = radius * Math.cos(phi) * 0.82;
    positions[index * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
  }
  return positions;
}

function damp(current: number, target: number, lambda: number, delta: number): number {
  return THREE.MathUtils.lerp(current, target, 1 - Math.exp(-lambda * delta));
}

export function OrbScene({ state, reducedMotion }: OrbSceneProps) {
  const groupRef = useRef<THREE.Group>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const ringRefs = useRef<Array<THREE.Mesh | null>>([]);
  const particleRef = useRef<THREE.Points>(null);
  const dustRef = useRef<THREE.Points>(null);

  const particlePositions = useMemo(() => shellPositions(620, 1.85, 3.25, 3), []);
  const dustPositions = useMemo(() => shellPositions(220, 1.6, 2.4, 17), []);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uAmplitude: { value: 0 },
      uDanger: { value: 0 },
      uColorA: { value: new THREE.Color("#ffcb05") },
      uColorB: { value: new THREE.Color("#ff8a1c") },
    }),
    [],
  );

  const palette = useMemo(() => {
    if (state === "error") {
      return {
        a: new THREE.Color("#ff8a5c"),
        b: new THREE.Color("#ff4d3d"),
        danger: 1,
      };
    }
    if (state === "processing") {
      return {
        a: new THREE.Color("#ffd84d"),
        b: new THREE.Color("#ff9f1c"),
        danger: 0,
      };
    }
    if (state === "speaking") {
      return {
        a: new THREE.Color("#ffe97a"),
        b: new THREE.Color("#ffab1c"),
        danger: 0,
      };
    }
    return {
      a: new THREE.Color("#ffcb05"),
      b: new THREE.Color("#f08c16"),
      danger: 0,
    };
  }, [state]);

  useFrame(({ clock, pointer }, delta) => {
    const time = clock.getElapsedTime();
    const motion = reducedMotion ? 0.25 : 1;
    const material = materialRef.current;
    const core = coreRef.current;
    const group = groupRef.current;

    if (material) {
      material.uniforms.uTime!.value = time * motion;
      const amplitude = state === "speaking" ? getAudioLevel() : 0;
      material.uniforms.uAmplitude!.value = damp(
        Number(material.uniforms.uAmplitude!.value),
        amplitude,
        7,
        delta,
      );
      material.uniforms.uDanger!.value = damp(
        Number(material.uniforms.uDanger!.value),
        palette.danger,
        5,
        delta,
      );
      (material.uniforms.uColorA!.value as THREE.Color).lerp(
        palette.a,
        1 - Math.exp(-delta * 4),
      );
      (material.uniforms.uColorB!.value as THREE.Color).lerp(
        palette.b,
        1 - Math.exp(-delta * 4),
      );
    }

    if (core) {
      let breathe = 1;
      if (state === "idle") breathe = 1 + Math.sin(time * 0.8) * 0.024;
      if (state === "listening") breathe = 1 + Math.sin(time * 2.3) * 0.05;
      if (state === "processing") breathe = 1 + Math.sin(time * 1.7) * 0.028;
      if (state === "speaking") breathe = 1 + getAudioLevel() * 0.22;
      if (state === "error") breathe = 1 + Math.sin(time * 7) * 0.012;
      const target = reducedMotion ? 1 : breathe;
      core.scale.setScalar(damp(core.scale.x, target, 8, delta));
      core.rotation.z += delta * (reducedMotion ? 0.01 : 0.045);
    }

    if (group) {
      const speed =
        state === "processing" ? 0.42 : state === "listening" ? 0.1 : state === "speaking" ? 0.18 : 0.05;
      group.rotation.y += delta * speed * motion;
      const targetX = reducedMotion ? 0 : pointer.y * 0.09;
      const targetY = reducedMotion ? 0 : pointer.x * 0.12;
      group.rotation.x = damp(group.rotation.x, targetX, 2.5, delta);
      group.rotation.z = damp(group.rotation.z, targetY * 0.35, 2.5, delta);
    }

    ringRefs.current.forEach((ring, index) => {
      if (!ring) return;
      const direction = index % 2 === 0 ? 1 : -1;
      const baseSpeed =
        state === "processing" ? 0.5 + index * 0.24 : state === "listening" ? 0.12 : 0.06;
      ring.rotation.z += delta * baseSpeed * direction * motion;
      ring.rotation.x += delta * 0.045 * direction * motion;
      const ripple =
        state === "listening" || state === "speaking"
          ? 1 + Math.sin(time * 2.1 - index * 0.9) * 0.035 * motion
          : 1;
      ring.scale.setScalar(damp(ring.scale.x, ripple, 5, delta));
    });

    if (particleRef.current) {
      particleRef.current.rotation.y += delta * (state === "processing" ? 0.26 : 0.07) * motion;
      particleRef.current.rotation.x += delta * 0.02 * motion;
    }
    if (dustRef.current) {
      dustRef.current.rotation.y -= delta * (state === "processing" ? 0.16 : 0.045) * motion;
    }
  });

  const ringColor = state === "error" ? "#ff7a5c" : "#ffd15c";

  return (
    <group ref={groupRef}>
      <mesh ref={coreRef}>
        <sphereGeometry args={[1.34, 128, 128]} />
        <shaderMaterial
          ref={materialRef}
          uniforms={uniforms}
          vertexShader={VERTEX_SHADER}
          fragmentShader={FRAGMENT_SHADER}
        />
      </mesh>

      <mesh scale={1.32}>
        <sphereGeometry args={[1.34, 64, 64]} />
        <meshBasicMaterial
          color={ringColor}
          transparent
          opacity={0.055}
          blending={THREE.AdditiveBlending}
          side={THREE.BackSide}
          depthWrite={false}
        />
      </mesh>

      {[1.92, 2.24, 2.58].map((radius, index) => (
        <mesh
          key={radius}
          ref={(element) => {
            ringRefs.current[index] = element;
          }}
          rotation={[Math.PI / 2.6 + index * 0.35, index * 0.5, index * 0.7]}
        >
          <torusGeometry args={[radius, index === 1 ? 0.0065 : 0.004, 10, 220]} />
          <meshBasicMaterial
            color={ringColor}
            transparent
            opacity={index === 1 ? 0.34 : 0.2}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}

      <points ref={particleRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[particlePositions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          color={ringColor}
          size={0.018}
          sizeAttenuation
          transparent
          opacity={0.68}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>

      <points ref={dustRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[dustPositions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          color="#fff0bd"
          size={0.028}
          sizeAttenuation
          transparent
          opacity={0.36}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
    </group>
  );
}
