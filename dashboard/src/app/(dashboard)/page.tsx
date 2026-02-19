"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import {
    Phone,
    Clock,
    Calendar,
    DollarSign,
    Activity,
    Users,
    Shield,
    Stethoscope,
    Utensils,
    Bot,
    TrendingUp,
    TrendingDown,
    Loader2
} from "lucide-react";
import { API_BASE_URL, fetcher } from "@/lib/api";

import type { AnalyticsData } from "@/lib/types";

function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
}

const TYPE_ICONS: Record<string, any> = {
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
    Icon: any;
    color?: string;
}) {
    const bgColors: Record<string, string> = {
        blue: "rgba(59, 130, 246, 0.1)",
        green: "rgba(16, 185, 129, 0.1)",
        purple: "rgba(139, 92, 246, 0.1)",
        orange: "rgba(249, 115, 22, 0.1)",
    };

    const textColors: Record<string, string> = {
        blue: "#3b82f6",
        green: "#10b981",
        purple: "#8b5cf6",
        orange: "#f97316",
    };

    return (
        <div className="metric-card hover:bg-white/[0.02] transition-colors" style={{ flex: 1, minWidth: 200 }}>
            <div
                style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: 8,
                }}
            >
                <span className="metric-label">{label}</span>
                <span
                    style={{
                        width: 36,
                        height: 36,
                        borderRadius: 10,
                        background: bgColors[color],
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: textColors[color]
                    }}
                >
                    <Icon className="w-5 h-5" />
                </span>
            </div>
            <div className="metric-value">{value}</div>
            {change && (
                <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 4 }}>
                    {change.startsWith("+") ? (
                        <TrendingUp className="w-3 h-3 text-emerald-400" />
                    ) : (
                        <TrendingDown className="w-3 h-3 text-red-400" />
                    )}
                    <span
                        style={{
                            fontSize: 12,
                            color: change.startsWith("+") ? "#34d399" : "#f87171",
                        }}
                    >
                        {change} vs last month
                    </span>
                </div>
            )}
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

    // SVG donut chart
    let offset = 0;
    const segments = Object.entries(outcomes).map(([key, value]) => {
        const pct = total > 0 ? (value / total) * 100 : 0;
        const dash = `${pct} ${100 - pct}`;
        const seg = { key, value, pct, dash, offset, color: colors[key] || "#666" };
        offset += pct;
        return seg;
    });

    return (
        <div className="glass-card" style={{ padding: 24, flex: 1 }}>
            <h3 className="section-title">Call Outcomes</h3>
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 32,
                }}
            >
                <div style={{ position: "relative", width: 160, height: 160 }}>
                    <svg viewBox="0 0 42 42" style={{ transform: "rotate(-90deg)" }}>
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
                    <div
                        style={{
                            position: "absolute",
                            top: "50%",
                            left: "50%",
                            transform: "translate(-50%, -50%)",
                            textAlign: "center",
                        }}
                    >
                        <div style={{ fontSize: 22, fontWeight: 700 }}>{total.toLocaleString()}</div>
                        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Calls</div>
                    </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    {segments.map((seg) => (
                        <div key={seg.key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <div
                                style={{
                                    width: 10,
                                    height: 10,
                                    borderRadius: 3,
                                    background: seg.color,
                                }}
                            />
                            <span style={{ fontSize: 13, color: "var(--text-secondary)", textTransform: "capitalize", minWidth: 80 }}>
                                {seg.key.replace("_", " ")}
                            </span>
                            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                                {Math.round(seg.pct)}%
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

function AgentPerformanceTable({
    agents,
}: {
    agents: any[];
}) {
    return (
        <div className="glass-card" style={{ padding: 24, marginTop: 20 }}>
            <h3 className="section-title">Agent Performance</h3>
            <div className="overflow-x-auto">
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Agent</th>
                            <th>Calls</th>
                            <th>Conversion Rate</th>
                            <th>Avg Duration</th>
                            <th>Score</th>
                        </tr>
                    </thead>
                    <tbody>
                        {agents.map((agent) => {
                            const Icon = TYPE_ICONS[agent.business_type] || Bot;
                            return (
                                <tr key={agent.agent_id}>
                                    <td>
                                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                                            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                                                <Icon className="w-5 h-5" />
                                            </div>
                                            <div>
                                                <div
                                                    style={{
                                                        fontWeight: 600,
                                                        color: "var(--text-primary)",
                                                        fontSize: 14,
                                                        textTransform: "capitalize",
                                                    }}
                                                >
                                                    {agent.agent_id.replace(/_/g, " ")}
                                                </div>
                                                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                                                    {agent.business_type}
                                                </div>
                                            </div>
                                        </div>
                                    </td>
                                    <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                                        {agent.calls}
                                    </td>
                                    <td>
                                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                            <div
                                                style={{
                                                    width: 100,
                                                    height: 6,
                                                    background: "rgba(55, 65, 81, 0.5)",
                                                    borderRadius: 3,
                                                    overflow: "hidden",
                                                }}
                                            >
                                                <div
                                                    style={{
                                                        width: `${agent.conversion_rate}%`,
                                                        height: "100%",
                                                        borderRadius: 3,
                                                        background:
                                                            agent.conversion_rate >= 35
                                                                ? "#10b981"
                                                                : agent.conversion_rate >= 25
                                                                    ? "#3b82f6"
                                                                    : "#f59e0b",
                                                    }}
                                                />
                                            </div>
                                            <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: 13 }}>
                                                {agent.conversion_rate}%
                                            </span>
                                        </div>
                                    </td>
                                    <td>{formatDuration(agent.avg_duration)}</td>
                                    <td>
                                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                            <div
                                                style={{
                                                    width: 60,
                                                    height: 6,
                                                    borderRadius: 3,
                                                    overflow: "hidden",
                                                    background: "rgba(55, 65, 81, 0.5)",
                                                }}
                                            >
                                                <div
                                                    style={{
                                                        width: `${Math.min(agent.conversion_rate * 2.5, 100)}%`,
                                                        height: "100%",
                                                        borderRadius: 3,
                                                        background:
                                                            agent.conversion_rate >= 35
                                                                ? "#10b981"
                                                                : agent.conversion_rate >= 25
                                                                    ? "#3b82f6"
                                                                    : "#f59e0b",
                                                    }}
                                                />
                                            </div>
                                            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                                                {(agent.conversion_rate / 10 + 3.5).toFixed(1)}/5
                                            </span>
                                        </div>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default function DashboardPage() {
    const { data, error } = useSWR<AnalyticsData>(`${API_BASE_URL}/analytics`, fetcher);

    // In MVP, we might get empty data if no calls.
    // Ensure we handle loading/error gracefully.

    if (error) return <div className="p-12 text-center text-red-400">Failed to load analytics: {error.message}</div>;
    if (!data) return (
        <div className="flex items-center justify-center h-screen text-gray-400 gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            Loading dashboard...
        </div>
    );

    // Real cost from call logger vs $3/min human agent benchmark
    const actualCost = data.total_cost || 0;
    const humanEquivalent = Math.round((data.avg_duration || 120) / 60 * 3 * data.total_calls); // $3/min human agent
    const costSavings = Math.max(0, humanEquivalent - Math.round(actualCost));

    return (
        <div>
            {/* Header */}
            <div
                style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 28,
                }}
            >
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>
                        Dashboard
                    </h1>
                    <p style={{ fontSize: 14, color: "var(--text-muted)" }}>
                        Overview of your AI voice agent performance
                    </p>
                </div>
                {/* Live Indicator - Connect to WebSocket later */}
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        background: "rgba(16, 185, 129, 0.1)",
                        border: "1px solid rgba(16, 185, 129, 0.3)",
                        padding: "8px 16px",
                        borderRadius: 10,
                    }}
                >
                    <div className="pulse-live bg-emerald-500 w-2 h-2 rounded-full" />
                    <span className="text-emerald-400 text-sm font-semibold">
                        System Online
                    </span>
                </div>
            </div>

            {/* Metric Cards */}
            <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
                <MetricCard
                    label="Total Calls"
                    value={data.total_calls.toLocaleString()}
                    change={data.changes?.total_calls}
                    Icon={Phone}
                    color="blue"
                />
                <MetricCard
                    label="Avg Duration"
                    value={formatDuration(data.avg_duration)}
                    change={data.changes?.avg_duration}
                    Icon={Clock}
                    color="purple"
                />
                <MetricCard
                    label="Booking Rate"
                    value={`${data.booking_rate}%`}
                    change={data.changes?.booking_rate}
                    Icon={Calendar}
                    color="green"
                />
                <MetricCard
                    label="Cost Savings"
                    value={`$${costSavings.toLocaleString()}`}
                    change={data.changes?.total_calls}
                    Icon={DollarSign}
                    color="orange"
                />
            </div>

            {/* Charts Row */}
            <div style={{ display: "flex", gap: 20, marginBottom: 20, flexWrap: "wrap" }}>
                {/* Call Volume Chart - placeholder with gradient bar */}
                <div className="glass-card" style={{ padding: 24, flex: 1.5, minWidth: 300 }}>
                    <h3 className="section-title">Calls per Day (Last 30 Days)</h3>
                    {data.calls_per_day && data.calls_per_day.length > 0 ? (
                        <>
                            <div
                                style={{
                                    height: 180,
                                    display: "flex",
                                    alignItems: "flex-end",
                                    gap: 4,
                                    paddingBottom: 24,
                                }}
                            >
                                {(() => {
                                    const maxCount = Math.max(1, ...data.calls_per_day.map(d => d.count));
                                    return data.calls_per_day.map((day, i) => {
                                        const pct = (day.count / maxCount) * 100;
                                        return (
                                            <div
                                                key={day.date}
                                                title={`${day.date}: ${day.count} call${day.count !== 1 ? "s" : ""}`}
                                                style={{
                                                    flex: 1,
                                                    height: `${Math.max(pct, day.count > 0 ? 8 : 2)}%`,
                                                    background: day.count > 0
                                                        ? `linear-gradient(to top, rgba(59, 130, 246, 0.3), rgba(59, 130, 246, 0.7))`
                                                        : "rgba(55, 65, 81, 0.3)",
                                                    borderRadius: "2px 2px 0 0",
                                                    transition: "height 0.3s ease",
                                                    cursor: "default",
                                                }}
                                            />
                                        );
                                    });
                                })()}
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-muted)" }}>
                                <span>{data.calls_per_day[0]?.date.slice(5)}</span>
                                {data.calls_per_day.length > 15 && (
                                    <span>{data.calls_per_day[Math.floor(data.calls_per_day.length / 2)]?.date.slice(5)}</span>
                                )}
                                <span>{data.calls_per_day[data.calls_per_day.length - 1]?.date.slice(5)}</span>
                            </div>
                        </>
                    ) : (
                        <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 14 }}>
                            No call data yet. Make some calls to see the chart.
                        </div>
                    )}
                </div>

                <OutcomeDonut outcomes={data.outcomes} />
            </div>

            {/* Agent Performance Table */}
            <AgentPerformanceTable agents={data.agent_performance} />
        </div>
    );
}
