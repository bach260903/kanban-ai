"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Badge, Button, Card, Spinner } from "@/components/ui/primitives";

export function MonitorBanner({ boardId }: { boardId: string }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await api.agentMonitor({ board_id: boardId });
      for (let i = 0; i < 30; i++) {
        await new Promise((res) => setTimeout(res, 1200));
        const d = await api.getRun(r.id);
        if (d.status === "done") {
          setResult(d.result);
          break;
        }
        if (d.status === "error") {
          setError(d.error || "Thất bại");
          break;
        }
      }
    } catch (e: any) {
      setError(e?.message || "Thất bại");
    } finally {
      setRunning(false);
    }
  }

  if (!result && !running && !error) {
    return (
      <Button variant="outline" size="sm" onClick={run}>
        🔭 Chạy giám sát
      </Button>
    );
  }

  return (
    <Card className="p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">Giám sát</p>
        <div className="flex items-center gap-2">
          {running ? <Spinner /> : null}
          <Button size="sm" variant="ghost" onClick={() => { setResult(null); setError(null); }}>
            Đặt lại
          </Button>
          <Button size="sm" variant="outline" onClick={run}>
            Chạy lại
          </Button>
        </div>
      </div>
      {error ? (
        <p className="text-sm text-destructive mt-2">{error}</p>
      ) : result ? (
        <div className="mt-2 space-y-2">
          {result.summary && <p className="text-sm">{result.summary}</p>}
          {(result.alerts || []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Không phát hiện điểm nghẽn.</p>
          ) : (
            <ul className="space-y-1.5">
              {result.alerts.map((a: any, i: number) => (
                <li key={i} className="text-xs flex items-start gap-2">
                  <Badge
                    variant={a.severity === "critical" ? "destructive" : a.severity === "warn" ? "warning" : "secondary"}
                    className="text-[10px]"
                  >
                    {a.severity}
                  </Badge>
                  <div className="flex-1">
                    <p className="font-medium">{a.kind}</p>
                    <p className="text-muted-foreground">{a.evidence}</p>
                    {a.suggestion && <p className="text-muted-foreground italic">→ {a.suggestion}</p>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </Card>
  );
}
