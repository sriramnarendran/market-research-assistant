import type { RunStatus } from "@/api/types";
import { statusLabel, statusVariant } from "@/lib/runStatus";
import { Badge } from "@/components/ui/badge";

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return <Badge variant={statusVariant(status)}>{statusLabel(status)}</Badge>;
}
