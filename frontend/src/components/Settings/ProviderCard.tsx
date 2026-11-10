import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Trash2,
  XCircle,
} from "lucide-react";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Input } from "../ui/Field";
import { cn } from "../../lib/cn";
import type { ProviderInfo, ProviderTestResult } from "../../types/api";

interface ProviderCardProps {
  provider: ProviderInfo;
  /** Disable all actions while a global operation is running. */
  busy?: boolean;
  onSelectProvider?: () => void;
  onSaveKey: (apiKey: string) => Promise<boolean>;
  onRemoveKey: () => Promise<boolean>;
  onSaveModel?: (model: string) => Promise<boolean>;
  onTestConnection?: () => Promise<ProviderTestResult>;
}

type LocalNotice =
  | { kind: "success"; message: string }
  | { kind: "error"; message: string }
  | null;

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function ProviderCard({
  provider,
  busy = false,
  onSelectProvider,
  onSaveKey,
  onRemoveKey,
  onSaveModel,
  onTestConnection,
}: ProviderCardProps) {
  const isLlm = provider.kind === "llm";
  const isSpeech = provider.kind === "speech";

  // API keys live only in this transient state: never in the store,
  // localStorage, sessionStorage or URLs, and cleared after every save.
  const [keyValue, setKeyValue] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const [removingKey, setRemovingKey] = useState(false);

  const [model, setModel] = useState(provider.model ?? "");
  const [savingModel, setSavingModel] = useState(false);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null);

  const [notice, setNotice] = useState<LocalNotice>(null);

  // Keep the local model field in sync with refreshed backend metadata.
  useEffect(() => {
    setModel(provider.model ?? "");
  }, [provider.model]);

  const handleSaveKey = async () => {
    const trimmed = keyValue.trim();
    if (!trimmed) return;
    setSavingKey(true);
    setNotice(null);
    try {
      const ok = await onSaveKey(trimmed);
      if (ok) {
        setKeyValue("");
        setShowKey(false);
        setNotice({ kind: "success", message: "API key configured ✓" });
        setTestResult(null);
      }
    } catch (error) {
      setNotice({ kind: "error", message: errorMessage(error) });
    } finally {
      setSavingKey(false);
    }
  };

  const handleRemoveKey = async () => {
    setRemovingKey(true);
    setNotice(null);
    try {
      const ok = await onRemoveKey();
      if (ok) {
        setKeyValue("");
        setShowKey(false);
        setNotice({ kind: "success", message: "API key removed." });
        setTestResult(null);
      }
    } catch (error) {
      setNotice({ kind: "error", message: errorMessage(error) });
    } finally {
      setRemovingKey(false);
    }
  };

  const handleSaveModel = async () => {
    const trimmed = model.trim();
    if (!trimmed || trimmed === provider.model || !onSaveModel) return;
    setSavingModel(true);
    setNotice(null);
    try {
      const ok = await onSaveModel(trimmed);
      if (ok) setNotice({ kind: "success", message: "Model saved." });
    } catch (error) {
      setNotice({ kind: "error", message: errorMessage(error) });
    } finally {
      setSavingModel(false);
    }
  };

  const handleTest = async () => {
    if (!onTestConnection) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTestConnection();
      setTestResult(result);
    } catch (error) {
      setTestResult({
        provider: provider.id,
        ok: false,
        message: errorMessage(error),
        model: null,
        model_ok: null,
      });
    } finally {
      setTesting(false);
    }
  };

  const modelDirty = isLlm && model.trim() !== (provider.model ?? "") && model.trim() !== "";

  return (
    <article
      data-provider={provider.id}
      className={cn(
        "flex flex-col gap-4 rounded-2xl border p-4 transition-colors",
        provider.selected
          ? "border-duck-400/35 bg-duck-400/[0.04]"
          : "border-white/[0.07] bg-black/20",
      )}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-sm font-semibold tracking-wide text-zinc-100">
              {provider.name}
            </h3>
            <Badge tone={provider.configured ? "success" : "error"} dot>
              {provider.configured ? "Configured" : "Not configured"}
            </Badge>
            {provider.selected ? <Badge tone="duck">Active provider</Badge> : null}
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-500">
            {provider.description}
          </p>
        </div>
      </header>

      {isLlm && onSelectProvider ? (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-black/25 px-3.5 py-2.5">
          <span className="text-[11px] text-zinc-500">
            {provider.selected
              ? "Used by the debugging pipeline right now."
              : provider.configured
                ? "Only one LLM provider is active at a time."
                : "Save an API key before selecting this provider."}
          </span>
          <Button
            variant={provider.selected ? "secondary" : "primary"}
            size="sm"
            disabled={provider.selected || !provider.configured || busy}
            onClick={onSelectProvider}
          >
            {provider.selected ? "Selected" : "Use this provider"}
          </Button>
        </div>
      ) : null}

      <div className="space-y-2">
        <label
          htmlFor={`${provider.id}-api-key`}
          className="flex items-center gap-1.5 text-xs font-medium text-zinc-300"
        >
          <KeyRound className="h-3.5 w-3.5 text-duck-300" aria-hidden /> API key
        </label>
        <div className="flex items-start gap-2">
          <div className="relative min-w-0 flex-1">
            <Input
              id={`${provider.id}-api-key`}
              type={showKey ? "text" : "password"}
              value={keyValue}
              onChange={(event) => setKeyValue(event.target.value)}
              placeholder={provider.configured ? "Enter a new key to replace it" : "Paste your API key"}
              autoComplete="new-password"
              spellCheck={false}
              className="pr-10 font-mono text-xs"
              disabled={savingKey || removingKey}
            />
            <button
              type="button"
              aria-label={showKey ? "Hide API key" : "Show API key"}
              onClick={() => setShowKey((current) => !current)}
              className="focus-ring absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-zinc-500 transition-colors hover:text-zinc-200"
            >
              {showKey ? (
                <EyeOff className="h-4 w-4" aria-hidden />
              ) : (
                <Eye className="h-4 w-4" aria-hidden />
              )}
            </button>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void handleSaveKey()}
            disabled={!keyValue.trim() || savingKey || removingKey || busy}
            loading={savingKey}
          >
            Save key
          </Button>
          {provider.configured ? (
            <Button
              variant="danger"
              size="sm"
              onClick={() => void handleRemoveKey()}
              disabled={savingKey || removingKey || busy}
              loading={removingKey}
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden /> Remove
            </Button>
          ) : null}
        </div>
        <p className="text-[10px] leading-relaxed text-zinc-600">
          Stored only in the local <code className="font-mono">.env</code> file — never in the
          browser, never returned by the API after saving.
        </p>
      </div>

      {isLlm ? (
        <div className="space-y-2">
          <label
            htmlFor={`${provider.id}-model`}
            className="flex items-center justify-between text-xs font-medium text-zinc-300"
          >
            <span>Model ID</span>
            <span className="text-[10px] font-normal text-zinc-600">
              default: <code className="font-mono">{provider.default_model}</code>
            </span>
          </label>
          <div className="flex items-center gap-2">
            <Input
              id={`${provider.id}-model`}
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder={provider.default_model ?? "model id"}
              spellCheck={false}
              className="font-mono text-xs"
              disabled={savingModel}
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void handleSaveModel()}
              disabled={!modelDirty || savingModel || busy}
              loading={savingModel}
            >
              Save model
            </Button>
          </div>
        </div>
      ) : null}

      {provider.connection_test_supported && onTestConnection ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-medium text-zinc-300">Connection</span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void handleTest()}
              disabled={!provider.configured || testing || busy}
              loading={testing}
            >
              Test connection
            </Button>
          </div>
          {testResult ? (
            <div
              className={cn(
                "flex items-start gap-2 rounded-xl border px-3 py-2.5 text-[11px] leading-relaxed",
                testResult.ok && testResult.model_ok === true
                  ? "border-emerald-400/25 bg-emerald-400/[0.07] text-emerald-300"
                  : testResult.ok
                    ? "border-amber-glow/25 bg-amber-glow/[0.06] text-amber-glow/90"
                    : "border-danger/25 bg-danger/[0.07] text-danger",
              )}
              data-testid="provider-test-result"
            >
              {testResult.ok && testResult.model_ok === true ? (
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              ) : testResult.ok ? (
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              ) : (
                <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              )}
              <span>{testResult.message}</span>
            </div>
          ) : (
            <p className="text-[10px] leading-relaxed text-zinc-600">
              Sends a credentials-only request to {provider.name} — no repository context,
              transcripts or prompts.
            </p>
          )}
        </div>
      ) : null}

      {isSpeech ? (
        <div className="space-y-2.5">
          <div className="flex flex-wrap gap-2">
            <Badge tone={provider.configured ? "success" : "neutral"} dot>
              STT · Prisma {provider.configured ? "enabled" : "needs key"}
            </Badge>
            <Badge tone={provider.configured ? "success" : "neutral"} dot>
              TTS · Timbre {provider.configured ? "enabled" : "needs key"}
            </Badge>
          </div>
          <p className="text-[10px] leading-relaxed text-zinc-600">
            One Gnani credential currently powers both Prisma STT and Timbre TTS. No safe
            credential-only check exists, so “Configured” means the key is stored — the
            speech pipeline itself verifies it when you run a session.
          </p>
        </div>
      ) : null}

      {notice ? (
        <div
          className={cn(
            "rounded-xl border px-3 py-2.5 text-[11px] leading-relaxed",
            notice.kind === "success"
              ? "border-emerald-400/25 bg-emerald-400/[0.07] text-emerald-300"
              : "border-danger/25 bg-danger/[0.07] text-danger",
          )}
          data-testid="provider-notice"
          role="status"
        >
          {notice.message}
        </div>
      ) : null}
    </article>
  );
}
