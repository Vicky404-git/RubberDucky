import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  FileWarning,
  Fingerprint,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select, Toggle } from "../components/ui/Field";
import { EmptyState, ErrorBanner, Skeleton } from "../components/ui/States";
import { useAppStore } from "../stores/appStore";

type Destination = "rubberducky" | "git";

export function IgnoreManager() {
  const ignore = useAppStore((state) => state.ignore);
  const loading = useAppStore((state) => state.loading);
  const error = useAppStore((state) => state.errors.ignore);
  const refreshIgnore = useAppStore((state) => state.refreshIgnore);
  const applyIgnore = useAppStore((state) => state.applyIgnore);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [destination, setDestination] = useState<Destination>("rubberducky");
  const [approved, setApproved] = useState(false);

  useEffect(() => {
    void refreshIgnore();
  }, [refreshIgnore]);

  const suggestionKey = ignore?.suggestions.join("|") ?? "";
  useEffect(() => {
    setSelected(new Set());
    setApproved(false);
  }, [suggestionKey]);

  const allSelected = useMemo(
    () => Boolean(ignore?.suggestions.length) && selected.size === ignore?.suggestions.length,
    [ignore?.suggestions.length, selected.size],
  );

  const toggle = (pattern: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(pattern)) next.delete(pattern);
      else next.add(pattern);
      return next;
    });
  };

  const toggleAll = () => {
    if (!ignore) return;
    setSelected(allSelected ? new Set() : new Set(ignore.suggestions));
  };

  const apply = async () => {
    if (!approved || selected.size === 0) return;
    const success = await applyIgnore(Array.from(selected), destination);
    if (success) {
      setSelected(new Set());
      setApproved(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI context protection"
        title="Ignore Manager"
        description="Review which paths RubberDucky excludes from Git context, and approve any new ignore patterns yourself. Sensitive files are detected by path only — their contents are never read."
        actions={
          <Button size="sm" variant="ghost" onClick={() => void refreshIgnore()} loading={loading.ignore}>
            <RefreshCw className="h-3.5 w-3.5" /> Rescan
          </Button>
        }
      />

      {error ? <ErrorBanner message={error} onRetry={() => void refreshIgnore()} /> : null}

      {loading.ignore && !ignore ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
      ) : ignore ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="glass-panel px-4 py-3.5">
              <p className="eyebrow">.gitignore</p>
              <p className="mt-1.5 text-lg font-semibold text-zinc-100">{ignore.gitignore.rules.length}</p>
              <p className="text-[11px] text-zinc-600">repository rules</p>
            </div>
            <div className="glass-panel px-4 py-3.5">
              <p className="eyebrow">.rubberduckyignore</p>
              <p className="mt-1.5 text-lg font-semibold text-zinc-100">{ignore.rubberduckyignore.rules.length}</p>
              <p className="text-[11px] text-zinc-600">AI-only exclusions</p>
            </div>
            <div className="glass-panel px-4 py-3.5">
              <p className="eyebrow">Secret patterns</p>
              <p className="mt-1.5 text-lg font-semibold text-zinc-100">{ignore.builtin_sensitive_patterns.length}</p>
              <p className="text-[11px] text-zinc-600">always enforced</p>
            </div>
            <div className="glass-panel px-4 py-3.5">
              <p className="eyebrow">Sensitive files found</p>
              <p className="mt-1.5 text-lg font-semibold text-zinc-100">{ignore.sensitive_findings.length}</p>
              <p className="text-[11px] text-zinc-600">of {ignore.candidate_count} scanned paths</p>
            </div>
          </div>

          <Panel
            title={
              <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
                <FileWarning className="h-4 w-4 text-amber-glow" aria-hidden /> Sensitive-file detection
              </span>
            }
            subtitle="Paths matching built-in secret rules. They are already excluded from AI context."
          >
            {ignore.sensitive_findings.length === 0 ? (
              <EmptyState
                title="No sensitive files detected"
                description="No non-ignored paths matched the built-in credential patterns."
                icon={<ShieldCheck className="h-4 w-4" />}
              />
            ) : (
              <ul className="grid max-h-[240px] gap-1.5 overflow-auto font-mono text-[11px] text-amber-glow/90 sm:grid-cols-2">
                {ignore.sensitive_findings.map((path) => (
                  <li key={path} className="truncate rounded-lg border border-amber-glow/20 bg-amber-glow/[0.055] px-3 py-2">
                    {path}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(340px,0.9fr)]">
            <Panel
              title={
                <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
                  <Sparkles className="h-4 w-4 text-duck-300" aria-hidden /> Suggested patterns
                </span>
              }
              subtitle="Deterministic local heuristics from IgnoreManager.suggest_patterns(). Nothing is written automatically."
              action={
                ignore.suggestions.length > 0 ? (
                  <Button size="sm" variant="ghost" onClick={toggleAll}>
                    {allSelected ? "Clear all" : "Select all"}
                  </Button>
                ) : null
              }
            >
              {ignore.suggestions.length === 0 ? (
                <EmptyState
                  title="No suggestions right now"
                  description="The working tree does not contain obvious generated artifacts, caches or secret files that are still exposed."
                />
              ) : (
                <div className="space-y-4">
                  <ul className="space-y-1.5">
                    {ignore.suggestions.map((pattern) => {
                      const checked = selected.has(pattern);
                      return (
                        <li key={pattern}>
                          <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-white/[0.06] bg-black/20 px-3.5 py-2.5 transition-colors hover:border-white/[0.12]">
                            <span
                              className={`flex h-4 w-4 items-center justify-center rounded border ${
                                checked ? "border-duck-400 bg-duck-400 text-ink-950" : "border-white/20 bg-transparent"
                              }`}
                            >
                              {checked ? <Check className="h-3 w-3" aria-hidden /> : null}
                            </span>
                            <input
                              type="checkbox"
                              className="sr-only"
                              checked={checked}
                              onChange={() => toggle(pattern)}
                            />
                            <span className="font-mono text-xs text-zinc-300">{pattern}</span>
                            <Badge tone="neutral" className="ml-auto">
                              proposed
                            </Badge>
                          </label>
                        </li>
                      );
                    })}
                  </ul>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <label htmlFor="ignore-destination" className="text-xs font-medium text-zinc-300">
                        Destination
                      </label>
                      <Select
                        id="ignore-destination"
                        value={destination}
                        onChange={(event) => setDestination(event.target.value as Destination)}
                      >
                        <option value="rubberducky">.rubberduckyignore — AI context only</option>
                        <option value="git">.gitignore — Git tracking rules</option>
                      </Select>
                    </div>
                    <div className="rounded-xl border border-white/[0.06] bg-black/20 px-3.5 py-2.5 text-[11px] leading-relaxed text-zinc-500">
                      {destination === "rubberducky"
                        ? "Safest option: hides paths from the AI without changing Git behaviour."
                        : "Note: .gitignore does not untrack files that Git already tracks."}
                    </div>
                  </div>

                  <Toggle
                    checked={approved}
                    onChange={setApproved}
                    label="I reviewed and approve these patterns"
                    description="Required. The backend rejects ignore changes without explicit approval."
                  />

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-[11px] text-zinc-600">
                      {selected.size} selected · appends only, never rewrites existing rules
                    </p>
                    <Button
                      variant="primary"
                      onClick={() => void apply()}
                      disabled={!approved || selected.size === 0 || loading.action}
                      loading={loading.action}
                    >
                      Apply approved patterns
                    </Button>
                  </div>
                </div>
              )}
            </Panel>

            <div className="space-y-5">
              <Panel
                title=".rubberduckyignore"
                subtitle={ignore.rubberduckyignore.path}
                action={
                  <Badge tone={ignore.rubberduckyignore.exists ? "success" : "neutral"}>
                    {ignore.rubberduckyignore.exists ? "active" : "missing"}
                  </Badge>
                }
              >
                {ignore.rubberduckyignore.rules.length === 0 ? (
                  <EmptyState title="No custom AI exclusions" />
                ) : (
                  <ul className="max-h-[220px] space-y-1 overflow-auto font-mono text-[11px] text-zinc-400">
                    {ignore.rubberduckyignore.rules.map((rule) => (
                      <li key={rule} className="rounded-md border border-white/[0.05] bg-black/20 px-2.5 py-1.5">
                        {rule}
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              <Panel
                title=".gitignore"
                subtitle={ignore.gitignore.path}
                action={
                  <Badge tone={ignore.gitignore.exists ? "success" : "neutral"}>
                    {ignore.gitignore.exists ? "active" : "missing"}
                  </Badge>
                }
              >
                {ignore.gitignore.rules.length === 0 ? (
                  <EmptyState title="No Git ignore rules" />
                ) : (
                  <ul className="max-h-[220px] space-y-1 overflow-auto font-mono text-[11px] text-zinc-400">
                    {ignore.gitignore.rules.map((rule) => (
                      <li key={rule} className="rounded-md border border-white/[0.05] bg-black/20 px-2.5 py-1.5">
                        {rule}
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>
          </div>

          <Panel
            title={
              <span className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
                <Fingerprint className="h-4 w-4 text-zinc-500" aria-hidden /> Built-in sensitive patterns
              </span>
            }
            subtitle="Always enforced regardless of repository ignore files."
          >
            <div className="flex flex-wrap gap-1.5">
              {ignore.builtin_sensitive_patterns.map((pattern) => (
                <code
                  key={pattern}
                  className="rounded-md border border-white/[0.06] bg-black/25 px-2 py-1 font-mono text-[10px] text-zinc-500"
                >
                  {pattern}
                </code>
              ))}
            </div>
            <p className="mt-3 flex items-start gap-2 text-[11px] leading-relaxed text-zinc-600">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              Secret redaction is defence-in-depth, not a guarantee. Keep credentials in .env and
              never speak them into a session.
            </p>
          </Panel>
        </>
      ) : (
        <EmptyState
          title="Ignore rules unavailable"
          description="The bridge could not read ignore configuration."
        />
      )}
    </div>
  );
}
