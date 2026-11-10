import { create } from "zustand";
import { ApiError, api } from "../services/api";
import {
  createEventStream,
  type ConnectionState,
} from "../services/events";
import {
  orbStateFromBackend,
  orbStateFromEvent,
  type OrbState,
} from "../lib/orb";
import type {
  BridgeEvent,
  ConfigUpdate,
  GitContext,
  HealthResponse,
  IgnoreRules,
  LogEntry,
  ProviderInfo,
  SafeConfig,
  SessionRecord,
  StatusResponse,
} from "../types/api";

interface LoadingFlags {
  bootstrap: boolean;
  status: boolean;
  sessions: boolean;
  git: boolean;
  ignore: boolean;
  config: boolean;
  providers: boolean;
  logs: boolean;
  action: boolean;
}

interface ErrorFlags {
  bootstrap?: string;
  git?: string;
  ignore?: string;
  config?: string;
  providers?: string;
  logs?: string;
  session?: string;
}

interface Notice {
  kind: "success" | "error" | "info";
  message: string;
}

interface AudioRequest {
  url: string;
  sessionId: string;
}

interface AppStore {
  connection: ConnectionState;
  health: HealthResponse | null;
  status: StatusResponse | null;
  config: SafeConfig | null;
  providers: ProviderInfo[];
  selectedLlm: string;
  sessions: SessionRecord[];
  latest: SessionRecord | null;
  git: GitContext | null;
  ignore: IgnoreRules | null;
  logs: LogEntry[];
  logPath: string | null;
  logsExist: boolean;
  events: BridgeEvent[];
  orbState: OrbState;
  stage: string;
  errorMessage: string | null;
  audio: AudioRequest | null;
  loading: LoadingFlags;
  errors: ErrorFlags;
  notice: Notice | null;
  bootstrap: () => Promise<void>;
  connectEvents: () => void;
  disconnectEvents: () => void;
  handleStatus: (status: StatusResponse) => void;
  handleEvent: (event: BridgeEvent) => void;
  refreshStatus: () => Promise<void>;
  refreshSessions: () => Promise<void>;
  refreshConfig: () => Promise<void>;
  refreshProviders: () => Promise<void>;
  refreshGit: () => Promise<void>;
  refreshIgnore: () => Promise<void>;
  refreshLogs: () => Promise<void>;
  startSession: () => Promise<SessionRecord | null>;
  retrySession: (sessionId: string) => Promise<SessionRecord | null>;
  saveConfig: (update: ConfigUpdate) => Promise<boolean>;
  /** The API key is used only for the request; it is never persisted here. */
  saveProviderKey: (provider: string, apiKey: string) => Promise<boolean>;
  removeProviderKey: (provider: string) => Promise<boolean>;
  selectLlmProvider: (provider: string) => Promise<boolean>;
  saveProviderModel: (provider: string, model: string) => Promise<boolean>;
  applyIgnore: (patterns: string[], destination: "rubberducky" | "git") => Promise<boolean>;
  deleteAudio: (sessionId: string) => Promise<void>;
  setAudio: (audio: AudioRequest | null) => void;
  finishPlayback: () => void;
  setNotice: (notice: Notice | null) => void;
  clearNotice: () => void;
}

let stopStream: (() => void) | null = null;
let refreshTimer: number | null = null;
let bootstrapped = false;

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function patchSession(session: SessionRecord, event: BridgeEvent): SessionRecord {
  return {
    ...session,
    status: event.status ?? session.status,
    stage: event.stage ?? session.stage,
    transcript: event.transcript ?? session.transcript,
    diagnosis: event.diagnosis ?? session.diagnosis,
    spoken_response: event.spoken_response ?? session.spoken_response,
    category: event.category ?? session.category,
    category_source: event.category_source ?? session.category_source,
    log_probability: event.log_probability ?? session.log_probability,
    git_branch: event.branch ?? session.git_branch,
    git_summary: event.summary ?? session.git_summary,
    audio_url: event.audio_url ?? session.audio_url,
    error: event.type === "session_failed" ? (event.message ?? session.error) : session.error,
    updated_at: event.timestamp,
  };
}

function stateForSession(session: SessionRecord | null): OrbState {
  return session ? orbStateFromBackend(session.status) : "idle";
}

