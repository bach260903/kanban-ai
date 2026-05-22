"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { BoardDetail } from "@/lib/types";
import { Button, Dialog, Label, Spinner, Textarea } from "@/components/ui/primitives";
import { useQueryClient } from "@tanstack/react-query";

export function BreakdownModal({
  board,
  open,
  onClose,
}: {
  board: BoardDetail;
  open: boolean;
  onClose: () => void;
}) {
  const [goal, setGoal] = useState("");
  const [columnId, setColumnId] = useState(board.columns[0]?.id || "");
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setPlan(null);
    try {
      const run = await api.agentBreakdown({ board_id: board.id, goal_text: goal, target_column_id: columnId || undefined });
      // poll
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 1200));
        const detail = await api.getRun(run.id);
        if (detail.status === "done") {
          setPlan(detail.result?.plan);
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
      setBusy(false);
    }
  }

  async function commit() {
    if (!plan) return;
    setBusy(true);
    try {
      for (const s of plan.subtasks || []) {
        await api.createTask(board.id, {
          column_id: columnId,
          title: s.title,
          description: s.description || "",
          priority: "medium",
          est_hours: s.est_hours,
          tags: s.required_skills || [],
        });
      }
      qc.invalidateQueries({ queryKey: ["board", board.id] });
      onClose();
      setPlan(null);
      setGoal("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="✨ AI phân rã công việc">
      {!plan ? (
        <form onSubmit={generate} className="space-y-4">
          <div className="space-y-2">
            <Label>Mục tiêu / Epic</Label>
            <Textarea
              required
              rows={3}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Triển khai luồng đăng nhập email + password với JWT"
            />
          </div>
          <div className="space-y-2">
            <Label>Cột đích</Label>
            <select
              className="h-9 w-full rounded-md border border-border bg-transparent px-3 text-sm"
              value={columnId}
              onChange={(e) => setColumnId(e.target.value)}
            >
              {board.columns.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" type="button" onClick={onClose}>Hủy</Button>
            <Button type="submit" disabled={busy || !goal.trim()}>
              {busy ? <Spinner /> : null}
              Tạo kế hoạch
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">{plan.notes || "Các công việc đề xuất:"}</p>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {(plan.subtasks || []).map((s: any, i: number) => (
              <div key={i} className="border border-border rounded-md p-3">
                <p className="text-sm font-medium">{s.title}</p>
                {s.description && <p className="text-xs text-muted-foreground mt-1">{s.description}</p>}
                <div className="text-[10px] text-muted-foreground mt-2 flex gap-3">
                  <span>{s.est_hours ?? "?"}h</span>
                  <span>{(s.required_skills || []).join(", ")}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setPlan(null)}>Bỏ</Button>
            <Button onClick={commit} disabled={busy}>
              {busy ? <Spinner /> : null}
              Thêm {plan.subtasks?.length || 0} công việc vào bảng
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
