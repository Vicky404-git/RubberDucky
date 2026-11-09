import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Cpu,
  FolderCog,
  KeyRound,
  Keyboard,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Terminal,
  Volume2,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Field, Input, Select, Toggle } from "../components/ui/Field";
import { ErrorBanner, Skeleton } from "../components/ui/States";
import { useAppStore } from "../stores/appStore";
import type { ConfigUpdate, SafeConfig } from "../types/api";

interface FormState {
  llmProvider: string;
  llmModel: string;
  llmTemperature: number;
  llmMaxTokens: number;
  llmTimeout: number;
  voiceLanguage: string;
  recordSeconds: number;
  gitMaxCommits: number;
  gitMaxChars: number;
  loggingLevel: string;
  hotkeyKey: string;
  hotkeyModifiers: string;
  triageDevice: string;
  triageLazyLoad: boolean;
}

function toForm(config: SafeConfig): FormState {
  return {
    llmProvider: config.llm.provider,
    llmModel: config.llm.model,
    llmTemperature: config.llm.temperature,
    llmMaxTokens: config.llm.max_tokens,
    llmTimeout: config.llm.timeout,
    voiceLanguage: config.voice.language,
    recordSeconds: config.voice.record_seconds,
    gitMaxCommits: config.git.max_commits,
    gitMaxChars: config.git.max_chars,
    loggingLevel: config.logging.level,
    hotkeyKey: config.hotkey.key,
    hotkeyModifiers: config.hotkey.modifiers,
    triageDevice: config.triage.device,
    triageLazyLoad: config.triage.lazy_load,
  };
}

function changes(config: SafeConfig, form: FormState): ConfigUpdate {
  const update: ConfigUpdate = {};
  if (form.llmProvider !== config.llm.provider) update.llm_provider = form.llmProvider;
  if (form.llmModel !== config.llm.model) update.llm_model = form.llmModel;
  if (form.llmTemperature !== config.llm.temperature) update.llm_temperature = form.llmTemperature;
  if (form.llmMaxTokens !== config.llm.max_tokens) update.llm_max_tokens = form.llmMaxTokens;
  if (form.llmTimeout !== config.llm.timeout) update.llm_timeout = form.llmTimeout;
  if (form.voiceLanguage !== config.voice.language) update.voice_language = form.voiceLanguage;
  if (form.recordSeconds !== config.voice.record_seconds) update.record_seconds = form.recordSeconds;
  if (form.gitMaxCommits !== config.git.max_commits) update.git_max_commits = form.gitMaxCommits;
  if (form.gitMaxChars !== config.git.max_chars) update.git_max_chars = form.gitMaxChars;
  if (form.loggingLevel !== config.logging.level) update.logging_level = form.loggingLevel;
  if (form.hotkeyKey !== config.hotkey.key) update.hotkey_key = form.hotkeyKey;
  if (form.hotkeyModifiers !== config.hotkey.modifiers) update.hotkey_modifiers = form.hotkeyModifiers;
  if (form.triageDevice !== config.triage.device) update.triage_device = form.triageDevice;
  if (form.triageLazyLoad !== config.triage.lazy_load) update.triage_lazy_load = form.triageLazyLoad;
  return update;
}

