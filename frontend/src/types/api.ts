export type SessionStatus =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "completed"
  | "failed";

export interface TimelineEntry {
  type: string;
  message: string;
  timestamp: number;
}

export interface SessionRecord {
  id: string;
  started_at: number;
  updated_at: number;
  status: SessionStatus;
  stage: string;
  transcript: string | null;
  category: string | null;
  category_source: string | null;
  requires_logs: boolean;
  log_probability: number;
  git_branch: string | null;
  git_summary: string | null;
  diagnosis: string | null;
  spoken_response: string | null;
  error: string | null;
  retryable: boolean;
  audio_url: string | null;
  duration_ms: number | null;
  timeline: TimelineEntry[];
}

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  project_root: string;
  config_path: string;
  has_openrouter_key: boolean;
  has_gnani_key: boolean;
  git_available: boolean;
  arecord_available: boolean;
  aplay_available: boolean;
}

export interface StatusResponse {
  state: SessionStatus;
  active: boolean;
  daemon_running: boolean;
  project_name: string;
  project_root: string;
  branch: string;
  hotkey: { key: string; modifiers: string };
  credentials: { openrouter: boolean; gnani: boolean };
  latest_session: SessionRecord | null;
  last_diagnosis: string | null;
  session_count: number;
}

export interface SafeConfig {
  llm: {
    provider: string;
    model: string;
    temperature: number;
    max_tokens: number;
    timeout: number;
  };
  voice: { record_seconds: number; language: string };
  git: { max_commits: number; max_chars: number; timeout: number };
  triage: { device: string; lazy_load: boolean };
  hotkey: { key: string; modifiers: string };
  logging: { level: string; max_bytes: number; backup_count: number };
  ignore: {
    gitignore_path: string;
    rubberduckyignore_path: string;
    gitignore_exists: boolean;
    rubberduckyignore_exists: boolean;
    builtin_sensitive_patterns: string[];
  };
  paths: {
    project_root: string;
    config_path: string;
    env_file_present: boolean;
    state_dir: string;
    frontend_dist: string;
  };
}

export interface ConfigUpdate {
  llm_provider?: string;
  llm_model?: string;
  llm_temperature?: number;
  llm_max_tokens?: number;
  llm_timeout?: number;
  voice_language?: string;
  record_seconds?: number;
  git_max_commits?: number;
  git_max_chars?: number;
  logging_level?: string;
  hotkey_key?: string;
  hotkey_modifiers?: string;
  triage_device?: string;
  triage_lazy_load?: boolean;
}

export interface GitCommit {
  hash: string;
  date: string;
  subject: string;
}

export interface GitContext {
  branch: string;
  clean: boolean;
  status_lines: string[];
  conflicts: string[];
  has_conflicts: boolean;
  staged_diff: string;
  unstaged_diff: string;
  commits: GitCommit[];
  ignored_paths: string[];
}

export interface GitDiffResponse {
  kind: "staged" | "unstaged";
  diff: string;
  empty: boolean;
  length: number;
  redacted: boolean;
}

export interface IgnoreFileInfo {
  path: string;
  exists: boolean;
  rules: string[];
}

export interface IgnoreRules {
  gitignore: IgnoreFileInfo;
  rubberduckyignore: IgnoreFileInfo;
  builtin_sensitive_patterns: string[];
  suggestions: string[];
  preview: string;
  sensitive_findings: string[];
  candidate_count: number;
}

export interface ApplyIgnoreResponse extends IgnoreRules {
  applied: string[];
  destination: "rubberducky" | "git";
}

export interface LogEntry {
  level: string;
  line: string;
  message: string;
}

export interface LogsResponse {
  path: string;
  entries: LogEntry[];
  exists: boolean;
}

export interface SessionsResponse {
  sessions: SessionRecord[];
  count: number;
}

export interface BridgeEvent {
  type: string;
  timestamp: number;
  session_id?: string;
  status?: SessionStatus;
  stage?: string;
  message?: string;
  audio_url?: string;
  transcript?: string;
  diagnosis?: string;
  spoken_response?: string;
  category?: string;
  category_source?: string;
  log_probability?: number;
  branch?: string;
  summary?: string;
  code?: string;
  retryable?: boolean;
  changed?: string[];
  patterns?: string[];
  destination?: string;
  duration_seconds?: number;
  [key: string]: unknown;
}

export interface SnapshotEvent extends Omit<BridgeEvent, "type" | "status"> {
  type: "snapshot";
  status: StatusResponse;
  events: BridgeEvent[];
}

export type PlaybackPhase = "started" | "completed";
