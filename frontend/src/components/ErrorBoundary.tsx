import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("RubberDucky UI error", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center p-6">
          <div className="glass-panel max-w-md p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-danger/25 bg-danger/10 text-danger">
              <AlertTriangle className="h-5 w-5" aria-hidden />
            </div>
            <h1 className="mt-4 text-lg font-semibold text-zinc-100">The interface hit an error</h1>
            <p className="mt-2 text-xs leading-relaxed text-zinc-500">
              The Python bridge is unaffected. Reload the window to reconnect.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="focus-ring mt-5 inline-flex h-10 items-center rounded-xl bg-duck-gradient px-5 text-sm font-semibold text-ink-950"
            >
              Reload interface
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
