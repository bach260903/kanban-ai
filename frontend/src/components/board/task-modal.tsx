"use client";

import { useEffect, useState } from "react";
import type { BoardDetail, Task } from "@/lib/types";
import { api } from "@/lib/api";
import { useComments, useUpdateTask, useDeleteTask } from "@/lib/queries";
import { Button, Dialog, Input, Label, Spinner, Textarea } from "@/components/ui/primitives";
import { useQueryClient } from "@tanstack/react-query";

interface Props {
  board: BoardDetail;
  task: Task | null;
  onClose: () => void;
  onSuggestAssignee: (taskId: string) => void;
}

const PRIORITIES = ["low", "medium", "high", "urgent"];
const PRIORITY_LABEL: Record<string, string> = {
  low: "Thấp",
  medium: "Trung bình",
  high: "Cao",
  urgent: "Khẩn cấp",
};

export function TaskModal({ board, task, onClose, onSuggestAssignee }: Props) {
  const open = !!task;
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [columnId, setColumnId] = useState("");
  const [estHours, setEstHours] = useState("");
  const [tags, setTags] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  const { data: comments = [] } = useComments(board.id, task?.id ?? null);
  const updateTask = useUpdateTask(board.id);
  const deleteTask = useDeleteTask(board.id);
  const qc = useQueryClient();

  useEffect(() => {
    if (!task) return;
    setTitle(task.title);
    setDescription(task.description || "");
    setPriority(task.priority);
    setColumnId(task.column_id);
    setEstHours(task.est_hours ? String(task.est_hours) : "");
    setTags((task.tags || []).join(", "));
    setDueAt(task.due_at ? task.due_at.slice(0, 16) : "");
  }, [task]);

  async function save() {
    if (!task) return;
    setBusy(true);
    try {
      await updateTask.mutateAsync({
        taskId: task.id,
        body: {
          title,
          description,
          priority,
          column_id: columnId,
          est_hours: estHours ? Number(estHours) : null,
          tags: tags
            .split(",")
            .map((t) => t.trim().toLowerCase())
            .filter(Boolean),
          due_at: dueAt ? new Date(dueAt).toISOString() : null,
        },
      });
      onClose();
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!task) return;
    if (!confirm("Bạn có chắc muốn xóa công việc này?")) return;
    setBusy(true);
    try {
      await deleteTask.mutateAsync(task.id);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  async function addComment() {
    if (!task || !comment.trim()) return;
    await api.createComment(board.id, task.id, comment.trim());
    setComment("");
    qc.invalidateQueries({ queryKey: ["comments", board.id, task.id] });
  }

  async function toggleAssignee(userId: string) {
    if (!task) return;
    const isAssigned = task.assignees.some((a) => a.user_id === userId);
    if (isAssigned) await api.unassignUser(board.id, task.id, userId);
    else await api.assignUser(board.id, task.id, userId);
    qc.invalidateQueries({ queryKey: ["board", board.id] });
  }

  const users = board.members.map((m) => ({ id: m.user_id, display_name: m.display_name, email: m.email }));

  return (
    <Dialog open={open} onClose={onClose} title="Chi tiết công việc">
      {!task ? null : (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Tiêu đề</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Cột</Label>
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
            <div className="space-y-2">
              <Label>Mức ưu tiên</Label>
              <select
                className="h-9 w-full rounded-md border border-border bg-transparent px-3 text-sm"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>{PRIORITY_LABEL[p] ?? p}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Bắt đầu làm</Label>
              <Input value={new Date(task.created_at).toLocaleString("vi-VN")} readOnly />
            </div>
            <div className="space-y-2">
              <Label>Ước lượng (giờ)</Label>
              <Input type="number" min={0} step={0.5} value={estHours} onChange={(e) => setEstHours(e.target.value)} />
            </div>
            <div className="space-y-2 col-span-2">
              <Label>Hạn chót</Label>
              <Input type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Nhãn (cách nhau bởi dấu phẩy)</Label>
            <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="fastapi, react, sql" />
          </div>
          <div className="space-y-2">
            <Label>Mô tả</Label>
            <Textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Người phụ trách</Label>
              <Button size="sm" variant="outline" type="button" onClick={() => onSuggestAssignee(task.id)}>
                ✨ Gợi ý bằng AI
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {users.map((u) => {
                const assigned = task.assignees.some((a) => a.user_id === u.id);
                return (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => toggleAssignee(u.id)}
                    className={
                      "px-2 py-1 rounded-md text-xs border transition-colors " +
                      (assigned ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent")
                    }
                  >
                    {u.display_name}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2 pt-2 border-t border-border">
            <Label>Bình luận ({comments.length})</Label>
            <div className="max-h-40 overflow-y-auto space-y-2">
              {comments.map((c) => (
                <div key={c.id} className="text-xs bg-secondary/50 rounded-md p-2">
                  <p className="text-muted-foreground mb-1">
                    {new Date(c.created_at).toLocaleString()}
                  </p>
                  <p>{c.body}</p>
                </div>
              ))}
              {comments.length === 0 && <p className="text-xs text-muted-foreground">Chưa có bình luận nào.</p>}
            </div>
            <div className="flex gap-2">
              <Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Nhập bình luận..." />
              <Button type="button" variant="secondary" onClick={addComment}>Gửi</Button>
            </div>
          </div>

          <div className="flex justify-between pt-2 border-t border-border">
            <Button variant="destructive" onClick={remove} disabled={busy}>Xóa</Button>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={onClose}>Hủy</Button>
              <Button onClick={save} disabled={busy}>
                {busy ? <Spinner /> : null}
                Lưu
              </Button>
            </div>
          </div>
        </div>
      )}
    </Dialog>
  );
}
