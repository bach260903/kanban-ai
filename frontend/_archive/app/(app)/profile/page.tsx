"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSkills, useUserSkills } from "@/lib/queries";
import { useAuth } from "@/lib/auth";
import { Badge, Button, Card, Input, Spinner } from "@/components/ui/primitives";
import { useQueryClient } from "@tanstack/react-query";

const LEVELS = [
  { value: "beginner", label: "Mới bắt đầu" },
  { value: "intermediate", label: "Trung cấp" },
  { value: "expert", label: "Chuyên gia" },
];

export default function ProfilePage() {
  const user = useAuth((s) => s.user);
  const { data: skills = [] } = useSkills();
  const { data: userSkills = [] } = useUserSkills(user?.id ?? null);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [newSkill, setNewSkill] = useState("");
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();

  useEffect(() => {
    const map: Record<string, string> = {};
    for (const us of userSkills) map[us.skill_id] = us.level;
    setSelected(map);
  }, [userSkills]);

  function toggle(skillId: string) {
    setSelected((prev) => {
      const next = { ...prev };
      if (next[skillId]) delete next[skillId];
      else next[skillId] = "intermediate";
      return next;
    });
  }

  function changeLevel(skillId: string, level: string) {
    setSelected((prev) => ({ ...prev, [skillId]: level }));
  }

  async function save() {
    if (!user) return;
    setBusy(true);
    try {
      await api.setUserSkills(
        user.id,
        Object.entries(selected).map(([skill_id, level]) => ({ skill_id, level })),
      );
      qc.invalidateQueries({ queryKey: ["user-skills", user.id] });
    } finally {
      setBusy(false);
    }
  }

  async function createNew() {
    if (!newSkill.trim()) return;
    await api.createSkill(newSkill.trim().toLowerCase());
    setNewSkill("");
    qc.invalidateQueries({ queryKey: ["skills"] });
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Hồ sơ cá nhân</h1>
        <p className="text-sm text-muted-foreground">Quản lý kỹ năng để AI gợi ý phân công chính xác hơn.</p>
      </div>

      <Card className="p-5 space-y-3">
        <h2 className="font-medium">Thông tin của tôi</h2>
        <p className="text-sm">{user?.display_name} · <span className="text-muted-foreground">{user?.email}</span></p>
        <div className="text-xs text-muted-foreground">
          UID: <span className="font-mono">{user?.id}</span>
        </div>
      </Card>

      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Kỹ năng</h2>
          <Badge variant="secondary">{Object.keys(selected).length} đã chọn</Badge>
        </div>
        <div className="flex gap-2">
          <Input value={newSkill} onChange={(e) => setNewSkill(e.target.value)} placeholder="Thêm kỹ năng mới (vd: fastapi)" />
          <Button variant="secondary" onClick={createNew} disabled={!newSkill.trim()}>+ Thêm</Button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {skills.map((s) => {
            const checked = !!selected[s.id];
            return (
              <div key={s.id} className="flex items-center gap-2 border border-border rounded-md p-2">
                <input type="checkbox" checked={checked} onChange={() => toggle(s.id)} className="h-4 w-4" />
                <span className="flex-1 text-sm">{s.name}</span>
                {checked && (
                  <select
                    className="h-7 rounded-md border border-border bg-transparent px-2 text-xs"
                    value={selected[s.id]}
                    onChange={(e) => changeLevel(s.id, e.target.value)}
                  >
                    {LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
                  </select>
                )}
              </div>
            );
          })}
        </div>
        <div className="flex justify-end">
          <Button onClick={save} disabled={busy}>
            {busy ? <Spinner /> : null}
            Lưu kỹ năng
          </Button>
        </div>
      </Card>
    </div>
  );
}
