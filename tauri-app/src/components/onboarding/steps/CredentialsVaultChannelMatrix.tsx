/** Col 2 — channel matrix + seal readiness (Vault mission layout). */
import type {
  ChannelCardModel,
  SealReadiness,
  VaultChannelId,
} from "@/components/onboarding/steps/credentialsVaultState";
import { cn } from "@/lib/utils";

export type { ChannelCardModel };

export function CredentialsVaultChannelMatrix({
  channels,
  selected,
  onSelect,
  readiness,
  className,
}: {
  channels: ChannelCardModel[];
  selected: VaultChannelId;
  onSelect: (id: VaultChannelId) => void;
  readiness: SealReadiness;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "credentials-vault-matrix lumina-glass lumina-glass--overlay",
        className,
      )}
      aria-label="Vault channels"
    >
      <header className="credentials-vault-matrix__toolbar">
        <p className="credentials-vault-matrix__title">Channels</p>
        <p className="credentials-vault-matrix__subtitle">
          Select a channel · green ready · amber fill · red blocked
        </p>
      </header>

      <div className="credentials-vault-matrix__list" role="listbox" aria-label="Channel list">
        {channels.map((ch) => {
          const active = selected === ch.id;
          return (
            <button
              key={ch.id}
              type="button"
              role="option"
              aria-selected={active}
              title={ch.tip}
              className="credentials-vault-channel-card"
              data-state={ch.state === "idle" ? undefined : ch.state}
              data-active={active ? "true" : "false"}
              onClick={() => onSelect(ch.id)}
            >
              <span className="credentials-vault-channel-card__head">
                <span className="credentials-vault-channel-card__dot" aria-hidden />
                <span className="credentials-vault-channel-card__label">{ch.label}</span>
              </span>
              <p className="credentials-vault-channel-card__summary" title={ch.summary}>
                {ch.summary}
              </p>
            </button>
          );
        })}
      </div>

      <div
        className="credentials-vault-matrix__readiness"
        data-state={readiness.state === "idle" ? undefined : readiness.state}
        role="status"
      >
        <p className="credentials-vault-matrix__readiness-title">{readiness.title}</p>
        <p className="credentials-vault-matrix__readiness-body">{readiness.body}</p>
      </div>
    </section>
  );
}
