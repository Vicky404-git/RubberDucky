import { useEffect } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  EyeOff,
  GitBranch,
  GitCommitHorizontal,
  Lock,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { DiffViewer } from "../components/Git/DiffViewer";
import { PageHeader } from "../components/ui/PageHeader";
import { Panel } from "../components/ui/Panel";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorBanner, Skeleton } from "../components/ui/States";
import { useAppStore } from "../stores/appStore";

function statusTone(code: string): string {
  if (code.includes("?")) return "text-sky-300";
  if (code.includes("U")) return "text-danger";
  if (code.includes("M")) return "text-amber-glow";
  if (code.includes("D")) return "text-danger/80";
  if (code.includes("A")) return "text-emerald-300";
  return "text-zinc-400";
}

export function GitContext() {
  const git = useAppStore((state) => state.git);
  const loading = useAppStore((state) => state.loading);
  const error = useAppStore((state) => state.errors.git);
  const refreshGit = useAppStore((state) => state.refreshGit);

  useEffect(() => {
    void refreshGit();
  }, [refreshGit]);

  const statusEntries = (git?.status_lines ?? []).filter((line) => !line.startsWith("##"));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Read-only repository context"
        title="Git Context"
        description="The exact safe context the AI can see: branch, working tree, staged and unstaged diffs, recent commits and conflicts. Sensitive paths are removed and credentials are redacted."
        actions={
          <Button size="sm" variant="ghost" onClick={() => void refreshGit()} loading={loading.git}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />

      <div className="flex items-start gap-2.5 rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3 text-[11px] leading-relaxed text-zinc-500">
        <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-duck-300/70" aria-hidden />
        <p>
          RubberDucky never stages, commits, resets, checks out or pushes. This page only reads
          existing Git state and shows ignore-filtered, secret-redacted output.
        </p>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void refreshGit()} /> : null}

      {loading.git && !git ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
      ) : git ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="glass-panel px-4 py-3.5">
              <p className="eyebrow">Branch</p>
              <p className="mt-1.5 flex items-center gap-2 font-mono text-sm text-zinc-200">
                <GitBranch className="h-3.5 w-3.5 text-duck-300" aria-hidden />
                <span className="truncate">{git.branch}</span>
              </p>
            </div>
            <div className="glass-panel px-4 py-3.5">
              <p className="eyebrow">Working tree</p>
              <p className="mt-1.5 flex items-center gap-2 text-sm">
                {git.clean ? (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" aria-hidden />
                    <span className="text-emerald-300">Clean</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-glow" aria-hidden />
                    <span className="text-amber-glow">{statusEntries.length} changed</span>
                  </>
                )}
              </p>
            </div>
            <div className="glass-panel px-4 py-3.5">
              <p className="eyebrow">Conflicts</p>
              <p className="mt-1.5 flex items-center gap-2 text-sm">
                <ShieldCheck className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
                <span className={git.has_conflicts ? "text-danger" : "text-zinc-300"}>
                  {git.has_conflicts ? `${git.conflicts.length} detected` : "None"}
                </span>
              </p>
            </div>
            <div className="glass-panel px-4 py-3.5">
              <p className="eyebrow">Recent commits</p>
              <p className="mt-1.5 flex items-center gap-2 text-sm text-zinc-300">
                <GitCommitHorizontal className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
                {git.commits.length}
              </p>
            </div>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <Panel title="Working tree status" subtitle="Ignored and sensitive paths are excluded">
              {statusEntries.length === 0 ? (
                <EmptyState
                  title="Working tree is clean"
                  description="No non-ignored tracked or untracked changes."
                  icon={<CheckCircle2 className="h-4 w-4" />}
                />
              ) : (
                <ul className="max-h-[320px] space-y-1 overflow-auto font-mono text-[11px]">
                  {statusEntries.map((line) => (
                    <li key={line} className="flex items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-white/[0.03]">
                      <span className={`w-6 shrink-0 ${statusTone(line.slice(0, 2))}`}>
                        {line.slice(0, 2)}
                      </span>
                      <span className="min-w-0 break-all text-zinc-300">{line.slice(3)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Recent commits" subtitle="Subject lines only · branch history">
              {git.commits.length === 0 ? (
                <EmptyState title="No recent commits" icon={<GitCommitHorizontal className="h-4 w-4" />} />
              ) : (
                <ol className="space-y-3">
                  {git.commits.map((commit) => (
                    <li key={commit.hash} className="flex gap-3">
                      <span className="mt-1 h-2 w-2 shrink-0 rounded-full border border-duck-400/50 bg-duck-400/20" />
                      <div className="min-w-0 flex-1 border-b border-white/[0.05] pb-3 last:border-0 last:pb-0">
                        <p className="truncate text-xs text-zinc-300">{commit.subject}</p>
                        <p className="mt-1 font-mono text-[10px] text-zinc-600">
                          {commit.hash} · {commit.date}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
          </div>

          {git.has_conflicts ? (
            <Panel
              title={
                <span className="flex items-center gap-2 text-sm font-semibold text-danger">
                  <AlertTriangle className="h-4 w-4" aria-hidden /> Merge conflicts
                </span>
              }
              subtitle="Resolve these in your editor or terminal. RubberDucky will not modify them."
            >
              <ul className="space-y-1.5 font-mono text-[11px] text-danger/90">
                {git.conflicts.map((path) => (
                  <li key={path} className="rounded-lg border border-danger/20 bg-danger/[0.06] px-3 py-2">
                    {path}
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}

          <Panel
            title="Safe diff summaries"
            subtitle="Filtered by IgnoreManager, truncated by [git] max_chars and redacted before display"
            action={<Badge tone="neutral">read-only</Badge>}
          >
            <div className="space-y-3">
              <DiffViewer
                title="Staged changes"
                diff={git.staged_diff}
                emptyHint="No staged changes."
                defaultOpen={!git.clean && !git.staged_diff.startsWith("No ")}
              />
              <DiffViewer
                title="Unstaged changes"
                diff={git.unstaged_diff}
                emptyHint="No unstaged tracked changes."
                defaultOpen={!git.clean && !git.unstaged_diff.startsWith("No ")}
              />
            </div>
          </Panel>

          <Panel
            title="Ignored paths"
            subtitle={`${git.ignored_paths.length} path(s) excluded from AI context`}
            action={<EyeOff className="h-4 w-4 text-zinc-600" aria-hidden />}
          >
            {git.ignored_paths.length === 0 ? (
              <EmptyState title="No ignored paths" description="Git reports nothing excluded." />
            ) : (
              <ul className="grid max-h-[280px] gap-1 overflow-auto font-mono text-[11px] text-zinc-500 sm:grid-cols-2">
                {git.ignored_paths.map((path) => (
                  <li key={path} className="truncate rounded-md border border-white/[0.05] bg-black/20 px-2.5 py-1.5">
                    {path}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      ) : (
        <EmptyState
          title="Git context unavailable"
          description="The bridge could not read the repository. Check that this project is a Git repository."
        />
      )}

    </div>
  );
}
