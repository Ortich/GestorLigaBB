"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { session } from "@/lib/api";

const NAV = [
  { href: "/equipo", label: "Equipo", icon: "\u{1F6E1}" },
  { href: "/partido", label: "Partido", icon: "\u{1F3C8}" },
  { href: "/liga", label: "Liga", icon: "\u{1F3C6}" },
  { href: "/reglas", label: "Reglas", icon: "\u{1F4D6}" },
];

export function AppShell({
  title,
  subtitle,
  children,
  requireAuth = true,
  action,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  requireAuth?: boolean;
  action?: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(!requireAuth);

  useEffect(() => {
    if (!requireAuth) return;
    if (!session.token) {
      router.replace("/");
      return;
    }
    setReady(true);
  }, [requireAuth, router]);

  if (!ready) return null;

  return (
    <div className="mx-auto flex min-h-[100dvh] w-full max-w-xl flex-col">
      <header className="sticky top-0 z-30 border-b border-white/10 bg-pitch-950/85 px-4 py-3 backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-bold text-stone-50">{title}</h1>
            {subtitle && <p className="truncate text-xs text-stone-400">{subtitle}</p>}
          </div>
          {action}
        </div>
      </header>

      <main className="flex-1 space-y-4 px-4 py-4 pb-28">{children}</main>

      <nav className="fixed bottom-0 left-1/2 z-30 w-full max-w-xl -translate-x-1/2 border-t border-white/10 bg-pitch-950/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
        <ul className="grid grid-cols-4">
          {NAV.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex min-h-[60px] flex-col items-center justify-center gap-0.5 text-[11px] font-semibold transition ${
                    active ? "text-gold-400" : "text-stone-400"
                  }`}
                >
                  <span className="text-xl leading-none">{item.icon}</span>
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
