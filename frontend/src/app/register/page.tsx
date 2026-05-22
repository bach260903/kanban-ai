"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Input, Label, Spinner } from "@/components/ui/primitives";

export default function RegisterPage() {
  const router = useRouter();
  const setSession = useAuth((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.register({ email, password, display_name: displayName });
      const tok = await api.login({ email, password });
      localStorage.setItem("kanban_token", tok.access_token);
      const me = await api.me();
      setSession(tok.access_token, me);
      router.replace("/boards");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(typeof err.detail?.detail === "string" ? err.detail.detail : "Đăng ký thất bại");
      } else {
        setError("Đăng ký thất bại");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-secondary/30 to-background">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-semibold mb-1">Tạo tài khoản</h1>
        <p className="text-sm text-muted-foreground mb-6">Bắt đầu không gian làm việc Kanban có trợ lý AI.</p>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Tên hiển thị</Label>
            <Input id="name" required value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Tên của bạn" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ban@example.com" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Mật khẩu (&gt;= 8 ký tự)</Label>
            <Input id="password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Spinner /> : null}
            Tạo tài khoản
          </Button>
        </form>
        <p className="mt-6 text-sm text-center text-muted-foreground">
          Đã có tài khoản?{" "}
          <Link className="text-foreground underline underline-offset-4" href="/login">
            Đăng nhập
          </Link>
        </p>
      </Card>
    </div>
  );
}
