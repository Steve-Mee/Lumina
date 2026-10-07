import { RotateCcw } from "lucide-react";
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
}

export class PanelErrorBoundary extends Component<
  PanelErrorBoundaryProps,
  PanelErrorBoundaryState
> {
  state: PanelErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): PanelErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[${this.props.panelName}] panel error`, error, info);
  }

  private handleRetry = (): void => {
    this.props.onRetry?.();
    this.setState({ hasError: false });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          className={cn(
            "flex h-full min-h-0 flex-col items-center justify-center gap-3 rounded-lg px-4 py-6 text-center",
            "border border-[color-mix(in_srgb,var(--lumina-cyan)_16%,transparent)]",
            "bg-[color-mix(in_srgb,var(--lumina-void)_70%,transparent)]",
            this.props.className,
          )}
          role="alert"
        >
          <p className="risk-envelope-panel__toolbar-title">{this.props.panelName}</p>
          <p className="max-w-xs font-mono text-[11px] leading-relaxed text-white/55">
            This organ is silent. Retry does not invent a graph or a decision chain.
          </p>
          <Button size="xs" variant="command-ghost" onClick={this.handleRetry}>
            <RotateCcw data-icon="inline-start" />
            Retry
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
