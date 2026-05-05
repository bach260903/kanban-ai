"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUsers } from "@/lib/queries";
import { Button, Dialog, Spinner } from "@/components/ui/primitives";
import { useQueryClient } from "@tanstack/react-query";

export function SuggestAssigneeDialog({
  boardId,
  taskId,
  onClose,
}: {
  boardId: string;
  taskId: string | null;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { data: users = [] } = useUsers();
  const qc = useQueryClient();
  const open = !!taskId;

  useEffect(() => {
    if (!taskId) return;
    let cancelled = false;
    setBusy(true);
    setSuggestions([]);
    setError(null);
    (async () => {
      try {
        const run = await api.agentSuggestAssignee({ board_id: boardId, task_id: taskId });
        for (let i = 0; i < 30; i++) {
          await new Promise((r) => setTimeout(r, 1200));
          if (cancelled) return;
          const detail = await api.getRun(run.id);
          if (detail.status === "done") {
            setSuggestions(detail.result?.assignments?.suggestions || []);
            break;
          }
          if (detail.status === "error") {
            setError(detail.error || "Thất bại");
            break;
          }
        }
      } catch (e: any) {
        setError(e?.message || "Thất bại");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [taskId, boardId]);

  async function pick(userId: string) {
    if (!taskId) return;
    await api.assignUser(boardId, taskId, userId);
    qc.invalidateQueries({ queryKey: ["board", boardId] });
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose} title="✨ Gợi ý người phụ trách">
      {busy ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> AI đang so sánh kỹ năng và khối lượng công việc...
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : suggestions.length === 0 ? (
        <p className="text-sm text-muted-foreground">Không có gợi ý phù hợp.</p>
      ) : (
        <div className="space-y-2">
          {[...suggestions]
            .sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
            .map((s, i) => {
            const user = users.find((u) => u.id === s.user_id);
            const pct = Math.max(1, Math.min(99, Math.round(Number(s.score || 0) * 100)));
            return (
              <div key={i} className="rounded-md border border-border p-3 flex items-start gap-3">
                <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center">
                  {(user?.display_name || s.user_id).slice(0, 1).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{user?.display_name || s.user_id.slice(0, 8)}</p>
                    <span className="text-xs text-muted-foreground">Mức phù hợp {pct}%</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{s.reason}</p>
                  <Button size="sm" className="mt-2" onClick={() => pick(s.user_id)}>
                    Gán ngay
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Dialog>
  );
}
