"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
    LogOut,
    User,
    LayoutDashboard,
    Bot,
    Phone,
    Megaphone,
    Headphones,
    Settings,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

const NAV_ITEMS = [
    { href: "/", label: "Dashboard", Icon: LayoutDashboard },
    { href: "/agents", label: "Agents", Icon: Bot },
    { href: "/calls", label: "Calls", Icon: Phone },
    { href: "/campaigns", label: "Campaigns", Icon: Megaphone },
    { href: "/monitor", label: "Monitor", Icon: Headphones },
    { href: "/settings", label: "Settings", Icon: Settings },
];

export default function Sidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const [user, setUser] = useState<{ email: string; tenant_name: string } | null>(null);

    useEffect(() => {
        fetch(`${API_BASE_URL}/auth/me`, {
            credentials: "include",
        })
            .then(res => {
                if (!res.ok) {
                    router.push("/login");
                    throw new Error("Invalid session");
                }
                return res.json();
            })
            .then(data => {
                if (data && data.email) {
                    setUser(data);
                }
            })
            .catch(err => {
                console.error("Failed to load user info:", err);
                router.push("/login");
            });
    }, [router]);

    const handleLogout = async () => {
        try {
            await fetch(`${API_BASE_URL}/auth/logout`, {
                method: "POST",
                credentials: "include",
            });
        } catch (err) {
            console.error("Logout request failed:", err);
        }
        router.push("/login");
        router.refresh();
    };

    return (
        <aside className="sidebar w-[240px] h-screen fixed top-0 left-0 flex flex-col py-6 px-4 z-50">
            {/* Logo */}
            <div className="flex items-center gap-2.5 mb-9 pl-2">
                <Image
                    src="/logo.png"
                    alt="Superactive"
                    width={40}
                    height={40}
                    className="w-auto h-10 object-contain"
                />
                <span className="text-lg font-bold tracking-tight">
                    Superactive
                </span>
            </div>

            {/* Nav Links */}
            <nav className="flex flex-col gap-1 flex-1">
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
                            <item.Icon className="w-5 h-5 shrink-0" />
                            {item.label}
                        </Link>
                    );
                })}
            </nav>

            {/* Status & User */}
            <div className="mt-auto flex flex-col gap-3">
                <div className="glass-card px-4 py-3.5 flex items-center gap-2.5">
                    <div className="pulse-live w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-[13px] text-[var(--text-secondary)]">
                        System Online
                    </span>
                </div>

                {/* User Profile & Logout */}
                {user ? (
                    <div className="bg-white/5 border text-sm border-white/10 rounded-2xl p-4 flex flex-col gap-3">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-gray-400">
                                <User className="w-4 h-4" />
                            </div>
                            <div className="flex-1 overflow-hidden">
                                <p className="font-semibold text-white truncate">
                                    {user.tenant_name || "Settings"}
                                </p>
                                <p className="text-xs text-gray-400 truncate">{user.email}</p>
                            </div>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center justify-center gap-2 text-red-400 font-medium bg-red-500/10 hover:bg-red-500/20 py-2 rounded-xl transition-colors"
                        >
                            <LogOut className="w-3.5 h-3.5" />
                            <span>Log out</span>
                        </button>
                    </div>
                ) : (
                    <button
                        onClick={handleLogout}
                        className="w-full flex items-center justify-center gap-2 text-red-400 font-medium bg-red-500/10 hover:bg-red-500/20 py-2 rounded-xl transition-colors mt-4"
                    >
                        <LogOut className="w-3.5 h-3.5" />
                        <span>Force Log out</span>
                    </button>
                )}
            </div>
        </aside>
    );
}
