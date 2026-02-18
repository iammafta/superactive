"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
    { href: "/", label: "Dashboard", icon: "📊" },
    { href: "/agents", label: "Agents", icon: "🤖" },
    { href: "/calls", label: "Calls", icon: "📞" },
    { href: "/campaigns", label: "Campaigns", icon: "📣" },
    { href: "/settings", label: "Settings", icon: "⚙️" },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <aside
            className="sidebar"
            style={{
                width: 240,
                height: "100vh",
                position: "fixed",
                top: 0,
                left: 0,
                display: "flex",
                flexDirection: "column",
                padding: "24px 16px",
                zIndex: 50,
            }}
        >
            {/* Logo */}
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    marginBottom: 36,
                    paddingLeft: 8,
                }}
            >
                <img
                    src="/logo.png"
                    alt="Superactive"
                    style={{
                        width: 40,
                        height: 40,
                        objectFit: "contain"
                    }}
                />
                <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: -0.5 }}>
                    Superactive
                </span>
            </div>

            {/* Nav Links */}
            <nav style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
                {NAV_ITEMS.map((item) => {
                    const isActive =
                        item.href === "/"
                            ? pathname === "/"
                            : pathname.startsWith(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`sidebar-link ${isActive ? "active" : ""}`}
                        >
                            <span style={{ fontSize: 18, width: 24, textAlign: "center" }}>
                                {item.icon}
                            </span>
                            {item.label}
                        </Link>
                    );
                })}
            </nav>

            {/* Active calls badge */}
            <div
                className="glass-card"
                style={{
                    padding: "14px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                }}
            >
                <div
                    className="pulse-live"
                    style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: "#10b981",
                    }}
                />
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                    System Online
                </span>
            </div>
        </aside>
    );
}
