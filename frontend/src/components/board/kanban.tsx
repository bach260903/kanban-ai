"use client";

import { useMemo, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { arrayMove } from "@dnd-kit/sortable";
import type { BoardDetail, Task } from "@/lib/types";
import { ColumnView } from "./column";
import { TaskCard } from "./task-card";
import { useUpdateTask } from "@/lib/queries";
import { useQueryClient } from "@tanstack/react-query";

interface Props {
  board: BoardDetail;
  currentUserId?: string | null;
  onTaskClick: (task: Task) => void;
  onAddTask: (columnId: string) => void;
}

export function Kanban({ board, currentUserId, onTaskClick, onAddTask }: Props) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));
  const updateTask = useUpdateTask(board.id);
  const qc = useQueryClient();
  const [activeTask, setActiveTask] = useState<Task | null>(null);

  const tasksByCol = useMemo(() => {
    const map: Record<string, Task[]> = {};
    for (const c of board.columns) map[c.id] = [];
    for (const t of board.tasks) {
      if (!map[t.column_id]) map[t.column_id] = [];
      map[t.column_id].push(t);
    }
    Object.values(map).forEach((arr) => arr.sort((a, b) => a.position - b.position));
    return map;
  }, [board]);

  function handleDragStart(e: DragStartEvent) {
    const t = e.active.data.current?.task as Task | undefined;
    setActiveTask(t || null);
  }

  function handleDragEnd(e: DragEndEvent) {
    setActiveTask(null);
    const { active, over } = e;
    if (!over) return;
    const taskId = String(active.id);
    const task = board.tasks.find((t) => t.id === taskId);
    if (!task) return;

    let targetColId: string | null = null;
    let targetIndex: number | null = null;

    const overData = over.data.current as any;
    if (overData?.type === "column") {
      targetColId = overData.columnId;
      targetIndex = (tasksByCol[targetColId!] || []).length;
    } else if (overData?.type === "task") {
      const overTask = overData.task as Task;
      targetColId = overTask.column_id;
      const list = tasksByCol[targetColId] || [];
      targetIndex = list.findIndex((t) => t.id === overTask.id);
    }
    if (!targetColId || targetIndex == null) return;

    if (targetColId === task.column_id) {
      const list = tasksByCol[targetColId];
      const fromIdx = list.findIndex((t) => t.id === task.id);
      if (fromIdx === targetIndex) return;
      const newList = arrayMove(list, fromIdx, targetIndex);
      // Optimistic local order: assign positions
      const prev = qc.getQueryData<BoardDetail>(["board", board.id]);
      if (prev) {
        const newTasks = prev.tasks.map((t) => {
          if (t.column_id !== targetColId) return t;
          const idx = newList.findIndex((x) => x.id === t.id);
          return idx >= 0 ? { ...t, position: idx } : t;
        });
        qc.setQueryData(["board", board.id], { ...prev, tasks: newTasks });
      }
      updateTask.mutate({ taskId: task.id, body: { position: targetIndex } });
    } else {
      // Move to another column
      updateTask.mutate({ taskId: task.id, body: { column_id: targetColId, position: targetIndex } });
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4">
        {[...board.columns]
          .sort((a, b) => a.position - b.position)
          .map((c) => (
            <ColumnView
              key={c.id}
              column={c}
              tasks={tasksByCol[c.id] || []}
              currentUserId={currentUserId}
              onTaskClick={onTaskClick}
              onAddTask={onAddTask}
            />
          ))}
      </div>
      <DragOverlay>
        {activeTask ? (
          <TaskCard
            task={activeTask}
            isMine={!!currentUserId && activeTask.assignees.some((a) => a.user_id === currentUserId)}
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
