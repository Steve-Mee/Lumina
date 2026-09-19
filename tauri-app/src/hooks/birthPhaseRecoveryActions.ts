import type { BirthRecoveryAction } from "@/components/birth/BirthRecoveryActionBar";
import type { WipeConfirmKind } from "@/store/birthUiStore";

export interface StalledRecoveryActionHandlers {
  openWipeConfirm: (kind: WipeConfirmKind) => void;
  handleReviewGenesisSettings: () => void;
  handleCopyForensicsCommand: () => void;
  handleExpandAndRetryStalledStage: () => void;
  handleResumeStalledStage: () => void;
  handleRetryCurrentStage?: () => void;
  handleAcceptChampion?: () => void;
  setRecoveryDismissed: (dismissed: boolean) => void;
}

export interface StalledRecoveryActionOptions {
  championFreeze?: boolean;
  retryStage?: boolean;
}

/** Build stalled-stage recovery CTA row (exhausted vs expandable ladder). */
export function buildStalledRecoveryActions(
  evolutionExhausted: boolean,
  handlers: StalledRecoveryActionHandlers,
  options?: StalledRecoveryActionOptions,
): BirthRecoveryAction[] {
  const {
    openWipeConfirm,
    handleReviewGenesisSettings,
    handleCopyForensicsCommand,
    handleExpandAndRetryStalledStage,
    handleResumeStalledStage,
    handleRetryCurrentStage,
    handleAcceptChampion,
    setRecoveryDismissed,
  } = handlers;

  if (options?.retryStage) {
    return [
      {
        id: "retry",
        label: "Retry stage",
        loadingLabel: "Resetting stage sample…",
        variant: "primary",
        onClick: () => {
          if (handleRetryCurrentStage) {
            handleRetryCurrentStage();
            return;
          }
          handleResumeStalledStage();
        },
      },
      {
        id: "wipe_full",
        label: "Wipe & restart",
        variant: "outline",
        onClick: () => openWipeConfirm("full"),
      },
      {
        id: "forensics",
        label: "Copy forensics cmd",
        variant: "outline",
        onClick: handleCopyForensicsCommand,
      },
    ];
  }

  if (options?.championFreeze) {
    return [
      {
        id: "accept_champion",
        label: "Accept champion",
        loadingLabel: "Accepting…",
        variant: "primary",
        onClick: () => {
          if (handleAcceptChampion) {
            handleAcceptChampion();
            return;
          }
          handleResumeStalledStage();
        },
      },
      {
        id: "wipe_full",
        label: "Wipe & restart",
        variant: "outline",
        onClick: () => openWipeConfirm("full"),
      },
      {
        id: "forensics",
        label: "Copy forensics cmd",
        variant: "outline",
        onClick: handleCopyForensicsCommand,
      },
    ];
  }

  if (evolutionExhausted) {
    return [
      {
        id: "reset_keep_cache",
        label: "Reset birth (keep tick cache)",
        loadingLabel: "Resetting…",
        variant: "primary",
        onClick: () => openWipeConfirm("reset"),
      },
      {
        id: "genesis",
        label: "Review genesis settings",
        variant: "secondary",
        onClick: handleReviewGenesisSettings,
      },
      {
        id: "wipe_full",
        label: "Full wipe (including tick cache)",
        variant: "outline",
        onClick: () => openWipeConfirm("full"),
      },
      {
        id: "forensics",
        label: "Copy forensics cmd",
        variant: "outline",
        onClick: handleCopyForensicsCommand,
      },
      {
        id: "dismiss",
        label: "Dismiss",
        variant: "ghost",
        onClick: () => setRecoveryDismissed(true),
      },
    ];
  }

  return [
    {
      id: "expand",
      label: "Expand & retry",
      loadingLabel: "Starting…",
      variant: "primary",
      onClick: handleExpandAndRetryStalledStage,
    },
    {
      id: "genesis",
      label: "Review genesis settings",
      variant: "secondary",
      onClick: handleReviewGenesisSettings,
    },
    {
      id: "retry",
      label: "Retry stage",
      variant: "secondary",
      onClick: handleResumeStalledStage,
    },
    {
      id: "forensics",
      label: "Copy forensics cmd",
      variant: "outline",
      onClick: handleCopyForensicsCommand,
    },
    {
      id: "dismiss",
      label: "Dismiss",
      variant: "ghost",
      onClick: () => setRecoveryDismissed(true),
    },
  ];
}
