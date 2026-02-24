"use client";

import useSWR from "swr";
import {
    Phone,
    Clock,
    Shield,
    Stethoscope,
    Utensils,
    Bot,
    TrendingUp,
    TrendingDown,
    Loader2,
    MessageSquare,
    CheckCircle2,
    BookOpen,
    ExternalLink
} from "lucide-react";
import Link from "next/link";
import { API_BASE_URL, fetcher } from "@/lib/api";
import type { AnalyticsData } from "@/lib/types";

function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
}

const TYPE_ICONS: Record<string, React.ElementType> = {
    insurance: Shield,
    medical: Stethoscope,
    restaurant: Utensils,
};

function MetricCard({
    label,
    value,
    change,
    Icon,
    color = "blue"
}: {
    label: string;
    value: string;
    change?: string;
    Icon: React.ElementType;
    color?: string;
}) {
    const textColors: Record<string, string> = {
        blue: "#3b82f6",
        green: "#10b981",
        purple: "#8b5cf6",
        orange: "#f97316",
    };

    return (
        <div className="glass-card hover:bg-white/[0.02] transition-colors flex flex-col justify-between" style={{ padding: 20, minHeight: 120 }}>
            <div className="flex justify-between items-start mb-2">
                <span className="text-sm text-[var(--text-muted)] font-medium">{label}</span>
                <span className="p-2 rounded-lg bg-white/5" style={{ color: textColors[color] }}>
                    <Icon className="w-4 h-4" />
                </span>
            </div>
            <div>
                <div className="text-2xl font-bold text-[var(--text-primary)]">{value}</div>
                {change && (
                    <div className="flex items-center gap-1 mt-1">
                        {change.startsWith("+") ? (
                            <TrendingUp className="w-3 h-3 text-emerald-400" />
                        ) : (
                            <TrendingDown className="w-3 h-3 text-red-400" />
                        )}
                        <span className="text-xs" style={{ color: change.startsWith("+") ? "#34d399" : "#f87171" }}>
                            {change} vs last month
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}

function OutcomeDonut({ outcomes }: { outcomes: Record<string, number> }) {
    const total = Object.values(outcomes).reduce((a, b) => a + b, 0);
    const colors: Record<string, string> = {
        booked: "#10b981",
        transferred: "#3b82f6",
        completed: "#f59e0b",
        hung_up: "#ef4444",
    };

    let offset = 0;
    const segments = Object.entries(outcomes).map(([key, value]) => {
        const pct = total > 0 ? (value / total) * 100 : 0;
        const dash = `${pct} ${100 - pct} `;
        const seg = { key, value, pct, dash, offset, color: colors[key] || "#666" };
        offset += pct;
        return seg;
    });

    return (
        <div className="flex items-center justify-center gap-8">
            <div className="relative w-32 h-32">
                <svg viewBox="0 0 42 42" className="-rotate-90 w-full h-full">
                    {total > 0 ? segments.map((seg) => (
                        <circle
                            key={seg.key}
                            cx="21"
                            cy="21"
                            r="15.915"
                            fill="transparent"
                            stroke={seg.color}
                            strokeWidth="5"
                            strokeDasharray={seg.dash}
                            strokeDashoffset={-seg.offset}
                            strokeLinecap="round"
                        />
                    )) : (
                        <circle cx="21" cy="21" r="15.915" fill="transparent" stroke="#333" strokeWidth="5" />
                    )}
                </svg>
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
                    <div className="text-xl font-bold">{total.toLocaleString()}</div>
                    <div className="text-[10px] text-[var(--text-muted)]">Calls</div>
                </div>
            </div>
            <div className="flex flex-col gap-2">
                {segments.map((seg) => (
                    <div key={seg.key} className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-sm" style={{ background: seg.color }} />
                        <span className="text-xs text-[var(--text-secondary)] capitalize min-w-[70px]">
                            {seg.key.replace("_", " ")}
                        </span>
                        <span className="text-xs font-semibold text-[var(--text-primary)]">
                            {Math.round(seg.pct)}%
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function DashboardPage() {
    const { data, error, isLoading } = useSWR<AnalyticsData>(`${API_BASE_URL}/analytics`, fetcher);

    if (error) return <div className="p-12 text-center text-red-400">Failed to load analytics: {error.message}</div>;
    if (isLoading || !data) return (
        <div className="flex items-center justify-center h-[80vh] text-gray-400 gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            Loading dashboard...
        </div>
    );

    return (
        <div className="max-w-7xl mx-auto pb-12">
            {/* Header Area */}
            <div className="flex justify-between items-end mb-8">
                <div>
                    <h1 className="text-2xl font-bold mb-1 text-white">
                        Command Center
                    </h1>
                    <p className="text-sm text-[var(--text-muted)]">
                        Real-time overview of your AI workforce
                    </p>
                </div>
                <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 rounded-lg">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-emerald-400 text-sm font-semibold">Systems Online</span>
                </div>
            </div>

            {/* Bento Grid Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-4 gap-6">

                {/* Left Column (Main Stats & Feed) - Takes up 3 cols on XL */}
                <div className="lg:col-span-2 xl:col-span-3 space-y-6">

                    {/* Top KPIs */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <MetricCard
                            label="Total Conversations"
                            value={data.total_calls.toLocaleString()}
                            change={data.changes?.total_calls}
                            Icon={MessageSquare}
                            color="blue"
                        />
                        <MetricCard
                            label="Avg Call Duration"
                            value={formatDuration(data.avg_duration)}
                            change={data.changes?.avg_duration}
                            Icon={Clock}
                            color="purple"
                        />
                        <MetricCard
                            label="Booking / Success Rate"
                            value={`${data.booking_rate}%`}
                            change={data.changes?.booking_rate}
                            Icon={CheckCircle2}
                            color="green"
                        />
                    </div>

                    {/* Middle Section: Recent Transcripts & Outcomes */}
                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

                        {/* Feed Widget (2/3 width on XL) */}
                        <div className="xl:col-span-2 glass-card p-6 flex flex-col h-[400px]">
                            <div className="flex justify-between items-center mb-6">
                                <h3 className="section-title !mb-0">Live Transcripts</h3>
                                <span className="text-xs text-[var(--text-muted)]">Last 10 calls</span>
                            </div>

                            <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                                {data.recent_calls?.length > 0 ? (
                                    data.recent_calls.map((call, idx) => (
                                        <div key={call.call_id || idx} className="p-3 rounded-lg bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-colors flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${call.outcome === 'booked' ? 'bg-emerald-500/20 text-emerald-400' : call.outcome === 'hung_up' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'}`}>
                                                    <Phone className="w-4 h-4" />
                                                </div>
                                                <div>
                                                    <div className="text-sm font-medium text-[var(--text-primary)]">
                                                        {call.business_type ? call.business_type.charAt(0).toUpperCase() + call.business_type.slice(1) : "Agent"} Protocol
                                                    </div>
                                                    <div className="text-xs text-[var(--text-muted)] flex items-center gap-2">
                                                        <span>{formatDuration(call.duration_seconds)}</span>
                                                        <span>•</span>
                                                        <span>{new Date(call.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md ${call.outcome === 'booked' ? 'bg-emerald-500/10 text-emerald-400' :
                                                    call.outcome === 'hung_up' ? 'bg-red-500/10 text-red-400' :
                                                        'bg-blue-500/10 text-blue-400'
                                                    }`}>
                                                    {call.outcome.replace("_", " ")}
                                                </span>
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <div className="h-full flex items-center justify-center text-sm text-[var(--text-muted)]">
                                        No recent calls found.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Outcomes (1/3 width on XL) */}
                        <div className="glass-card p-6 flex flex-col justify-center items-center h-[400px]">
                            <h3 className="section-title self-start w-full">Outcomes</h3>
                            <div className="flex-1 w-full flex items-center justify-center">
                                <OutcomeDonut outcomes={data.outcomes} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Column — Quick Actions */}
                <div className="space-y-6 flex flex-col">

                    {/* Quick Start Guide */}
                    <div className="glass-card p-6 border border-blue-500/20 bg-blue-500/5">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
                                <BookOpen className="w-5 h-5 text-white" />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-white">Quick Start</h3>
                                <p className="text-xs text-blue-400">Get up and running</p>
                            </div>
                        </div>
                        <ul className="text-sm text-gray-400 space-y-3 mb-6">
                            <li className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">1</span>
                                Create an AI agent
                            </li>
                            <li className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">2</span>
                                Run a test call
                            </li>
                            <li className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs font-bold">3</span>
                                Launch a campaign
                            </li>
                        </ul>
                        <Link href="/agents/new" className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-colors no-underline">
                            Create Your First Agent
                        </Link>
                    </div>

                    {/* Documentation Link */}
                    <div className="glass-card p-6 flex-1 flex flex-col">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center">
                                <ExternalLink className="w-5 h-5 text-gray-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-white">Resources</h3>
                                <p className="text-xs text-gray-500">Docs & guides</p>
                            </div>
                        </div>
                        <ul className="text-sm text-gray-400 space-y-3 flex-1">
                            <li className="flex items-center gap-2 hover:text-white transition-colors cursor-pointer">
                                <span className="text-blue-400">→</span> Agent configuration guide
                            </li>
                            <li className="flex items-center gap-2 hover:text-white transition-colors cursor-pointer">
                                <span className="text-blue-400">→</span> State machine reference
                            </li>
                            <li className="flex items-center gap-2 hover:text-white transition-colors cursor-pointer">
                                <span className="text-blue-400">→</span> Campaign best practices
                            </li>
                            <li className="flex items-center gap-2 hover:text-white transition-colors cursor-pointer">
                                <span className="text-blue-400">→</span> Webhook integration
                            </li>
                        </ul>
                    </div>

                </div>
            </div>

            {/* Agent Performance Table (Bottom Full Width) */}
            <div className="glass-card mt-6 p-6">
                <h3 className="section-title">Fleet Performance</h3>
                <div className="overflow-x-auto">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Agent</th>
                                <th>Volume</th>
                                <th>Success Rate</th>
                                <th>Avg Duration</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.agent_performance?.map((agent) => {
                                const Icon = TYPE_ICONS[agent.business_type] || Bot;
                                return (
                                    <tr key={agent.agent_id}>
                                        <td>
                                            <div className="flex items-center gap-3">
                                                <div className="p-2 rounded-lg bg-white/5 text-[var(--text-secondary)]">
                                                    <Icon className="w-4 h-4" />
                                                </div>
                                                <div>
                                                    <div className="font-semibold text-[var(--text-primary)] text-sm capitalize">
                                                        {agent.agent_id.replace(/_/g, " ")}
                                                    </div>
                                                    <div className="text-xs text-[var(--text-muted)]">
                                                        {agent.business_type}
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="font-medium text-[var(--text-primary)]">
                                            {agent.calls} calls
                                        </td>
                                        <td>
                                            <div className="flex items-center gap-3">
                                                <div className="w-24 h-1.5 bg-white/10 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full rounded-full transition-all duration-500"
                                                        style={{
                                                            width: `${agent.conversion_rate}%`,
                                                            background: agent.conversion_rate >= 35 ? "#10b981" : agent.conversion_rate >= 25 ? "#3b82f6" : "#f59e0b",
                                                        }}
                                                    />
                                                </div>
                                                <span className="font-medium text-[var(--text-primary)] text-sm">
                                                    {agent.conversion_rate}%
                                                </span>
                                            </div>
                                        </td>
                                        <td className="text-sm text-[var(--text-secondary)]">
                                            {formatDuration(agent.avg_duration)}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
