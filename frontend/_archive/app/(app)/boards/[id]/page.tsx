"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useBoard, useCreateTask } from "@/lib/queries";
import type { Task } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { Kanban } from "@/components/board/kanban";
import { TaskModal } from "@/components/board/task-modal";
import { ChatPanel } from "@/components/ai/chat-panel";
import { BreakdownModal } from "@/components/ai/breakdown-modal";
import { SuggestAssigneeDialog } from "@/components/ai/suggest-assignee";
import { MonitorBanner } from "@/components/ai/monitor-banner";
import { ReportModal } from "@/components/ai/report-modal";
import { Button, Dialog, Input, Label, Spinner, Textarea } from "@/components/ui/primitives";

export default function BoardPage() {
  const params = useParams<{ id: string }>();
  const boardId = params.id;
  const { data: board, isLoading } = useBoard(boardId);
  const [openTask, setOpenTask] = useState<Task | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [breakdownOpen, setBreakdownOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [suggestForTask, setSuggestForTask] = useState<string | null>(null);
  const [membersOpen, setMembersOpen] = useState(false);
  const [memberUid, setMemberUid] = useState("");
  const [memberBusy, setMemberBusy] = useState(false);
  const [memberError, setMemberError] = useState<string | null>(null);
  const [addColumn, setAddColumn] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [assignNotices, setAssignNotices] = useState<Array<{ taskId: string; title: string }>>([]);
  const createTask = useCreateTask(boardId);
  const me = useAuth((s) => s.user);
  const prevMineRef = useRef<Set<string>>(new Set());
  const hydratedRef = useRef(false);

  async function submitNewTask(e: React.FormEvent) {
    e.preventDefault();
    if (!addColumn) return;
    await createTask.mutateAsync({ column_id: addColumn, title: newTitle, description: newDesc });
    setAddColumn(null);
    setNewTitle("");
    setNewDesc("");
  }

  async function addMemberByUid(e: React.FormEvent) {
    e.preventDefault();
    if (!memberUid.trim()) return;
    setMemberBusy(true);
    setMemberError(null);
    try {
      await api.addBoardMember(boardId, memberUid.trim());
      setMemberUid("");
      window.location.reload();
    } catch (err: any) {
      const detail = err?.detail?.detail || err?.message || "";
      if (typeof detail === "string" && detail.toLowerCase().includes("user not found")) {
        setMemberError("Không có người dùng với UID này.");
      } else if (typeof detail === "string" && detail.toLowerCase().includes("uuid")) {
        setMemberError("UID không hợp lệ.");
      } else {
        setMemberError("Không thể thêm thành viên. Vui lòng kiểm tra lại UID.");
      }
    } finally {
      setMemberBusy(false);
    }
  }

  async function removeMember(userId: string) {
    setMemberBusy(true);
    try {
      await api.removeBoardMember(boardId, userId);
      window.location.reload();
    } finally {
      setMemberBusy(false);
    }
  }

  useEffect(() => {
    if (!board || !me?.id) return;
    const mineNow = new Set(
      board.tasks.filter((t) => t.assignees.some((a) => a.user_id === me.id)).map((t) => t.id),
    );
    if (!hydratedRef.current) {
      prevMineRef.current = mineNow;
      hydratedRef.current = true;
      return;
    }
    const newlyAssigned = board.tasks.filter((t) => mineNow.has(t.id) && !prevMineRef.current.has(t.id));
    if (newlyAssigned.length) {
      setAssignNotices((prev) => [
        ...newlyAssigned.map((t) => ({ taskId: t.id, title: t.title })),
        ...prev,
      ].slice(0, 5));
    }
    prevMineRef.current = mineNow;
  }, [board, me?.id]);

  if (isLoading || !board) {
    return (
      <div className="p-6 flex items-center gap-2 text-muted-foreground">
        <Spinner /> Đang tải bảng...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="border-b border-border px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Link href="/boards" className="text-sm text-muted-foreground hover:text-foreground">← Danh sách bảng</Link>
          <h1 className="font-semibold truncate">{board.title}</h1>
          <span className="text-xs text-muted-foreground">
            {board.tasks.length} công việc · {board.columns.length} cột
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => setMembersOpen(true)}>👥 Thành viên</Button>
          <Button variant="outline" size="sm" onClick={() => setBreakdownOpen(true)}>✨ Phân rã việc</Button>
          <Button variant="outline" size="sm" onClick={() => setReportOpen(true)}>📝 Báo cáo</Button>
          <Button variant="default" size="sm" onClick={() => setChatOpen(true)}>💬 Trợ lý AI</Button>
        </div>
      </header>

      <div className="px-6 pt-3">
        {assignNotices.length ? (
          <div className="mb-3 space-y-2">
            {assignNotices.map((n) => (
              <div
                key={n.taskId}
                className="flex items-center justify-between rounded-md border border-emerald-400/60 bg-emerald-50 px-3 py-2 text-sm dark:bg-emerald-900/20"
              >
                <p>
                  🔔 Bạn vừa được giao việc: <span className="font-medium">{n.title}</span>
                </p>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setAssignNotices((prev) => prev.filter((x) => x.taskId !== n.taskId))}
                >
                  Đóng
                </Button>
              </div>
            ))}
          </div>
        ) : null}
        <MonitorBanner boardId={boardId} />
      </div>

      <div className="flex-1 px-6 pb-6 overflow-hidden">
        <div className="h-full overflow-x-auto">
          <Kanban
            board={board}
            currentUserId={me?.id}
            onTaskClick={(t) => setOpenTask(t)}
            onAddTask={(colId) => setAddColumn(colId)}
          />
        </div>
      </div>

      <TaskModal
        board={board}
        task={openTask}
        onClose={() => setOpenTask(null)}
        onSuggestAssignee={(taskId) => {
          setOpenTask(null);
          setSuggestForTask(taskId);
        }}
      />

      <ChatPanel board={board} open={chatOpen} onClose={() => setChatOpen(false)} />

      <BreakdownModal board={board} open={breakdownOpen} onClose={() => setBreakdownOpen(false)} />

      <ReportModal boardId={boardId} open={reportOpen} onClose={() => setReportOpen(false)} />

      <SuggestAssigneeDialog
        boardId={boardId}
        taskId={suggestForTask}
        onClose={() => setSuggestForTask(null)}
      />

      <Dialog open={!!addColumn} onClose={() => setAddColumn(null)} title="Thêm công việc mới">
        <form onSubmit={submitNewTask} className="space-y-3">
          <div className="space-y-2">
            <Label>Tiêu đề</Label>
            <Input required value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Triển khai /auth/login" />
          </div>
          <div className="space-y-2">
            <Label>Mô tả (tùy chọn)</Label>
            <Textarea rows={3} value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setAddColumn(null)}>Hủy</Button>
            <Button type="submit" disabled={createTask.isPending}>
              {createTask.isPending ? <Spinner /> : null}
              Thêm công việc
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={membersOpen} onClose={() => setMembersOpen(false)} title="Thành viên dự án">
        <form onSubmit={addMemberByUid} className="space-y-3">
          <Label>Thêm thành viên bằng UID</Label>
          <div className="flex gap-2">
            <Input value={memberUid} onChange={(e) => setMemberUid(e.target.value)} placeholder="Dán UID người dùng..." />
            <Button type="submit" disabled={memberBusy || !memberUid.trim()}>
              {memberBusy ? <Spinner /> : null}
              Thêm
            </Button>
          </div>
          {memberError ? <p className="text-sm text-destructive">{memberError}</p> : null}
        </form>
        <div className="mt-4 space-y-2">
          <p className="text-sm text-muted-foreground">Danh sách người phụ trách khả dụng:</p>
          {board.members.map((m, idx) => (
            <div key={m.user_id} className="flex items-center justify-between rounded-md border border-border p-2">
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">#{idx} · {m.display_name}</p>
                <p className="text-xs text-muted-foreground truncate">{m.email}</p>
                <p className="text-[10px] text-muted-foreground">UID: {m.user_id}</p>
              </div>
              {m.user_id !== board.owner_id ? (
                <Button size="sm" variant="ghost" onClick={() => removeMember(m.user_id)} disabled={memberBusy}>Xóa</Button>
              ) : (
                <span className="text-xs text-muted-foreground">Chủ dự án</span>
              )}
            </div>
          ))}
        </div>
      </Dialog>
    </div>
  );
}
