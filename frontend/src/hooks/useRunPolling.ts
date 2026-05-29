import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { TERMINAL_STATUSES, type RunDetail } from "@/api/types";

/** Adaptive poll interval: faster while judging verdicts stream in. */
function pollInterval(status: RunDetail["status"], elapsedMs: number): number {
  if (status === "judging") return 1_500;
  if (elapsedMs < 30_000) return 2_000;
  if (elapsedMs < 120_000) return 5_000;
  return 10_000;
}

export function useRunPolling(runId: string | undefined) {
  return useQuery<RunDetail>({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data;
      if (!run) return 2_000;
      if (TERMINAL_STATUSES.has(run.status)) return false;
      const createdAt = new Date(run.created_at).getTime();
      return pollInterval(run.status, Date.now() - createdAt);
    },
    refetchIntervalInBackground: true,
  });
}
