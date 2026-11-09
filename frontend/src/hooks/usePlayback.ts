import { useCallback, useEffect, useRef, useState } from "react";
import { setAudioLevel } from "../lib/audioLevel";
import { api } from "../services/api";
import { useAppStore } from "../stores/appStore";

interface AudioRequest {
  url: string;
  sessionId: string;
}

interface PlaybackState {
  playing: boolean;
  blocked: boolean;
  error: string | null;
  retry: () => void;
  stop: () => void;
}

export function usePlayback(audio: AudioRequest | null): PlaybackState {
  const finishPlayback = useAppStore((state) => state.finishPlayback);
  const [playing, setPlaying] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const elementRef = useRef<HTMLAudioElement | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const frameRef = useRef<number | null>(null);
  const dataRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const startedRef = useRef(false);
  const attemptRef = useRef<() => void>(() => undefined);

  const stopMeter = useCallback(() => {
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  const startMeter = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser || frameRef.current !== null) return;
    const data = new Float32Array(analyser.fftSize);
    dataRef.current = data;

    const loop = () => {
      const node = analyserRef.current;
      const buffer = dataRef.current;
      if (!node || !buffer) return;
      node.getFloatTimeDomainData(buffer);
      let sum = 0;
      for (let index = 0; index < buffer.length; index += 1) {
        const value = buffer[index] ?? 0;
        sum += value * value;
      }
      const rms = Math.sqrt(sum / buffer.length);
      setAudioLevel(Math.min(1, rms * 4.2));
      frameRef.current = requestAnimationFrame(loop);
    };
    frameRef.current = requestAnimationFrame(loop);
  }, []);

  useEffect(() => {
    setPlaying(false);
    setBlocked(false);
    setError(null);
    startedRef.current = false;

    if (!audio?.url) return;

    let cancelled = false;
    const element = new Audio(audio.url);
    element.preload = "auto";
    elementRef.current = element;

    const AudioContextClass =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

    let context: AudioContext | null = null;
    let analyser: AnalyserNode | null = null;
    try {
      if (!AudioContextClass) throw new Error("Web Audio is unavailable in this browser.");
      context = new AudioContextClass();
      analyser = context.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.82;
      const source = context.createMediaElementSource(element);
      source.connect(analyser);
      analyser.connect(context.destination);
      contextRef.current = context;
      analyserRef.current = analyser;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not initialise audio.");
    }

    const report = (phase: "started" | "completed") => {
      void api.playback(audio.sessionId, phase).catch(() => undefined);
    };

    const handlePlay = () => {
      if (cancelled) return;
      setPlaying(true);
      setBlocked(false);
      if (!startedRef.current) {
        startedRef.current = true;
        report("started");
      }
      startMeter();
    };

    const handleEnded = () => {
      if (cancelled) return;
      stopMeter();
      setPlaying(false);
      if (startedRef.current) {
        report("completed");
      }
      finishPlayback();
    };

    const handleError = () => {
      if (cancelled) return;
      setError("The generated audio could not be played.");
      setPlaying(false);
      stopMeter();
    };

    element.addEventListener("play", handlePlay);
    element.addEventListener("ended", handleEnded);
    element.addEventListener("error", handleError);

    const attempt = () => {
      setError(null);
      const run = async () => {
        try {
          if (contextRef.current?.state === "suspended") {
            await contextRef.current.resume();
          }
          await element.play();
        } catch (reason) {
          if (cancelled) return;
          if (reason instanceof DOMException && reason.name === "NotAllowedError") {
            setBlocked(true);
          } else {
            setError("The generated audio could not be played.");
          }
        }
      };
      void run();
    };
    attemptRef.current = attempt;
    attempt();

    return () => {
      cancelled = true;
      element.removeEventListener("play", handlePlay);
      element.removeEventListener("ended", handleEnded);
      element.removeEventListener("error", handleError);
      element.pause();
      element.removeAttribute("src");
      try {
        element.load();
      } catch {
        // Ignore teardown races.
      }
      stopMeter();
      if (startedRef.current) report("completed");
      void contextRef.current?.close().catch(() => undefined);
      contextRef.current = null;
      analyserRef.current = null;
      elementRef.current = null;
    };
  }, [audio?.url, audio?.sessionId, finishPlayback, startMeter, stopMeter]);

  const retry = useCallback(() => {
    setBlocked(false);
    attemptRef.current();
  }, []);

  const stop = useCallback(() => {
    const element = elementRef.current;
    if (element) {
      element.pause();
      element.currentTime = 0;
    }
    stopMeter();
    setPlaying(false);
    if (audio?.sessionId) {
      void api.playback(audio.sessionId, "completed").catch(() => undefined);
    }
    finishPlayback();
  }, [audio?.sessionId, finishPlayback, stopMeter]);

  return { playing, blocked, error, retry, stop };
}
