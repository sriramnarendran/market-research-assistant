import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "@/api/client";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

function faviconUrl(sourceUrl: string | undefined): string | null {
  if (!sourceUrl) return null;
  try {
    const host = new URL(sourceUrl).hostname;
    return `https://icons.duckduckgo.com/ip3/${host}.ico`;
  } catch {
    return null;
  }
}

function highlightText(text: string, needle: string | undefined): React.ReactNode {
  if (!needle || needle.length < 4) return text;
  const lower = text.toLowerCase();
  const idx = lower.indexOf(needle.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded bg-amber-200/80 px-0.5 text-foreground">
        {text.slice(idx, idx + needle.length)}
      </mark>
      {text.slice(idx + needle.length)}
    </>
  );
}

export function SourceChip({
  sourceId,
  index,
  highlightText: highlight,
}: {
  sourceId: string;
  index: number;
  highlightText?: string;
}) {
  const [open, setOpen] = useState(false);
  const { data: source, isLoading, error } = useQuery({
    queryKey: ["source", sourceId],
    queryFn: () => api.getSource(sourceId),
    enabled: open,
    staleTime: 5 * 60_000,
  });

  const icon = useMemo(() => faviconUrl(source?.url), [source?.url]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-full border border-input bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground transition-colors hover:bg-secondary/80"
      >
        {icon && (
          <img
            src={icon}
            alt=""
            className="h-3.5 w-3.5 rounded-sm"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        )}
        [{index}]
      </button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="flex w-full flex-col overflow-hidden sm:max-w-xl">
          <SheetHeader>
            <SheetTitle className="break-words pr-8">
              {source?.title || "Source"}
            </SheetTitle>
            <SheetDescription className="flex items-center gap-2 break-all">
              {source?.url && (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  {icon && (
                    <img src={icon} alt="" className="h-4 w-4 rounded-sm" />
                  )}
                  {source.url}
                  <ExternalLink className="h-3 w-3 shrink-0" />
                </a>
              )}
            </SheetDescription>
          </SheetHeader>
          <div className="flex-1 overflow-y-auto">
            {isLoading && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading…
              </p>
            )}
            {error && (
              <p className="text-sm text-destructive">
                Error: {error instanceof Error ? error.message : "failed to load"}
              </p>
            )}
            {source && (
              <div className="space-y-3">
                <div className="flex gap-2 text-xs text-muted-foreground">
                  <span>{source.origin}</span>
                  <span>·</span>
                  <span>{Math.round(source.bytes / 1024)} KB</span>
                </div>
                <pre className="whitespace-pre-wrap break-words rounded-md bg-muted p-3 text-xs leading-relaxed">
                  {highlightText(source.fetched_text, highlight)}
                </pre>
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
