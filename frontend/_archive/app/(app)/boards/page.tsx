"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useBoards } from "@/lib/queries";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Card, Dialog, Input, Label, Spinner, Textarea } from "@/components/ui/primitives";

export default function BoardsPage() {
  const { data: boards, isLoading, error } = useBoards();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const qc = useQueryClient();

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createBoard({ title, description: description || undefined });
      setOpen(false);
      setTitle("");
      setDescription("");
      qc.invalidateQueries({ queryKey: ["boards"] });
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Bảng công việc</h1>
          <p className="text-sm text-muted-foreground">Các dự án bạn đang theo dõi.</p>
        </div>
        <Button onClick={() => setOpen(true)}>+ Tạo bảng mới</Button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground"><Spinner /> Đang tải...</div>
      ) : error ? (
        <Card className="p-6"><p className="text-sm text-destructive">Không thể tải danh sách bảng.</p></Card>
      ) : !boards || boards.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-muted-foreground mb-4">Chưa có bảng nào. Hãy tạo bảng đầu tiên.</p>
          <Button onClick={() => setOpen(true)}>+ Tạo bảng mới</Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {boards.map((b) => (
            <Link key={b.id} href={`/boards/${b.id}`}>
              <Card className="p-5 hover:bg-accent/40 transition-colors cursor-pointer h-full">
                <h3 className="font-medium">{b.title}</h3>
                {b.description && <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{b.description}</p>}
                <p className="text-xs text-muted-foreground mt-3">Tạo ngày {new Date(b.created_at).toLocaleDateString("vi-VN")}</p>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="Tạo bảng mới">
        <form onSubmit={create} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Tên bảng</Label>
            <Input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Kế hoạch Q1" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="desc">Mô tả (tùy chọn)</Label>
            <Textarea id="desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Mục tiêu, phạm vi, liên kết..." />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Hủy</Button>
            <Button type="submit" disabled={creating}>
              {creating ? <Spinner /> : null}
              Tạo bảng
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
