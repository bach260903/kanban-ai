"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { BoardDetail } from "@/lib/types";
import { useAgentEvents } from "@/lib/ws";
import { Button, Input, Spinner } from "@/components/ui/primitives";
import { AgentTrace } from "./agent-trace";
import { useQueryClient } from "@tanstack/react-query";

interface Message {
  role: "user" | "agent";
  content: string;
  runId?: string;
  trace?: any[];
  result?: any;
  status?: "running" | "done" | "error";
}

const SUGGESTED_VI = [
  "Phân rã mục tiêu triển khai đăng nhập thành các subtask",
  "Board có chỗ nào bị tắc nghẽn không?",
  "Tóm tắt hoạt động gần đây trên board (stand-up)",
  "Tạo task 'Review pull request' ưu tiên cao",
];

interface Props {
  board: BoardDetail;
  open: boolean;
  onClose: () => void;
}

export function ChatPanel({ board, open, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const locale = "vi" as const;
  const scrollRef = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();

  const suggested = SUGGESTED_VI;

  useAgentEvents(activeRunId ? `agent.run.${activeRunId}` : null, (ev) => {
    if (!activeRunId) return;
    setMessages((prev) => {
      const next = [...prev];
      const idx = next.findIndex((m) => m.runId === activeRunId);
      if (idx === -1) return prev;
      const msg = { ...next[idx] };
      const trace = [...(msg.trace || [])];
      if (ev.type === "run.step") {
        trace.push({
          step_index: ev.step_index,
          node: ev.node,
          status: ev.status,
          output_summary: ev.output_summary,
          latency_ms: ev.latency_ms,
        });
        msg.trace = trace;
      } else if (ev.type === "run.tool") {
        trace.push({
          step_index: trace.length,
          node: ev.node || "executor",
          tool: ev.tool,
          args: ev.args,
          status: "finished",
        });
        msg.trace = trace;
      } else if (ev.type === "run.finished") {
        msg.status = ev.status === "error" ? "error" : "done";
        msg.result = ev.result;
        msg.content = renderResult(ev.result);
        qc.invalidateQueries({ queryKey: ["board", board.id] });
        qc.invalidateQueries({ queryKey: ["runs", board.id] });
      } else if (ev.type === "run.error") {
        msg.status = "error";
        msg.content = `Lỗi: ${ev.error}`;
      }
      next[idx] = msg;
      return next;
    });
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim()) return;
    if (isLowSignalPrompt(text)) {
      setMessages((m) => [
        ...m,
        { role: "user", content: text },
        {
          role: "agent",
          content:
            "Yêu cầu còn mơ hồ nên mình chưa gọi AI để tránh lãng phí. Bạn hãy nêu rõ: mục tiêu + tên task/cột + hành động mong muốn (vd: 'Gợi ý người làm task AI ở cột In progress').",
          status: "done",
        },
      ]);
      setInput("");
      return;
    }
    setSubmitting(true);
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    try {
      const taskIndex = buildTaskIndex(board.tasks);
      const run = await api.agentChat({
        board_id: board.id,
        message: text,
        locale,
        context: { task_index: taskIndex },
      });
      setActiveRunId(run.id);
      setMessages((m) => [...m, { role: "agent", runId: run.id, content: "", status: "running", trace: [] }]);
      // Long poll if WS misses (network)
      void pollUntilDone(run.id);
    } catch (e: any) {
      setMessages((m) => [...m, { role: "agent", content: `Lỗi: ${e?.message || "không xác định"}`, status: "error" }]);
    } finally {
      setSubmitting(false);
    }
  }

  async function pollUntilDone(runId: string) {
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      try {
        const detail = await api.getRun(runId);
        if (detail.status === "done" || detail.status === "error") {
          setMessages((prev) => {
            const next = [...prev];
            const idx = next.findIndex((m) => m.runId === runId);
            if (idx >= 0) {
              next[idx] = {
                ...next[idx],
                status: detail.status === "error" ? "error" : "done",
                result: detail.result,
                content: detail.error ? `Lỗi: ${detail.error}` : renderResult(detail.result),
                trace: next[idx].trace?.length ? next[idx].trace : detail.steps.map((s) => ({
                  step_index: s.step_index,
                  node: s.node,
                  status: "finished",
                  output_summary: s.output_summary || undefined,
                  latency_ms: s.latency_ms || undefined,
                })),
              };
            }
            return next;
          });
          qc.invalidateQueries({ queryKey: ["board", board.id] });
          return;
        }
      } catch {}
    }
  }

  return (
    <div
      className={
        "fixed top-0 right-0 h-full w-[420px] max-w-full bg-card border-l border-border shadow-2xl z-40 flex flex-col transition-transform " +
        (open ? "translate-x-0" : "translate-x-full")
      }
    >
      <div className="p-4 border-b border-border flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-medium">Trợ lý AI</h3>
          <p className="text-xs text-muted-foreground">Hỏi đáp và điều phối đa tác tử</p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onClose}
            className="text-xl leading-none px-2 hover:opacity-70"
            aria-label="Đóng"
          >
            ×
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="rounded-md border border-border p-2 bg-secondary/20">
          <p className="text-xs font-medium">Mã task nhanh (từ 0):</p>
          <div className="mt-1 space-y-1 max-h-28 overflow-y-auto">
            {board.tasks.slice(0, 20).map((t, idx) => (
              <p key={t.id} className="text-[11px] text-muted-foreground truncate">
                #{idx} · {t.title}
              </p>
            ))}
          </div>
        </div>
        {messages.length === 0 ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Gợi ý nhanh:
            </p>
            <div className="flex flex-col gap-2">
              {suggested.map((s, i) => (
                <button
                  key={i}
                  onClick={() => send(s)}
                  className="text-left text-xs rounded-md border border-border p-2 hover:bg-accent transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "ml-6" : ""}>
              <div
                className={
                  "rounded-lg p-3 text-sm " +
                  (m.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground")
                }
              >
                {m.role === "agent" && m.trace && m.trace.length > 0 ? (
                  <div className="mb-2">
                    <AgentTrace items={m.trace} running={m.status === "running"} />
                  </div>
                ) : null}
                {m.content ? (
                  <div className="whitespace-pre-wrap">{m.content}</div>
                ) : m.status === "running" ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Spinner /> Đang xử lý...
                  </div>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="p-3 border-t border-border">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Hỏi trợ lý AI..."
            disabled={submitting}
          />
          <Button type="submit" disabled={submitting || !input.trim()}>
            {submitting ? <Spinner /> : null}
            Gửi
          </Button>
        </form>
      </div>
    </div>
  );
}

function isLowSignalPrompt(text: string): boolean {
  const s = (text || "").trim().toLowerCase();
  if (!s) return true;
  if (s.length < 10) return true;
  const useful = ["task", "cột", "board", "gán", "phân", "báo cáo", "monitor", "assignee", "deadline", "hạn", "ai"];
  return !useful.some((k) => s.includes(k));
}

function buildTaskIndex(tasks: Array<{ id: string; title: string }>): Record<string, string> {
  const index: Record<string, string> = {};
  tasks.forEach((t, i) => {
    index[String(i)] = t.id;
  });
  return index;
}

function renderResult(result: any): string {
  if (!result) return "(không có kết quả)";
  if (typeof result.message === "string" && result.message.trim()) return result.message;
  if (result.report_md) return result.report_md;
  if (result.summary) {
    const alerts = (result.alerts || [])
      .map((a: any) => `• [${a.severity}] ${a.kind}: ${a.evidence}`)
      .join("\n");
    return `${result.summary}\n${alerts}`.trim();
  }
  if (result.plan) {
    const subs = (result.plan.subtasks || [])
      .map((s: any, i: number) => `${i + 1}. ${s.title} (${s.est_hours ?? "?"}h)`)
      .join("\n");
    return `Kế hoạch:\n${subs}`;
  }
  if (result.assignments?.suggestions?.length) {
    const lines = result.assignments.suggestions
      .map((a: any) => `• ${a.user_id.slice(0, 8)} — điểm ${a.score} — ${a.reason}`)
      .join("\n");
    return `Ứng viên phù hợp:\n${lines}`;
  }
  if (result.executor) {
    const calls = (result.executor.tool_calls || [])
      .map((c: any) => `• ${c.tool}(${JSON.stringify(c.args).slice(0, 120)}) → ${c.ok ? "thành công" : "lỗi"}`)
      .join("\n");
    return `${result.executor.final}\n${calls}`.trim();
  }
  return JSON.stringify(result, null, 2).slice(0, 1500);
}
