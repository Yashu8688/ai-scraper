"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Building2,
  Briefcase,
  Users,
  History,
  Settings,
  LogOut,
  ShieldCheck,
  Menu,
  X,
  ChevronRight,
  Send,
} from "lucide-react";

const navItems = [
  {
    label: "Platform",
    items: [
      { name: "Overview",         href: "/dashboard",             icon: LayoutDashboard, adminOnly: false },
      { name: "Companies",        href: "/dashboard/companies",   icon: Building2,       adminOnly: false },
      { name: "Job Leads",        href: "/dashboard/jobs",        icon: Briefcase,       adminOnly: false },
      { name: "Email",            href: "/dashboard/domain-jobs", icon: Send,            adminOnly: false },
    ],
  },
  {
    label: "Administration",
    items: [
      { name: "Operators",        href: "/dashboard/users",     icon: Users,     adminOnly: true  },
      { name: "Activity Logs",   href: "/dashboard/activity",  icon: History,   adminOnly: true  },
      { name: "Settings",         href: "/dashboard/settings",  icon: Settings,  adminOnly: true  },
    ],
  },
];

function NavLink({
  href,
  icon: Icon,
  name,
  active,
  onClick,
}: {
  href: string;
  icon: React.ElementType;
  name: string;
  active: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`nav-item ${active ? "active" : ""}`}
    >
      <Icon className="nav-item-icon" strokeWidth={active ? 2 : 1.75} />
      <span>{name}</span>
      {active && (
        <ChevronRight
          className="ml-auto opacity-40"
          style={{ width: "0.75rem", height: "0.75rem" }}
        />
      )}
    </Link>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setEmail(localStorage.getItem("email") || "operator@cyberjobs.com");
    setRole(localStorage.getItem("role") || "editor");
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("email");
    router.push("/login");
  };

  const initials = email.slice(0, 2).toUpperCase();

  const sidebarContent = (
    <div className="sidebar">
      {/* ── Logo ─────────────────────────────────── */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <ShieldCheck strokeWidth={2} style={{ width: "1rem", height: "1rem", color: "#fff" }} />
        </div>
        <div>
          <div className="sidebar-logo-sub">ATS Platform</div>
        </div>
      </div>

      {/* ── Navigation ───────────────────────────── */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-4">
        {navItems.map((section) => (
          <div key={section.label}>
            <div className="sidebar-section-label">{section.label}</div>
            {section.items.map((item) => {
              if (item.adminOnly && role !== "admin") return null;
              return (
                <NavLink
                  key={item.name}
                  href={item.href}
                  icon={item.icon}
                  name={item.name}
                  active={pathname === item.href}
                  onClick={() => setIsOpen(false)}
                />
              );
            })}
          </div>
        ))}
      </nav>

      {/* ── Profile Footer ────────────────────────── */}
      <div
        style={{
          borderTop: "1px solid var(--border-base)",
          padding: "0.875rem 0.75rem",
          background: "var(--surface-card)",
        }}
      >
        {/* User row */}
        <div className="flex items-center gap-2.5 px-1 py-1 rounded-lg mb-1">
          {/* Avatar */}
          <div
            className="flex items-center justify-center rounded-lg text-xs font-bold flex-shrink-0"
            style={{
              width: "2rem",
              height: "2rem",
              background:
                role === "admin"
                  ? "linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)"
                  : "linear-gradient(135deg, var(--color-accent-light) 0%, var(--border-base) 100%)",
              color: role === "admin" ? "var(--red-text)" : "var(--color-accent)",
              border: `1px solid ${role === "admin" ? "var(--red-border)" : "var(--border-base)"}`,
            }}
          >
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p
              className="truncate text-xs font-600"
              style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-primary)" }}
            >
              {email}
            </p>
            <span
              className="inline-flex items-center rounded-full px-1.5 py-0.5 mt-0.5"
              style={{
                fontSize: "0.5625rem",
                fontWeight: 700,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                background: role === "admin" ? "var(--red-bg)" : "var(--surface-muted)",
                color: role === "admin" ? "var(--red-text)" : "var(--text-secondary)",
                border: `1px solid ${role === "admin" ? "var(--red-border)" : "var(--border-base)"}`,
              }}
            >
              {role}
            </span>
          </div>
        </div>

        {/* Sign out */}
        <button
          onClick={handleLogout}
          className="btn btn-ghost w-full justify-start gap-2.5 mt-1"
          style={{ fontSize: "0.75rem", padding: "0.5rem 0.625rem" }}
        >
          <LogOut style={{ width: "0.875rem", height: "0.875rem" }} />
          Sign out
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* ── Mobile topbar ──────────────────────── */}
      <div
        className="flex h-14 items-center justify-between px-4 md:hidden"
        style={{
          borderBottom: "1px solid var(--border-base)",
          background: "var(--surface-card)",
        }}
      >
        <Link href="/dashboard" className="flex items-center gap-2 font-bold" style={{ color: "var(--text-primary)" }}>
          <div
            className="flex items-center justify-center rounded-lg"
            style={{
              width: "1.625rem",
              height: "1.625rem",
              background: "var(--color-accent)",
            }}
          >
            <ShieldCheck strokeWidth={2} style={{ width: "0.875rem", height: "0.875rem", color: "#fff" }} />
          </div>
          <span className="sidebar-logo-sub" style={{ fontSize: "0.75rem" }}>ATS Platform</span>
        </Link>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="btn btn-ghost btn-icon"
        >
          {isOpen ? <X style={{ width: "1.125rem", height: "1.125rem" }} /> : <Menu style={{ width: "1.125rem", height: "1.125rem" }} />}
        </button>
      </div>

      {/* ── Desktop sidebar ────────────────────── */}
      <div className="hidden md:flex">
        {sidebarContent}
      </div>

      {/* ── Mobile drawer ──────────────────────── */}
      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40 md:hidden"
            style={{ background: "rgba(28,25,23,0.25)", backdropFilter: "blur(3px)" }}
            onClick={() => setIsOpen(false)}
          />
          <div
            className="fixed inset-y-0 left-0 z-50 md:hidden"
            style={{ animation: "slideUp 200ms var(--ease-out)" }}
          >
            {sidebarContent}
          </div>
        </>
      )}
    </>
  );
}
