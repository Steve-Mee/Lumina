import type { ComponentProps } from "react";

import { Button, type buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { VariantProps } from "class-variance-authority";

type CommandVariant = "command-primary" | "command-ghost";

interface CommandButtonProps
  extends Omit<ComponentProps<typeof Button>, "variant">,
    VariantProps<typeof buttonVariants> {
  variant?: CommandVariant;
  intent?: "default" | "danger";
}

/** Cockpit-only button: command-primary (fill) or command-ghost (edge glow). */
export function CommandButton({
  variant = "command-ghost",
  intent = "default",
  className,
  ...props
}: CommandButtonProps) {
  return (
    <Button
      variant={variant}
      className={cn(className)}
      data-intent={intent === "danger" ? "danger" : undefined}
      {...props}
    />
  );
}
