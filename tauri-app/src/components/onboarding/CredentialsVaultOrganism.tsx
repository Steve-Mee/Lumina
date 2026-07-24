import { cn } from "@/lib/utils";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

interface CredentialsVaultOrganismProps {
  /** true when Fabric LINK is green — soft link glow */
  linked?: boolean;
  caption: string;
  className?: string;
}

/**
 * Calm forever-evolving presence (not a spinner).
 * Channel status lives in the panel status strip — not orbiting nodes.
 */
export function CredentialsVaultOrganism({
  linked = false,
  caption,
  className,
}: CredentialsVaultOrganismProps) {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <div
      className={cn(
        "credentials-vault-organism",
        linked && "credentials-vault-organism--linked",
        reducedMotion && "credentials-vault-organism--static",
        className,
      )}
      aria-hidden
    >
      <div className="credentials-vault-organism__void" />
      <div className="credentials-vault-organism__halo" />
      <div className="credentials-vault-organism__ring credentials-vault-organism__ring--outer" />
      <div className="credentials-vault-organism__ring credentials-vault-organism__ring--inner" />
      <div className="credentials-vault-organism__strand credentials-vault-organism__strand--a" />
      <div className="credentials-vault-organism__strand credentials-vault-organism__strand--b" />
      <div className="credentials-vault-organism__core">
        <div className="credentials-vault-organism__core-pulse" />
        <div className="credentials-vault-organism__core-inner" />
      </div>
      {linked ? <div className="credentials-vault-organism__link-ray" /> : null}
      <p className="credentials-vault-organism__caption">{caption}</p>
    </div>
  );
}
