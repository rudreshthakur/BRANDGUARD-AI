import {
  BarChart3, BookOpenCheck, ClipboardCheck, FileSearch, History, Image as ImageIcon, LayoutGrid, LogOut, Menu, Settings, X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { roleLabel } from "../lib/format";
import { useSession } from "../lib/session";
import type { Role } from "../lib/types";
import { Logo } from "./Logo";

const NAV = [
  { to: "/app/overview", label: "Overview", icon: LayoutGrid },
  { to: "/app/auditor", label: "Content Auditor", icon: FileSearch },
  { to: "/app/review", label: "Review Queue", icon: ClipboardCheck },
  { to: "/app/knowledge", label: "Brand Knowledge", icon: BookOpenCheck },
  { to: "/app/visual", label: "Visual Inspector", icon: ImageIcon },
  { to: "/app/analytics", label: "Brand Drift", icon: BarChart3 },
  { to: "/app/history", label: "Audit History", icon: History },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

const ROLE_HELP: Record<Role, string> = {
  creator: "Writes content, runs audits, applies corrections, submits for review.",
  reviewer: "Inspects findings and evidence, requests changes or approves.",
  admin: "Manages approved brand knowledge: documents, facts, rules.",
};

export function RoleSwitch() {
  const { session, setRole } = useSession();
  if (!session) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-xs text-graphite-mute md:inline">Acting as</span>
      <div className="inline-flex rounded-md border border-paper-rule bg-white p-0.5" role="radiogroup" aria-label="Demo role">
        {(["creator", "reviewer", "admin"] as Role[]).map((r) => (
          <button key={r} role="radio" aria-checked={session.role === r} title={ROLE_HELP[r]}
            onClick={() => setRole(r)}
            className={`rounded px-2.5 py-1 text-xs font-medium ${session.role === r ? "bg-ink text-white" : "text-graphite hover:text-ink"}`}>
            {roleLabel[r]}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Layout() {
  const { session, leave } = useSession();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);

  const sidebar = (
    <nav className="flex h-full flex-col bg-ink px-3 py-5 text-white" aria-label="Main">
      <div className="mb-7 px-2"><Logo light /></div>
      <ul className="space-y-0.5">
        {NAV.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink to={to} onClick={() => setOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-md px-2.5 py-2 text-sm ${isActive ? "bg-white/10 font-medium text-white" : "text-white/70 hover:bg-white/5 hover:text-white"}`}>
              <Icon className="h-4 w-4" aria-hidden /> {label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="mt-auto space-y-3 px-2 pt-6 text-xs text-white/60">
        <div>
          <div className="text-white/90">{session?.brandName}</div>
          <div>{session?.isDemo ? "Private demo workspace with synthetic data" : "Workspace"}</div>
        </div>
        <button className="inline-flex items-center gap-1.5 hover:text-white" onClick={() => { leave(); nav("/"); }}>
          <LogOut className="h-3.5 w-3.5" aria-hidden /> Leave workspace
        </button>
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
      <aside className="hidden w-60 shrink-0 bg-ink lg:block"><div className="sticky top-0 h-screen">{sidebar}</div></aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button className="absolute inset-0 bg-ink/40" aria-label="Close menu" onClick={() => setOpen(false)} />
          <aside className="relative h-full w-64">{sidebar}</aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-paper-edge bg-paper/95 px-4 py-3 backdrop-blur lg:px-8">
          <div className="flex items-center gap-3">
            <button className="btn-ghost p-1.5 lg:hidden" onClick={() => setOpen((o) => !o)} aria-label="Open menu">
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
            {session?.isDemo && (
              <span className="hidden text-xs text-graphite-mute sm:inline">
                Demo mode: Northstar Labs is a fictional brand. Roles switch without sign-in; this is not production authentication.
              </span>
            )}
          </div>
          <RoleSwitch />
        </header>
        <main id="main" className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-7 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