export const useAppStore = create<AppStore>()((set, get) => {
  const scheduleRefresh = () => {
    if (refreshTimer !== null) return;
    refreshTimer = window.setTimeout(() => {
      refreshTimer = null;
      void get().refreshStatus();
      void get().refreshSessions();
    }, 350);
  };

  return {
    connection: "connecting",
    health: null,
    status: null,
    config: null,
    providers: [],
    selectedLlm: "openrouter",
    sessions: [],
    latest: null,
    git: null,
    ignore: null,
    logs: [],
    logPath: null,
    logsExist: false,
    events: [],
    orbState: "idle",
    stage: "idle",
    errorMessage: null,
    audio: null,
    loading: {
      bootstrap: true,
      status: false,
      sessions: false,
      git: false,
      ignore: false,
      config: false,
      providers: false,
      logs: false,
      action: false,
    },
    errors: {},
    notice: null,

    bootstrap: async () => {
      if (bootstrapped) return;
      bootstrapped = true;
      set((state) => ({ loading: { ...state.loading, bootstrap: true } }));
      try {
        const [health, status, sessions] = await Promise.all([
          api.health(),
          api.status(),
          api.sessions(),
        ]);
        const latest = sessions.sessions[0] ?? status.latest_session;
        set({
          health,
          status,
          latest,
          sessions: sessions.sessions,
          orbState: stateForSession(latest),
          stage: latest?.stage ?? "idle",
          errorMessage: latest?.status === "failed" ? latest.error : null,
          audio:
            latest?.status === "speaking" && latest.audio_url
              ? { url: latest.audio_url, sessionId: latest.id }
              : null,
          errors: {},
        });
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, bootstrap: messageOf(error) },
        }));
      } finally {
        set((state) => ({ loading: { ...state.loading, bootstrap: false } }));
      }
    },

    connectEvents: () => {
      if (stopStream) return;
      stopStream = createEventStream({
        onConnection: (connection) =>
          set((state) => ({
            connection,
            errors:
              connection === "online"
                ? { ...state.errors, bootstrap: undefined }
                : state.errors,
          })),
        onStatus: (status) => get().handleStatus(status),
        onEvent: (event) => get().handleEvent(event),
      });
    },

    disconnectEvents: () => {
      stopStream?.();
      stopStream = null;
    },

    handleStatus: (status) => {
      const latest = status.latest_session ?? get().latest;
      set((state) => ({
        status,
        latest,
        orbState: stateForSession(latest),
        stage: latest?.stage ?? "idle",
        errorMessage: latest?.status === "failed" ? latest.error : null,
        audio:
          !state.audio && latest?.status === "speaking" && latest.audio_url
            ? { url: latest.audio_url, sessionId: latest.id }
            : state.audio,
      }));
    },

    handleEvent: (event) => {
      if (event.type === "snapshot") {
        const snapshot = event as BridgeEvent & { events?: BridgeEvent[] };
        set((state) => ({
          events: Array.isArray(snapshot.events) ? snapshot.events : state.events,
        }));
        return;
      }

      const nextOrb = orbStateFromEvent(event);
      set((state) => {
        const latest =
          state.latest && event.session_id === state.latest.id
            ? patchSession(state.latest, event)
            : state.latest;
        return {
          events: [...state.events, event].slice(-300),
          orbState: nextOrb ?? state.orbState,
          stage: event.stage ?? state.stage,
          latest,
          errorMessage:
            event.type === "session_failed"
              ? (event.message ?? "The session failed.")
              : event.type === "session_started" || event.type === "playback_completed"
                ? null
                : state.errorMessage,
          audio:
            event.type === "playback_ready" && event.audio_url
              ? { url: event.audio_url, sessionId: event.session_id ?? "" }
              : event.type === "playback_completed" || event.type === "session_failed"
                ? null
                : state.audio,
        };
      });

      if (event.type === "config_updated") void get().refreshConfig();
      if (event.type === "credentials_updated") {
        void get().refreshProviders();
        void get().refreshStatus();
      }
      if (event.type === "ignore_updated") void get().refreshIgnore();
      if (event.session_id) scheduleRefresh();
    },

    refreshStatus: async () => {
      set((state) => ({ loading: { ...state.loading, status: true } }));
      try {
        const status = await api.status();
        const latest = status.latest_session ?? get().latest;
        set((state) => ({
          status,
          latest,
          audio:
            !state.audio && latest?.status === "speaking" && latest.audio_url
              ? { url: latest.audio_url, sessionId: latest.id }
              : state.audio,
        }));
      } catch {
        // Keep the last known status; the connection indicator shows outages.
      } finally {
        set((state) => ({ loading: { ...state.loading, status: false } }));
      }
    },

    refreshSessions: async () => {
      set((state) => ({ loading: { ...state.loading, sessions: true } }));
      try {
        const response = await api.sessions();
        set((state) => ({
          sessions: response.sessions,
          latest: response.sessions[0] ?? state.latest,
        }));
      } catch {
        // Non-blocking.
      } finally {
        set((state) => ({ loading: { ...state.loading, sessions: false } }));
      }
    },

    refreshConfig: async () => {
      set((state) => ({
        loading: { ...state.loading, config: true },
        errors: { ...state.errors, config: undefined },
      }));
      try {
        const config = await api.config();
        set({ config });
      } catch (error) {
        set((state) => ({ errors: { ...state.errors, config: messageOf(error) } }));
      } finally {
        set((state) => ({ loading: { ...state.loading, config: false } }));
      }
    },

    refreshProviders: async () => {
      set((state) => ({
        loading: { ...state.loading, providers: true },
        errors: { ...state.errors, providers: undefined },
      }));
      try {
        const response = await api.providers();
        set({
          providers: response.providers,
          selectedLlm: response.selected_llm,
        });
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, providers: messageOf(error) },
        }));
      } finally {
        set((state) => ({ loading: { ...state.loading, providers: false } }));
      }
    },

    refreshGit: async () => {
      set((state) => ({
        loading: { ...state.loading, git: true },
        errors: { ...state.errors, git: undefined },
      }));
      try {
        const git = await api.gitContext();
        set({ git });
      } catch (error) {
        set((state) => ({ errors: { ...state.errors, git: messageOf(error) } }));
      } finally {
        set((state) => ({ loading: { ...state.loading, git: false } }));
      }
    },

    refreshIgnore: async () => {
      set((state) => ({
        loading: { ...state.loading, ignore: true },
        errors: { ...state.errors, ignore: undefined },
      }));
      try {
        const ignore = await api.ignoreRules();
        set({ ignore });
      } catch (error) {
        set((state) => ({ errors: { ...state.errors, ignore: messageOf(error) } }));
      } finally {
        set((state) => ({ loading: { ...state.loading, ignore: false } }));
      }
    },

    refreshLogs: async () => {
      set((state) => ({
        loading: { ...state.loading, logs: true },
        errors: { ...state.errors, logs: undefined },
      }));
      try {
        const response = await api.logs();
        set({
          logs: response.entries,
          logPath: response.path,
          logsExist: response.exists,
        });
      } catch (error) {
        set((state) => ({ errors: { ...state.errors, logs: messageOf(error) } }));
      } finally {
        set((state) => ({ loading: { ...state.loading, logs: false } }));
      }
    },

    startSession: async () => {
      set((state) => ({
        loading: { ...state.loading, action: true },
        errors: { ...state.errors, session: undefined },
      }));
      try {
        const session = await api.startSession();
        set({
          latest: session,
          orbState: "listening",
          stage: "recording",
          errorMessage: null,
          audio: null,
          notice: { kind: "info", message: "Listening… speak your bug now." },
        });
        void get().refreshSessions();
        return session;
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, session: messageOf(error) },
          notice: { kind: "error", message: messageOf(error) },
        }));
        return null;
      } finally {
        set((state) => ({ loading: { ...state.loading, action: false } }));
      }
    },

    retrySession: async (sessionId) => {
      set((state) => ({
        loading: { ...state.loading, action: true },
        errors: { ...state.errors, session: undefined },
      }));
      try {
        const session = await api.retrySession(sessionId);
        set({
          latest: session,
          orbState: "listening",
          stage: "recording",
          errorMessage: null,
          audio: null,
          notice: { kind: "info", message: "Retrying session — speak now." },
        });
        void get().refreshSessions();
        return session;
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, session: messageOf(error) },
          notice: { kind: "error", message: messageOf(error) },
        }));
        return null;
      } finally {
        set((state) => ({ loading: { ...state.loading, action: false } }));
      }
    },

    saveConfig: async (update) => {
      set((state) => ({
        loading: { ...state.loading, action: true },
        errors: { ...state.errors, config: undefined },
      }));
      try {
        const config = await api.updateConfig(update);
        set({
          config,
          notice: { kind: "success", message: "Settings saved. Restart the daemon if the hotkey changed." },
        });
        return true;
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, config: messageOf(error) },
          notice: { kind: "error", message: messageOf(error) },
        }));
        return false;
      } finally {
        set((state) => ({ loading: { ...state.loading, action: false } }));
      }
    },

    saveProviderKey: async (provider, apiKey) => {
      // The key exists only in this closure and the request body.
      // It is never written to the store, storage or logs.
      set((state) => ({
        loading: { ...state.loading, action: true },
        errors: { ...state.errors, providers: undefined },
      }));
      try {
        await api.saveProviderCredential(provider, apiKey);
        const response = await api.providers();
        set({
          providers: response.providers,
          selectedLlm: response.selected_llm,
          notice: { kind: "success", message: "API key configured ✓" },
        });
        void get().refreshStatus();
        return true;
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, providers: messageOf(error) },
          notice: { kind: "error", message: messageOf(error) },
        }));
        return false;
      } finally {
        set((state) => ({ loading: { ...state.loading, action: false } }));
      }
    },

    removeProviderKey: async (provider) => {
      set((state) => ({
        loading: { ...state.loading, action: true },
        errors: { ...state.errors, providers: undefined },
      }));
      try {
        await api.removeProviderCredential(provider);
        const response = await api.providers();
        set({
          providers: response.providers,
          selectedLlm: response.selected_llm,
          notice: { kind: "info", message: "API key removed." },
        });
        void get().refreshStatus();
        return true;
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, providers: messageOf(error) },
          notice: { kind: "error", message: messageOf(error) },
        }));
        return false;
      } finally {
        set((state) => ({ loading: { ...state.loading, action: false } }));
      }
    },

    selectLlmProvider: async (provider) => {
      set((state) => ({
        loading: { ...state.loading, action: true },
        errors: { ...state.errors, providers: undefined },
      }));
      try {
        await api.updateConfig({ llm_provider: provider });
        const [config, providers] = await Promise.all([
          api.config(),
          api.providers(),
        ]);
        set({
          config,
          providers: providers.providers,
          selectedLlm: providers.selected_llm,
          notice: { kind: "success", message: `${provider} is now the active provider.` },
        });
        return true;
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, providers: messageOf(error) },
          notice: { kind: "error", message: messageOf(error) },
        }));
        return false;
      } finally {
        set((state) => ({ loading: { ...state.loading, action: false } }));
      }
    },

    saveProviderModel: async (provider, model) => {
      set((state) => ({
        loading: { ...state.loading, action: true },
        errors: { ...state.errors, providers: undefined },
      }));
      try {
        const update: ConfigUpdate =
          provider === "groq" ? { llm_groq_model: model } : { llm_model: model };
        const config = await api.updateConfig(update);
        const providers = await api.providers();
        set({
          config,
          providers: providers.providers,
          selectedLlm: providers.selected_llm,
          notice: { kind: "success", message: `${provider} model saved.` },
        });
        return true;
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, providers: messageOf(error) },
          notice: { kind: "error", message: messageOf(error) },
        }));
        return false;
      } finally {
        set((state) => ({ loading: { ...state.loading, action: false } }));
      }
    },

    applyIgnore: async (patterns, destination) => {
      set((state) => ({
        loading: { ...state.loading, action: true },
        errors: { ...state.errors, ignore: undefined },
      }));
      try {
        const response = await api.applyIgnore(patterns, destination);
        set({
          ignore: response,
          notice: {
            kind: "success",
            message:
              response.applied.length > 0
                ? `Applied ${response.applied.length} ignore pattern(s).`
                : "No new patterns to apply.",
          },
        });
        return true;
      } catch (error) {
        set((state) => ({
          errors: { ...state.errors, ignore: messageOf(error) },
          notice: { kind: "error", message: messageOf(error) },
        }));
        return false;
      } finally {
        set((state) => ({ loading: { ...state.loading, action: false } }));
      }
    },

    deleteAudio: async (sessionId) => {
      try {
        await api.deleteAudio(sessionId);
        set((state) => ({
          sessions: state.sessions.map((session) =>
            session.id === sessionId ? { ...session, audio_url: null } : session,
          ),
          latest:
            state.latest?.id === sessionId
              ? { ...state.latest, audio_url: null }
              : state.latest,
          notice: { kind: "success", message: "Session audio deleted." },
        }));
      } catch (error) {
        set({ notice: { kind: "error", message: messageOf(error) } });
      }
    },

    setAudio: (audio) => set({ audio }),

    finishPlayback: () => {
      set({ audio: null, orbState: "idle", stage: "idle" });
      void get().refreshStatus();
      void get().refreshSessions();
    },

    setNotice: (notice) => set({ notice }),
    clearNotice: () => set({ notice: null }),
  };
});
