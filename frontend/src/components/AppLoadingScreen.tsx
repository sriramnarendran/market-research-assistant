import { Loader2 } from "lucide-react";

import { AppBackground } from "@/components/AppBackground";

export function AppLoadingScreen({ message = "Loading…" }: { message?: string }) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      <AppBackground />
      <div className="relative flex h-12 w-12 items-center justify-center rounded-xl bg-card/80 text-primary shadow-sm ring-1 ring-border/60 backdrop-blur-sm">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
      <p className="relative text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
