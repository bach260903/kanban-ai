"use client";

import { Badge, Spinner } from "@/components/ui/primitives";

const NODE_ICON: Record<string, string> = {
  orchestrator: "🧭",
  planner: "🧱",
  assigner: "👤",
  monitor: "🔭",
  reporter: "📝",
  executor: "⚙️",
};

interface TraceItem {
  step_index: number;
  node: string;
  status?: "started" | "finished";
  output_summary?: string;
  latency_ms?: number;
  tool?: string;
  args?: any;
  result?: any;
  error?: string;
}

export function AgentTrace({ items, running }: { items: TraceItem[]; running?: boolean }) {
  if (!items.length && !running) return null;
  return (
    <ol className="space-y-1.5">
      {items.map((it, i) => (
        <li key={i} className="text-xs flex items-start gap-2">
          <span className="mt-0.5">{NODE_ICON[it.node] || "•"}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium capitalize">{it.tool ? `${it.node} → ${it.tool}` : it.node}</span>
              {it.status === "started" ? (
                <Badge variant="outline" className="text-[10px]">đang chạy</Badge>
              ) : it.status === "finished" ? (
                <Badge variant="success" className="text-[10px]">
                  {it.latency_ms ? `${it.latency_ms}ms` : "xong"}
                </Badge>
              ) : null}
              {it.error ? <Badge variant="destructive" className="text-[10px]">lỗi</Badge> : null}
            </div>
            {it.output_summary && (
              <p className="text-muted-foreground mt-0.5 truncate">{it.output_summary}</p>
            )}
            {it.tool && it.args ? (
              <p className="text-muted-foreground mt-0.5 truncate">
                tham số: {JSON.stringify(it.args).slice(0, 200)}
              </p>
            ) : null}
          </div>
        </li>
      ))}
      {running ? (
        <li className="flex items-center gap-2 text-xs text-muted-foreground">
          <Spinner /> đang xử lý...
        </li>
      ) : null}
    </ol>
  );
}
