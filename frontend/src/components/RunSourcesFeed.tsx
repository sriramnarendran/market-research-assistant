import { AlertTriangle, ExternalLink, Globe, Loader2, Rss } from "lucide-react";

import type { SourceSummary, UrlFetchFailure } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function faviconUrl(sourceUrl: string): string | null {
  try {
    const host = new URL(sourceUrl).hostname;
    return `https://icons.duckduckgo.com/ip3/${host}.ico`;
  } catch {
    return null;
  }
}

function displayTitle(source: SourceSummary): string {
  if (source.title?.trim()) return source.title.trim();
  try {
    return new URL(source.url).hostname;
  } catch {
    return source.url;
  }
}

function originLabel(origin: SourceSummary["origin"]): string {
  return origin === "url_path" ? "Your URL" : "Web search";
}

export function RunSourcesFeed({
  sources,
  fetchFailures = [],
  isLoading,
  className,
}: {
  sources: SourceSummary[];
  fetchFailures?: UrlFetchFailure[];
  isLoading?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Rss className="h-4 w-4" />
          </span>
          <div>
            <h3 className="text-sm font-medium text-foreground">
              Sources collected
              {sources.length > 0 && (
                <span className="ml-1.5 tabular-nums text-muted-foreground">({sources.length})</span>
              )}
            </h3>
            <p className="text-xs text-muted-foreground">Updates as pages are fetched</p>
          </div>
        </div>
        {isLoading && sources.length === 0 && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      {fetchFailures.length > 0 && (
        <ul className="space-y-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-2">
          {fetchFailures.map((failure) => (
            <li
              key={failure.url}
              className="flex items-start gap-3 rounded-lg border border-amber-500/20 bg-card px-3 py-2.5"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate text-sm font-medium text-foreground">Could not fetch</p>
                  <Badge variant="outline" className="shrink-0 border-amber-500/40 text-[10px] text-amber-800">
                    Your URL
                  </Badge>
                </div>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{failure.url}</p>
                <p className="mt-1 text-xs text-amber-800">{failure.error}</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {sources.length === 0 && fetchFailures.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-muted/20 px-4 py-8 text-center">
          <Globe className="mx-auto h-8 w-8 text-muted-foreground/50" />
          <p className="mt-3 text-sm text-muted-foreground">
            Sources will appear here as we fetch your URLs and search the web.
          </p>
        </div>
      ) : (
        <ul className="max-h-72 space-y-2 overflow-y-auto rounded-xl border bg-muted/10 p-2 pr-1">
          {sources.map((source, index) => {
            const icon = faviconUrl(source.url);
            const isNew = index === sources.length - 1;
            return (
              <li
                key={source.id}
                className={cn(
                  "flex items-start gap-3 rounded-lg border bg-card px-3 py-2.5 shadow-sm transition-colors hover:border-primary/20",
                  isNew && "animate-in fade-in slide-in-from-bottom-1 duration-300",
                )}
              >
                {icon ? (
                  <img
                    src={icon}
                    alt=""
                    className="mt-0.5 h-4 w-4 shrink-0 rounded-sm"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : (
                  <Globe className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-medium text-foreground">{displayTitle(source)}</p>
                    <Badge variant="secondary" className="shrink-0 text-[10px]">
                      {originLabel(source.origin)}
                    </Badge>
                    {source.topic_match && (
                      <Badge variant="outline" className="shrink-0 text-[10px]">
                        {source.topic_match}
                      </Badge>
                    )}
                  </div>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-0.5 inline-flex max-w-full items-center gap-1 truncate text-xs text-primary hover:underline"
                  >
                    {source.url}
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
