"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogOut, User } from "lucide-react";

const NAV_ITEMS = [
    { href: "/", label: "Dashboard", icon: "📊" },
    { href: "/agents", label: "Agents", icon: "🤖" },
    { href: "/calls", label: "Calls", icon: "📞" },
    { href: "/campaigns", label: "Campaigns", icon: "📣" },
    { href: "/settings", label: "Settings", icon: "⚙️" },
];

export default function Sidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const [user, setUser] = useState<{ email: string; tenant_name: string } | null>(null);

    useEffect(() => {
        // Fetch current user details
        fetch("http://localhost:8765/api/auth/me", { credentials: "omit" }) // We have cookie or need to read it if it wasn't HttpOnly. Actually, let's just use the cookie we set. Wait, fetch to another port needs CORS config. 
        // We set the cookie as `superactive_auth` earlier. If we use headers: { Authorization: } we need to read it.
        // Let's read the cookie directly to get the token, since we set it via JS.
        const tokenMatch = document.cookie.match(/(?:^|; )superactive_auth=([^;]*)/);
        const token = tokenMatch ? tokenMatch[1] : null;

        if (token) {
            fetch("http://localhost:8765/api/auth/me", {
                headers: { "Authorization": `Bearer ${token}` }
            })
                .then(res => res.json())
                .then(data => {
                    if (data && data.email) {
                        setUser(data);
                    }
                })
                .catch(err => console.error("Failed to load user info:", err));
        }
    }, []);

    const handleLogout = () => {
        document.cookie = "superactive_auth=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
        router.push("/login");
        router.refresh();
    };

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
                        width: "auto",
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
            <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
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

                {/* User Profile & Logout */}
                {user && (
                    <div className="bg-white border text-sm border-gray-100 rounded-2xl p-4 flex flex-col gap-3 shadow-sm">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-gray-500">
                                <User size={16} />
                            </div>
                            <div className="flex-1 overflow-hidden">
                                <p className="font-semibold text-gray-900 truncate">
                                    {user.tenant_name || "Settings"}
                                </p>
                                <p className="text-xs text-gray-500 truncate">{user.email}</p>
                            </div>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center justify-center gap-2 text-red-600 font-medium bg-red-50 hover:bg-red-100 py-2 rounded-xl transition-colors"
                        >
                            <LogOut size={14} />
                            <span>Log out</span>
                        </button>
                    </div>
                )}
            </div>
        </aside>
    );
}
