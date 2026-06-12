import { AlertTriangle, RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  realOverlayBodyClass,
  realOverlayTitleClass,
} from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  hasError: boolean;
  message: string | null;
}

export class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { hasError: false, message: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[LUMINA Core] fatal app error", error, info);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  private handleRetry = (): void => {
    this.setState({ hasError: false, message: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-[var(--lumina-void)] px-6 text-center">
          <AlertTriangle className="size-10 text-amber-400" aria-hidden />
          <div className="font-mono">
            <p className={realOverlayTitleClass()}>
              LUMINA Command Deck encountered an error
            </p>
            {import.meta.env.DEV && this.state.message ? (
              <p className={cn("mt-2 max-w-md text-xs", realOverlayBodyClass())}>
                {this.state.message}
              </p>
            ) : null}
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={this.handleRetry}>
              Try again
            </Button>
            <Button size="sm" onClick={this.handleReload}>
              <RotateCcw data-icon="inline-start" />
              Reload
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
