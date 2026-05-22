"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button, Dialog, Spinner } from "@/components/ui/primitives";

export function ReportModal({
  boardId,
  open,
  onClose,
}: {
  boardId: string;
  open: boolean;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const run = await api.agentReport({ board_id: boardId });
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 1200));
        const d = await api.getRun(run.id);
        if (d.status === "done") {
          setReport(d.result?.report_md || "(trống)");
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
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="📝 Báo cáo hằng ngày">
      {!report && !busy && !error ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Tạo bản tóm tắt nhanh từ hoạt động gần đây, việc đang làm và rủi ro hiện tại.
          </p>
          <div className="flex justify-end">
            <Button onClick={generate}>Tạo báo cáo</Button>
          </div>
        </div>
      ) : busy ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> AI đang tổng hợp hoạt động...
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        <div className="space-y-3">
          <div className="bg-secondary/40 rounded-md p-3 max-h-80 overflow-y-auto">
            <ReportPreview report={report || ""} />
          </div>
          <div className="flex justify-between">
            <Button variant="outline" onClick={generate} disabled={busy}>Chạy lại</Button>
            <Button variant="ghost" onClick={onClose}>Đóng</Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

function ReportPreview({ report }: { report: string }) {
  const lines = report.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  return (
    <div className="space-y-2">
      {lines.map((line, idx) => {
        const plain = line.replace(/^[-*]\s+/, "").replace(/^#+\s*/, "");
        if (line.startsWith("#")) {
          return <h4 key={idx} className="text-sm font-semibold">{plain}</h4>;
        }
        if (line.startsWith("-") || line.startsWith("*")) {
          return (
            <div key={idx} className="rounded border border-border bg-background px-2 py-1 text-sm">
              {plain}
            </div>
          );
        }
        return <p key={idx} className="text-sm">{plain}</p>;
      })}
    </div>
  );
}
