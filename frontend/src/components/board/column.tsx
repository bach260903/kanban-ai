"use client";

import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Column as ColumnType, Task } from "@/lib/types";
import { TaskCard } from "./task-card";
import { Badge, Button } from "@/components/ui/primitives";

interface Props {
  column: ColumnType;
  tasks: Task[];
  currentUserId?: string | null;
  onTaskClick: (task: Task) => void;
  onAddTask: (columnId: string) => void;
}

export function ColumnView({ column, tasks, currentUserId, onTaskClick, onAddTask }: Props) {
  const { setNodeRef, isOver } = useDroppable({
    id: column.id,
    data: { type: "column", columnId: column.id },
  });
  const overWip = column.wip_limit ? tasks.length > column.wip_limit : false;

  return (
    <div
      ref={setNodeRef}
      className={
        "flex flex-col w-72 shrink-0 rounded-lg border bg-secondary/30 transition-colors " +
        (isOver ? "border-primary bg-primary/5" : "border-border")
      }
    >
      <div className="flex items-center justify-between p-3 border-b border-border">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-sm">{column.name}</h3>
          <Badge variant={overWip ? "destructive" : "secondary"} className="text-[10px]">
            {tasks.length}
            {column.wip_limit ? ` / ${column.wip_limit}` : ""}
          </Badge>
        </div>
        <Button size="sm" variant="ghost" onClick={() => onAddTask(column.id)}>
          +
        </Button>
      </div>
      <div className="flex flex-col gap-2 p-2 min-h-[160px]">
        <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
          {tasks.map((t) => (
            <TaskCard
              key={t.id}
              task={t}
              isMine={!!currentUserId && t.assignees.some((a) => a.user_id === currentUserId)}
              onClick={() => onTaskClick(t)}
            />
          ))}
        </SortableContext>
      </div>
    </div>
  );
}
