"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const token = useAuth((s) => s.token);
  useEffect(() => {
    router.replace(token ? "/boards" : "/login");
  }, [router, token]);
  return (
    <div className="min-h-screen flex items-center justify-center text-muted-foreground">
      Đang chuyển hướng...
    </div>
  );
}
