"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/primitives";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { token, user, clear } = useAuth();

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  if (!token) return null;

  return (
    <div className="min-h-screen flex bg-background">
      <aside className="w-60 border-r border-border bg-sidebar text-sidebar-foreground flex flex-col">
        <div className="p-4 border-b border-sidebar-border">
          <Link href="/boards" className="font-semibold text-lg flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs">K</span>
            Kanban
          </Link>
          <p className="text-xs text-muted-foreground mt-1">Không gian làm việc đa tác tử</p>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          <NavLink href="/boards" pathname={pathname} icon="📋">Bảng công việc</NavLink>
          <NavLink href="/profile" pathname={pathname} icon="👤">Hồ sơ và kỹ năng</NavLink>
        </nav>
        <div className="p-4 border-t border-sidebar-border space-y-2">
          <div className="text-xs">
            <div className="font-medium truncate">{user?.display_name}</div>
            <div className="text-muted-foreground truncate">{user?.email}</div>
          </div>
          <Button variant="outline" size="sm" className="w-full" onClick={() => { clear(); router.replace("/login"); }}>
            Đăng xuất
          </Button>
        </div>
      </aside>
      <main className="flex-1 min-w-0">{children}</main>
    </div>
  );
}

function NavLink({ href, pathname, icon, children }: { href: string; pathname: string; icon: string; children: React.ReactNode }) {
  const active = pathname === href || pathname.startsWith(href + "/");
  return (
    <Link
      href={href}
      className={
        "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors " +
        (active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "hover:bg-sidebar-accent/60")
      }
    >
      <span>{icon}</span>
      {children}
    </Link>
  );
}
