import { cn } from "@/lib/utils";

/** Fixed decorative mesh + dot grid behind page content. */
export function AppBackground({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("app-background pointer-events-none fixed inset-0 -z-10", className)}>
      <div className="app-background__mesh" />
      <div className="app-background__grid" />
    </div>
  );
}
