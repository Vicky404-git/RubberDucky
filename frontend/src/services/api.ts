import type {
  ApplyIgnoreResponse,
  ConfigUpdate,
  GitContext,
  GitDiffResponse,
  HealthResponse,
  IgnoreRules,
  LogsResponse,
  PlaybackPhase,
  SafeConfig,
  SessionRecord,
  SessionsResponse,
  StatusResponse,
} from "../types/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("Cannot reach the local RubberDucky bridge. Is it running?", 0);
  }

  if (!response.ok) {
    let detail = `Request failed (HTTP ${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail) && body.detail.length > 0) {
        const first = body.detail[0] as { msg?: unknown };
        if (typeof first?.msg === "string") detail = first.msg;
      }
    } catch {
      // Keep the generic message.
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  status: () => request<StatusResponse>("/api/status"),
  config: () => request<SafeConfig>("/api/config"),
  updateConfig: (update: ConfigUpdate) =>
    request<SafeConfig>("/api/config", { method: "PUT", body: JSON.stringify(update) }),
  sessions: (limit = 50) => request<SessionsResponse>(`/api/sessions?limit=${limit}`),
  session: (id: string) => request<SessionRecord>(`/api/sessions/${encodeURIComponent(id)}`),
  startSession: (dockerContainer?: string | null) =>
    request<SessionRecord>("/api/sessions/start", {
      method: "POST",
      body: JSON.stringify({ docker_container: dockerContainer ?? null }),
    }),
  retrySession: (id: string, dockerContainer?: string | null) =>
    request<SessionRecord>(`/api/sessions/${encodeURIComponent(id)}/retry`, {
      method: "POST",
      body: JSON.stringify({ docker_container: dockerContainer ?? null }),
    }),
  playback: (id: string, phase: PlaybackPhase) =>
    request<SessionRecord>(`/api/sessions/${encodeURIComponent(id)}/playback`, {
      method: "POST",
      body: JSON.stringify({ phase }),
    }),
  deleteAudio: (id: string) =>
    request<{ deleted: boolean }>(`/api/sessions/${encodeURIComponent(id)}/audio/delete`, {
      method: "POST",
    }),
  gitContext: () => request<GitContext>("/api/git/context"),
  gitDiff: (kind: "staged" | "unstaged") =>
    request<GitDiffResponse>(`/api/git/diff?kind=${kind}`),
  ignoreRules: () => request<IgnoreRules>("/api/ignore/rules"),
  applyIgnore: (patterns: string[], destination: "rubberducky" | "git") =>
    request<ApplyIgnoreResponse>("/api/ignore/apply", {
      method: "POST",
      body: JSON.stringify({ patterns, destination, approved: true }),
    }),
  logs: (limit = 200) => request<LogsResponse>(`/api/logs?limit=${limit}`),
};