export function Settings() {
  const config = useAppStore((state) => state.config);
  const health = useAppStore((state) => state.health);
  const loading = useAppStore((state) => state.loading);
  const error = useAppStore((state) => state.errors.config);
  const refreshConfig = useAppStore((state) => state.refreshConfig);
  const saveConfig = useAppStore((state) => state.saveConfig);

  const [form, setForm] = useState<FormState | null>(null);

  useEffect(() => {
    void refreshConfig();
  }, [refreshConfig]);

  useEffect(() => {
    if (config) setForm(toForm(config));
  }, [config]);

  const update = useMemo(
    () => (config && form ? changes(config, form) : {}),
    [config, form],
  );
  const dirty = Object.keys(update).length > 0;

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  };

  if (!config || !form) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow="Configuration" title="Settings" description="Loading rubberducky.ini…" />
        {error ? <ErrorBanner message={error} onRetry={() => void refreshConfig()} /> : null}
        <div className="grid gap-5 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-64 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="Edits are written to the existing rubberducky.ini without replacing unmanaged keys, comments or secrets. Only changed fields are sent."
        actions={
          <>
            <Badge tone={dirty ? "duck" : "neutral"}>
              {dirty ? `${Object.keys(update).length} unsaved` : "Saved"}
            </Badge>
            <Button
              variant="primary"
              size="sm"
              onClick={() => void saveConfig(update)}
              disabled={!dirty || loading.action}
              loading={loading.action}
            >
              <Save className="h-3.5 w-3.5" /> Save changes
            </Button>
          </>
        }
      />

      {error ? <ErrorBanner message={error} onRetry={() => void refreshConfig()} /> : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          title={
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <SlidersHorizontal className="h-4 w-4 text-duck-300" aria-hidden /> Language model
            </span>
          }
          subtitle="OpenRouter is the only provider implemented by the backend."
        >
          <div className="space-y-4">
            <Field label="Provider" htmlFor="llm-provider">
              <Select
                id="llm-provider"
                value={form.llmProvider}
                onChange={(event) => set("llmProvider", event.target.value)}
              >
                <option value="openrouter">OpenRouter</option>
              </Select>
            </Field>
            <Field label="Model" htmlFor="llm-model" hint="OpenRouter model id">
              <Input
                id="llm-model"
                value={form.llmModel}
                onChange={(event) => set("llmModel", event.target.value)}
                spellCheck={false}
                className="font-mono text-xs"
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Temperature" htmlFor="llm-temperature">
                <Input
                  id="llm-temperature"
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={form.llmTemperature}
                  onChange={(event) => set("llmTemperature", Number(event.target.value))}
                />
              </Field>
              <Field label="Max tokens" htmlFor="llm-tokens">
                <Input
                  id="llm-tokens"
                  type="number"
                  min={64}
                  max={8192}
                  value={form.llmMaxTokens}
                  onChange={(event) => set("llmMaxTokens", Number(event.target.value))}
                />
              </Field>
              <Field label="Timeout (s)" htmlFor="llm-timeout">
                <Input
                  id="llm-timeout"
                  type="number"
                  min={3}
                  max={180}
                  value={form.llmTimeout}
                  onChange={(event) => set("llmTimeout", Number(event.target.value))}
                />
              </Field>
            </div>
          </div>
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <Volume2 className="h-4 w-4 text-duck-300" aria-hidden /> Voice capture
            </span>
          }
          subtitle="Recording duration and language for Gnani Prisma STT and Timbre TTS."
        >
          <div className="space-y-5">
            <Field label="Language" htmlFor="voice-language" hint="e.g. hi-IN">
              <Input
                id="voice-language"
                value={form.voiceLanguage}
                onChange={(event) => set("voiceLanguage", event.target.value)}
                className="font-mono text-xs"
              />
            </Field>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label htmlFor="record-seconds" className="text-xs font-medium text-zinc-300">
                  Recording duration
                </label>
                <span className="font-mono text-xs text-duck-200">{form.recordSeconds}s</span>
              </div>
              <input
                id="record-seconds"
                type="range"
                min={1}
                max={30}
                step={1}
                value={form.recordSeconds}
                onChange={(event) => set("recordSeconds", Number(event.target.value))}
                className="w-full"
              />
              <div className="mt-1.5 flex justify-between text-[10px] text-zinc-600">
                <span>1s</span>
                <span>arecord fixed duration</span>
                <span>30s</span>
              </div>
            </div>
          </div>
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <FolderCog className="h-4 w-4 text-duck-300" aria-hidden /> Git context
            </span>
          }
          subtitle="Read-only limits applied before context reaches the LLM."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Commit count" htmlFor="git-commits" hint="1–50">
              <Input
                id="git-commits"
                type="number"
                min={1}
                max={50}
                value={form.gitMaxCommits}
                onChange={(event) => set("gitMaxCommits", Number(event.target.value))}
              />
            </Field>
            <Field label="Max context chars" htmlFor="git-chars" hint="500–100000">
              <Input
                id="git-chars"
                type="number"
                min={500}
                max={100000}
                step={100}
                value={form.gitMaxChars}
                onChange={(event) => set("gitMaxChars", Number(event.target.value))}
              />
            </Field>
          </div>
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <Cpu className="h-4 w-4 text-duck-300" aria-hidden /> Triage engine
            </span>
          }
          subtitle="LAYA loads lazily and uses a keyword router before inference."
        >
          <div className="space-y-4">
            <Field label="Device" htmlFor="triage-device">
              <Select
                id="triage-device"
                value={form.triageDevice}
                onChange={(event) => set("triageDevice", event.target.value)}
              >
                <option value="cpu">CPU</option>
                <option value="cuda">CUDA</option>
              </Select>
            </Field>
            <Toggle
              checked={form.triageLazyLoad}
              onChange={(value) => set("triageLazyLoad", value)}
              label="Lazy load LAYA"
              description="Load the router on first inference instead of bridge startup."
            />
          </div>
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <Keyboard className="h-4 w-4 text-duck-300" aria-hidden /> Hotkey
            </span>
          }
          subtitle="Shared with the C++ X11 daemon. Restart the daemon after changing it."
        >
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Key" htmlFor="hotkey-key" hint="X11 keysym name">
                <Input
                  id="hotkey-key"
                  value={form.hotkeyKey}
                  onChange={(event) => set("hotkeyKey", event.target.value)}
                  className="font-mono text-xs"
                />
              </Field>
              <Field label="Modifiers" htmlFor="hotkey-modifiers" hint="joined with +">
                <Input
                  id="hotkey-modifiers"
                  value={form.hotkeyModifiers}
                  onChange={(event) => set("hotkeyModifiers", event.target.value)}
                  className="font-mono text-xs"
                />
              </Field>
            </div>
            <p className="rounded-lg border border-amber-glow/15 bg-amber-glow/[0.045] px-3 py-2 text-[11px] leading-relaxed text-amber-glow/90">
              Supported modifiers: Mod1–Mod5, Alt, Super, Win, Ctrl, Shift. Example:{" "}
              <code className="font-mono">Mod4+Alt</code> + <code className="font-mono">v</code>.
            </p>
          </div>
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <Terminal className="h-4 w-4 text-duck-300" aria-hidden /> Logging
            </span>
          }
          subtitle="Diagnostic metadata only — transcripts, diffs and secrets are never logged."
        >
          <Field label="Level" htmlFor="logging-level">
            <Select
              id="logging-level"
              value={form.loggingLevel}
              onChange={(event) => set("loggingLevel", event.target.value)}
            >
              {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </Select>
          </Field>
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <KeyRound className="h-4 w-4 text-duck-300" aria-hidden /> Credentials
            </span>
          }
          subtitle="Secrets stay in .env and are never sent to the browser."
        >
          <div className="space-y-2.5">
            {[
              { label: "GNANI_API", ready: Boolean(health?.has_gnani_key) },
              { label: "OPENROUTER_API_KEY", ready: Boolean(health?.has_openrouter_key) },
            ].map((item) => (
              <div
                key={item.label}
                className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-black/20 px-3.5 py-2.5"
              >
                <span className="font-mono text-[11px] text-zinc-400">{item.label}</span>
                <Badge tone={item.ready ? "success" : "error"} dot>
                  {item.ready ? "Configured" : "Missing"}
                </Badge>
              </div>
            ))}
            <p className="text-[11px] leading-relaxed text-zinc-600">
              .env file: {config.paths.env_file_present ? "present" : "not found"}. Values are read
              only by the Python bridge; the UI only receives presence booleans.
            </p>
          </div>
        </Panel>

        <Panel
          title={
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <ShieldCheck className="h-4 w-4 text-duck-300" aria-hidden /> Ignore settings
            </span>
          }
          subtitle="Managed by the existing IgnoreManager and reviewed on its own page."
          action={
            <Link
              to="/ignore"
              className="focus-ring text-[11px] text-zinc-500 underline-offset-2 hover:text-duck-200 hover:underline"
            >
              Open manager
            </Link>
          }
        >
          <ul className="space-y-2 font-mono text-[11px] text-zinc-500">
            <li className="flex items-center justify-between gap-3">
              <span className="truncate">.gitignore</span>
              <Badge tone={config.ignore.gitignore_exists ? "success" : "neutral"}>
                {config.ignore.gitignore_exists ? "active" : "missing"}
              </Badge>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span className="truncate">.rubberduckyignore</span>
              <Badge tone={config.ignore.rubberduckyignore_exists ? "success" : "neutral"}>
                {config.ignore.rubberduckyignore_exists ? "active" : "missing"}
              </Badge>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span className="truncate">Built-in secret patterns</span>
              <Badge tone="duck">{config.ignore.builtin_sensitive_patterns.length}</Badge>
            </li>
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-zinc-600">
            No ignore toggle is exposed because built-in secret protection is always enforced.
          </p>
        </Panel>

        <Panel title="Paths" subtitle="Read-only runtime locations." className="lg:col-span-2">
          <dl className="grid gap-2 text-[11px] sm:grid-cols-2">
            {[
              ["Project root", config.paths.project_root],
              ["Config", config.paths.config_path],
              ["State", config.paths.state_dir],
              ["Frontend build", config.paths.frontend_dist],
            ].map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="text-zinc-600">{label}</dt>
                <dd className="truncate font-mono text-zinc-400" title={value}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>

      <div className="flex justify-end">
        <Button
          variant="primary"
          onClick={() => void saveConfig(update)}
          disabled={!dirty || loading.action}
          loading={loading.action}
        >
          <Save className="h-4 w-4" /> Save changes
        </Button>
      </div>
    </div>
  );
}
