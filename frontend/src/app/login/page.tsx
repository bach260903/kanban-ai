"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Input, Label, Spinner } from "@/components/ui/primitives";

export default function LoginPage() {
  const router = useRouter();
  const setSession = useAuth((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const tok = await api.login({ email, password });
      localStorage.setItem("kanban_token", tok.access_token);
      const me = await api.me();
      setSession(tok.access_token, me);
      router.replace("/boards");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(typeof err.detail?.detail === "string" ? err.detail.detail : "Đăng nhập thất bại");
      } else {
        setError("Đăng nhập thất bại");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-secondary/30 to-background">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-semibold mb-1">Chào mừng bạn quay lại</h1>
        <p className="text-sm text-muted-foreground mb-6">Đăng nhập để tiếp tục làm việc trên Kanban.</p>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ban@example.com" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Mật khẩu</Label>
            <Input id="password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Spinner /> : null}
            Đăng nhập
          </Button>
        </form>
        <p className="mt-6 text-sm text-center text-muted-foreground">
          Chưa có tài khoản?{" "}
          <Link className="text-foreground underline underline-offset-4" href="/register">
            Đăng ký ngay
          </Link>
        </p>
      </Card>
    </div>
  );
}
