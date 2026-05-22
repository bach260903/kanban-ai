"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Task } from "@/lib/types";
import { Badge } from "@/components/ui/primitives";

interface Props {
  task: Task;
  isMine?: boolean;
  onClick?: () => void;
}

const PRIORITY_COLOR: Record<string, string> = {
  urgent: "bg-red-100 text-red-900 dark:bg-red-900/30 dark:text-red-100",
  high: "bg-orange-100 text-orange-900 dark:bg-orange-900/30 dark:text-orange-100",
  medium: "bg-blue-100 text-blue-900 dark:bg-blue-900/30 dark:text-blue-100",
  low: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};
const PRIORITY_LABEL: Record<string, string> = {
  urgent: "Khẩn cấp",
  high: "Cao",
  medium: "Trung bình",
  low: "Thấp",
};

export function TaskCard({ task, isMine = false, onClick }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
    data: { type: "task", task },
  });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  const overdue = task.due_at && new Date(task.due_at) < new Date() && task.status !== "done";

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={
        "rounded-md border bg-card p-3 shadow-sm hover:shadow-md transition-shadow cursor-grab active:cursor-grabbing select-none " +
        (isMine
          ? "border-emerald-400/70 ring-1 ring-emerald-400/50 bg-emerald-50/40 dark:bg-emerald-900/10"
          : "border-border")
      }
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-snug flex-1">{task.title}</p>
        <Badge className={PRIORITY_COLOR[task.priority] || PRIORITY_COLOR.medium} variant="secondary">
          {PRIORITY_LABEL[task.priority] || task.priority}
        </Badge>
      </div>
      {isMine ? (
        <Badge variant="success" className="mt-2 text-[10px]">
          Được giao cho bạn
        </Badge>
      ) : null}
      {task.description && (
        <p className="mt-2 text-xs text-muted-foreground line-clamp-2">{task.description}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {task.tags?.slice(0, 3).map((t) => (
          <Badge key={t} variant="outline" className="text-[10px]">
            {t}
          </Badge>
        ))}
        {task.est_hours ? (
          <Badge variant="outline" className="text-[10px]">
            {task.est_hours}h
          </Badge>
        ) : null}
        {overdue ? (
          <Badge variant="destructive" className="text-[10px]">
            Quá hạn
          </Badge>
        ) : task.due_at ? (
          <span className="text-[10px] text-muted-foreground">
            {new Date(task.due_at).toLocaleDateString("vi-VN")}
          </span>
        ) : null}
      </div>
      <div className="mt-2 text-[10px] text-muted-foreground">
        Bắt đầu: {new Date(task.created_at).toLocaleDateString("vi-VN")}
        {task.due_at ? ` · Hạn chót: ${new Date(task.due_at).toLocaleDateString("vi-VN")}` : ""}
      </div>
      {task.assignees?.length ? (
        <div className="mt-3 flex -space-x-1.5">
          {task.assignees.slice(0, 3).map((a) => (
            <div
              key={a.user_id}
              title={a.display_name}
              className="h-6 w-6 rounded-full bg-primary text-primary-foreground text-[10px] font-medium flex items-center justify-center border-2 border-card"
            >
              {(a.display_name || a.email || "?").slice(0, 1).toUpperCase()}
            </div>
          ))}
          {task.assignees.length > 3 ? (
            <div className="h-6 w-6 rounded-full bg-muted text-[10px] flex items-center justify-center border-2 border-card">
              +{task.assignees.length - 3}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
