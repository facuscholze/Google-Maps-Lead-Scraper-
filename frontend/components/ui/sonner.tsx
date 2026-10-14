"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner } from "sonner";

/**
 * Toasts globales (sonner) enroscados al tema innblock.
 * Uso: `import { toast } from "sonner"; toast.success("Listo")`.
 */
const Toaster = ({ ...props }: React.ComponentProps<typeof Sonner>) => {
  const { resolvedTheme } = useTheme();
  return (
    <Sonner
      theme={(resolvedTheme as "dark" | "light") ?? "dark"}
      position="top-center"
      gap={8}
      toastOptions={{
        classNames: {
          toast:
            "group toast !rounded-lg !border !border-border !bg-popover !text-popover-foreground !shadow-lift !font-sans",
          description: "!text-muted-foreground",
          actionButton: "!bg-primary !text-primary-foreground !rounded-md",
          cancelButton: "!bg-secondary !text-secondary-foreground !rounded-md",
          success: "[&_[data-icon]]:!text-emerald-500",
          error: "[&_[data-icon]]:!text-destructive",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
