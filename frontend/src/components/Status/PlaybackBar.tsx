import { Play, RotateCcw, Square, Volume2, VolumeX } from "lucide-react";
import { usePlayback } from "../../hooks/usePlayback";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { ActivityMeter } from "./Indicators";

interface PlaybackBarProps {
  audio: { url: string; sessionId: string } | null;
}

export function PlaybackBar({ audio }: PlaybackBarProps) {
  const { playing, blocked, error, retry, stop } = usePlayback(audio);

  if (!audio) return null;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-duck-400/20 bg-duck-400/[0.055] px-4 py-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-duck-400/25 bg-ink-950/60 text-duck-300">
        {playing ? (
          <Volume2 className="h-4 w-4" aria-hidden />
        ) : (
          <VolumeX className="h-4 w-4" aria-hidden />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-xs font-medium text-duck-100">
            {blocked ? "Audio is ready" : error ? "Playback problem" : playing ? "Speaking response" : "Generated response"}
          </p>
          {playing ? <Badge tone="duck">Live amplitude</Badge> : null}
        </div>
        <p className="mt-0.5 truncate text-[11px] text-zinc-500">
          {blocked
            ? "Browser blocked autoplay. Enable audio to hear the diagnosis."
            : error
              ? error
              : "Analysed with the Web Audio API — the orb reacts to real speech amplitude."}
        </p>
      </div>

      <ActivityMeter mode={playing ? "speaking" : "idle"} className="hidden sm:flex" bars={7} />

      {blocked ? (
        <Button size="sm" variant="primary" onClick={retry}>
          <Play className="h-3.5 w-3.5" /> Enable audio
        </Button>
      ) : playing ? (
        <Button size="icon" variant="ghost" onClick={stop} aria-label="Stop playback">
          <Square className="h-3.5 w-3.5" />
        </Button>
      ) : (
        <Button size="sm" variant="secondary" onClick={retry} disabled={Boolean(error)}>
          <RotateCcw className="h-3.5 w-3.5" /> Replay
        </Button>
      )}
    </div>
  );
}
