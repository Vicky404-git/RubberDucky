import { Suspense, useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import { cn } from "../../lib/cn";
import type { OrbState } from "../../lib/orb";
import { OrbScene } from "./OrbScene";

function webglAvailable(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext("webgl2") || canvas.getContext("webgl")),
    );
  } catch {
    return false;
  }
}

const FALLBACK_TONE: Record<OrbState, string> = {
  idle: "from-duck-300 via-amber-glow to-duck-600",
  listening: "from-duck-200 via-duck-400 to-amber-glow",
  processing: "from-duck-300 via-amber-glow to-orange-500",
  speaking: "from-duck-100 via-duck-300 to-amber-glow",
  error: "from-orange-300 via-danger to-red-600",
};

function FallbackOrb({ state }: { state: OrbState }) {
  return (
    <div className="relative flex h-full w-full items-center justify-center">
      <div
        className={cn(
          "relative h-[46%] w-[46%] animate-pulse-soft rounded-full bg-gradient-to-br shadow-glow",
          FALLBACK_TONE[state],
        )}
      >
        <span className="absolute inset-[12%] rounded-full border border-white/20" />
        <span className="absolute inset-[24%] rounded-full border border-white/10" />
      </div>
      <span className="absolute h-[62%] w-[62%] rounded-full border border-duck-300/25" />
      <span className="absolute h-[76%] w-[76%] rounded-full border border-duck-300/15" />
      <span className="absolute h-[90%] w-[90%] rounded-full border border-duck-300/10" />
    </div>
  );
}

interface OrbProps {
  state: OrbState;
  className?: string;
}

export function Orb({ state, className }: OrbProps) {
  const reducedMotion = useReducedMotion();
  const supported = useMemo(webglAvailable, []);

  return (
    <div className={cn("relative select-none", className)}>
      <div className="orb-aura" aria-hidden />
      <div className="orb-floor" aria-hidden />
      <div className="orb-canvas-wrap relative h-full w-full">
        {supported ? (
          <Canvas
            camera={{ position: [0, 0, 6.2], fov: 38 }}
            dpr={[1, 1.75]}
            gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
            style={{ background: "transparent" }}
          >
            <Suspense fallback={null}>
              <OrbScene state={state} reducedMotion={reducedMotion} />
            </Suspense>
          </Canvas>
        ) : (
          <FallbackOrb state={state} />
        )}
      </div>
      <span className="sr-only" role="status" aria-live="polite">
        Orb state: {state}
      </span>
    </div>
  );
}
