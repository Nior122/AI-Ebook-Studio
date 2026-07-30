"use client";

// Application shell: responsive left sidebar (desktop) + collapsible drawer
// (mobile) and a top bar with the user menu. Wraps all authenticated pages.

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useUser, useClerk } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import {
  IconBook,
  IconDashboard,
  IconHelp,
  IconLogout,
  IconMenu,
  IconClose,
  IconProjects,
  IconSettings,
  IconPlus,
} from "@/components/ui/icons";

interface NavItem {
  label: string;
  href: string;
  icon: (props: React.SVGProps<SVGSVGElement>) => React.ReactElement;
}

const NAV: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: IconDashboard },
  { label: "Projects", href: "/projects", icon: IconProjects },
  { label: "Settings", href: "/settings", icon: IconSettings },
  { label: "Help", href: "/help", icon: IconHelp },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function SidebarContent({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <Link
        href="/dashboard"
        onClick={onNavigate}
        className="flex items-center gap-2 px-6 py-5 text-foreground"
      >
        <IconBook className="h-6 w-6" />
        <span className="text-base font-semibold tracking-tight">AI Ebook Studio</span>
      </Link>
      <nav className="flex-1 space-y-1 px-3 py-2" aria-label="Primary">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
              )}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-3 py-4">
        <Link href="/new-book" onClick={onNavigate}>
          <Button className="w-full">
            <IconPlus className="h-4 w-4" />
            New Book
          </Button>
        </Link>
      </div>
    </div>
  );
}

function UserMenu() {
  const { user } = useUser();
  const { signOut } = useClerk();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const displayName = user?.fullName ?? user?.primaryEmailAddress?.emailAddress ?? "U";
  const initials = displayName
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  const email = user?.primaryEmailAddress?.emailAddress ?? "";

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full p-1 pr-2 text-sm hover:bg-secondary"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
          {initials}
        </span>
        <span className="hidden max-w-[140px] truncate text-left font-medium text-foreground sm:block">
          {displayName}
        </span>
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            role="menu"
            className="absolute right-0 z-20 mt-2 w-48 rounded-md border border-border bg-card p-1 shadow-lg"
          >
            <div className="px-3 py-2 text-xs text-muted-foreground">{email}</div>
            <button
              role="menuitem"
              onClick={() => signOut({ redirectUrl: "/sign-in" })}
              className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-sm text-foreground hover:bg-secondary"
            >
              <IconLogout className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-card lg:block">
        <SidebarContent pathname={pathname} />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-border bg-card">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-4 text-muted-foreground hover:text-foreground"
              aria-label="Close navigation"
            >
              <IconClose className="h-5 w-5" />
            </button>
            <SidebarContent pathname={pathname} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur">
          <button
            onClick={() => setMobileOpen(true)}
            className="text-muted-foreground hover:text-foreground lg:hidden"
            aria-label="Open navigation"
          >
            <IconMenu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          <UserMenu />
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
