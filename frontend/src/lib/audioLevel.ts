let level = 0;

export function setAudioLevel(next: number): void {
  level = Math.max(0, Math.min(1, next));
}

export function getAudioLevel(): number {
  return level;
}
