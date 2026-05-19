import { AlertTriangle, RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PanelErrorBoundaryProps {
  panelName: string;
  className?: string;
  children: ReactNode;
  onRetry?: () => void;
}

interface PanelErrorBoundaryState {
  hasError: boolean;
  message: string | null;
}

export class PanelErrorBoundary extends Component<
  PanelErrorBoundaryProps,
  PanelErrorBoundaryState
> {
  state: PanelErrorBoundaryState = { hasError: false, message: null };

  static getDerivedStateFromError(error: Error): PanelErrorBoundaryState {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[${this.props.panelName}] panel error`, error, info);
  }

  private handleRetry = (): void => {
    this.props.onRetry?.();
    this.setState({ hasError: false, message: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          className={cn(
            "flex h-full min-h-[120px] flex-col items-center justify-center gap-3 rounded-lg border border-red-500/25 bg-red-950/20 p-4 text-center",
            this.props.className,
          )}
          role="alert"
        >
          <AlertTriangle className="size-5 text-red-400" aria-hidden />
          <div className="font-mono text-[11px]">
            <p className="tracking-wide text-red-200">{this.props.panelName} unavailable</p>
            {import.meta.env.DEV && this.state.message ? (
              <p className="mt-1 max-w-xs truncate text-[10px] text-red-200/60">
                {this.state.message}
              </p>
            ) : null}
          </div>
          <Button size="xs" variant="outline" onClick={this.handleRetry}>
            <RotateCcw data-icon="inline-start" />
            Retry
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
