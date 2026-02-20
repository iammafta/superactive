"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
    Shield,
    Stethoscope,
    Utensils,
    Bot,
    Wrench,
    GitBranch,
    Plus,
    Phone,
    Activity,
    PhoneIncoming,
    PhoneOutgoing,
    ArrowLeftRight
} from "lucide-react";
import { API_BASE_URL, fetcher } from "@/lib/api";
import type { AgentConfig } from "@/lib/types";
import TestChatModal from "@/components/TestChatModal";

const TYPE_ICONS: Record<string, any> = {
    insurance: Shield,
    medical: Stethoscope,
    restaurant: Utensils,
};

function guardrailLabel(level: number): string {
    if (level >= 0.8) return "Strict";
    if (level >= 0.5) return "Guided";
    if (level >= 0.2) return "Flexible";
    return "Open";
}

export default function AgentsPage() {
    const { data: agents, error } = useSWR<AgentConfig[]>(`${API_BASE_URL}/agents`, fetcher);

    // Test Call Modal State
    const [isTestModalOpen, setIsTestModalOpen] = useState(false);
    const [selectedAgent, setSelectedAgent] = useState<{ id: string; name: string } | null>(null);

    const openTestModal = (e: React.MouseEvent, agent: AgentConfig) => {
        e.preventDefault(); // Prevent Link navigation
        setSelectedAgent({ id: agent.id, name: agent.name });
        setIsTestModalOpen(true);
    };

    if (error) return <div className="p-8 text-red-400">Failed to load agents.</div>;
    if (!agents) return <div className="p-8 text-gray-400">Loading agents...</div>;

    return (
        <div>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Agents</h1>
                    <p style={{ fontSize: 14, color: "var(--text-muted)" }}>
                        Configure and manage your AI voice agents
                    </p>
                </div>
                <Link href="/agents/new">
                    <button className="btn-primary" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <Plus className="w-5 h-5" /> New Agent
                    </button>
                </Link>
            </div>

            {/* Agent Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
                {agents.map((agent) => {
                    const Icon = TYPE_ICONS[agent.business_type] || Bot;
                    const color = agent.active ? "#10b981" : "#6b7280";

                    return (
                        <Link key={agent.id} href={`/agents/${agent.id}`} className="no-underline block">
                            <div className="glass-card hover:border-blue-500/30 transition-colors" style={{ padding: 24, cursor: "pointer", position: "relative" }}>
                                {/* Top row */}
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                                        <div
                                            style={{
                                                width: 44,
                                                height: 44,
                                                borderRadius: 12,
                                                background: "rgba(59, 130, 246, 0.1)",
                                                border: "1px solid rgba(59, 130, 246, 0.2)",
                                                display: "flex",
                                                alignItems: "center",
                                                justifyContent: "center",
                                                color: "#3b82f6"
                                            }}
                                        >
                                            <Icon className="w-6 h-6" />
                                        </div>
                                        <div>
                                            <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)" }}>
                                                {agent.name}
                                            </div>
                                            <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "capitalize" }}>
                                                {agent.business_type}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                    <span className={`badge ${agent.active ? "badge-success" : "badge-secondary"}`}>
                                        {agent.active ? "Active" : "Inactive"}
                                    </span>
                                    {agent.agent_type === 'inbound' && (
                                        <span className="flex items-center gap-1 text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                            <PhoneIncoming className="w-3 h-3" /> Inbound
                                        </span>
                                    )}
                                    {agent.agent_type === 'outbound' && (
                                        <span className="flex items-center gap-1 text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                            <PhoneOutgoing className="w-3 h-3" /> Outbound
                                        </span>
                                    )}
                                    {agent.agent_type === 'hybrid' && (
                                        <span className="flex items-center gap-1 text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                            <ArrowLeftRight className="w-3 h-3" /> Hybrid
                                        </span>
                                    )}
                                </div>
                            </div>

                            {/* Description */}
                            <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 20, lineHeight: 1.5, minHeight: 40 }}>
                                {agent.description || "No description provided."}
                            </p>

                            {/* Trigger Call Button (Overlay) */}
                            <div className="absolute top-4 right-20">
                                {/* If we want it in the header? No, let's put it at the bottom actions */}
                            </div>

                            {/* Guardrail bar */}
                            <div style={{ marginBottom: 16 }}>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Guardrail Level</span>
                                    <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                                        {guardrailLabel(agent.guardrail_level)} ({(agent.guardrail_level * 100).toFixed(0)}%)
                                    </span>
                                </div>
                                <div style={{ height: 6, background: "rgba(55, 65, 81, 0.5)", borderRadius: 3, overflow: "hidden" }}>
                                    <div
                                        style={{
                                            width: `${agent.guardrail_level * 100}%`,
                                            height: "100%",
                                            borderRadius: 3,
                                            background: `linear-gradient(to right, #10b981, #3b82f6, #6366f1)`,
                                        }}
                                    />
                                </div>
                            </div>

                            {/* Info row + Action */}
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                                <div style={{ display: "flex", gap: 12, fontSize: 12, color: "var(--text-muted)" }}>
                                    <span className="flex items-center gap-1"><Wrench className="w-3 h-3" /> {agent.allowed_tools?.length || 0} tools</span>
                                    <span className="flex items-center gap-1"><GitBranch className="w-3 h-3" /> {agent.states?.length || 0} states</span>
                                </div>

                                <button
                                    onClick={(e) => openTestModal(e, agent)}
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 hover:text-blue-300 text-xs font-medium transition-colors border border-blue-500/20"
                                >
                                    <Phone className="w-3.5 h-3.5" />
                                    Test Call
                                </button>
                            </div>
                        </Link>
                    );
                })}
            </div>

            {/* Test Chat Modal UI Simulator */}
            {selectedAgent && (
                <TestChatModal
                    isOpen={isTestModalOpen}
                    onClose={() => setIsTestModalOpen(false)}
                    agentId={selectedAgent.id}
                    agentName={selectedAgent.name}
                />
            )}
        </div>
    );
}
