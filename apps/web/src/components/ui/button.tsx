import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { Slot } from "radix-ui";
import * as React from "react";

import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex shrink-0 select-none items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium " +
    "transition-colors duration-[var(--dur-fast)] disabled:pointer-events-none disabled:opacity-50 " +
    "[&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground hover:bg-primary-hover",
        secondary: "border border-input bg-surface text-foreground hover:bg-surface-hover",
        ghost: "text-foreground hover:bg-surface-hover",
        soft: "bg-accent-soft text-accent-text hover:bg-accent-soft-hover",
        destructive: "bg-danger-solid text-primary-foreground hover:opacity-90",
        link: "h-auto px-0 text-accent-text underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-[calc(var(--control-h)-0.375rem)] px-2.5 text-[0.8125rem]",
        md: "h-[var(--control-h)] px-3.5 text-[length:var(--text-base)]",
        lg: "h-[calc(var(--control-h)+0.5rem)] px-5 text-base",
        icon: "size-[var(--control-h)]",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    /** Render the child element (for example a Link) with button styles. */
    asChild?: boolean;
    /** Shows a spinner and blocks clicks while an action is running. */
    loading?: boolean;
  };

export function Button({ className, variant, size, asChild, loading, disabled, children, ...props }: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...(asChild ? {} : { type: props.type ?? "button" })}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {loading ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
          {children}
        </>
      )}
    </Comp>
  );
}
