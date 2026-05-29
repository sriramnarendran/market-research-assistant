import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { SourceSummary } from "@/api/types";

/** Poll sources while a run is in progress — same cadence as run status. */
function pollInterval(elapsedMs: number): number {
  if (elapsedMs < 30_000) return 2_000;
  if (elapsedMs < 120_000) return 5_000;
  return 10_000;
}

export function useRunSourcesPolling(
  runId: string | undefined,
  enabled: boolean,
  runCreatedAt?: string,
) {
  return useQuery<SourceSummary[]>({
    queryKey: ["run", runId, "sources"],
    queryFn: () => api.listRunSources(runId!),
    enabled: Boolean(runId) && enabled,
    refetchInterval: () => {
      if (!enabled || !runCreatedAt) return false;
      const createdAt = new Date(runCreatedAt).getTime();
      return pollInterval(Date.now() - createdAt);
    },
    refetchIntervalInBackground: true,
  });
}
