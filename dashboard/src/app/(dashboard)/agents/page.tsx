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
    PhoneIncoming,
    PhoneOutgoing,
    ArrowLeftRight
} from "lucide-react";
import { API_BASE_URL, fetcher } from "@/lib/api";
import type { AgentConfig } from "@/lib/types";
import TestCallModal from "@/components/TestCallModal";
import PageHeader from "@/components/ui/PageHeader";

import EmptyState from "@/components/ui/EmptyState";

const TYPE_ICONS: Record<string, typeof Bot> = {
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

    const [isTestModalOpen, setIsTestModalOpen] = useState(false);
    const [selectedAgent, setSelectedAgent] = useState<{ id: string; name: string } | null>(null);

    const openTestModal = (e: React.MouseEvent, agent: AgentConfig) => {
        e.preventDefault();
        setSelectedAgent({ id: agent.id, name: agent.name });
        setIsTestModalOpen(true);
    };

    if (error) return <div className="p-8 text-red-400">Failed to load agents.</div>;
    if (!agents) return <div className="p-8 text-gray-400">Loading agents...</div>;

    const hasAgents = agents.length > 0;

    return (
        <div>
            {/* Header */}
            <PageHeader
                title="Agents"
                description="Configure and manage your AI voice agents"
                action={
                    hasAgents && (
                        <Link href="/agents/new">
                            <button className="btn-primary flex items-center gap-2">
                                <Plus className="w-5 h-5" /> New Agent
                            </button>
                        </Link>
                    )
                }
            />

            {/* Agent Cards or Empty State */}
            {!hasAgents ? (
                <EmptyState
                    icon={Bot}
                    title="No agents found"
                    description="Create your first AI voice agent to handle calls, book appointments, or assist customers."
                    action={
                        <Link href="/agents/new" className="no-underline">
                            <button className="btn-primary flex items-center gap-2">
                                <Plus className="w-5 h-5" /> Create Agent
                            </button>
                        </Link>
                    }
                />
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                    {agents.map((agent) => {
                        const Icon = TYPE_ICONS[agent.business_type] || Bot;

                        return (
                            <Link key={agent.id} href={`/agents/${agent.id}`} className="no-underline block">
                                <div className="glass-card hover:border-blue-500/30 transition-colors p-6 cursor-pointer relative">
                                    {/* Top row */}
                                    <div className="flex justify-between items-start mb-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-11 h-11 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-500">
                                                <Icon className="w-6 h-6" />
                                            </div>
                                            <div>
                                                <div className="text-base font-semibold text-white">
                                                    {agent.name}
                                                </div>
                                                <div className="text-xs text-gray-400 capitalize">
                                                    {agent.business_type}
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
                                    <p className="text-[13px] text-gray-400 mb-5 leading-relaxed min-h-[40px]">
                                        {agent.description || "No description provided."}
                                    </p>

                                    {/* Guardrail bar */}
                                    <div className="mb-4">
                                        <div className="flex justify-between mb-1.5">
                                            <span className="text-xs text-gray-500">Guardrail Level</span>
                                            <span className="text-xs font-semibold text-white">
                                                {guardrailLabel(agent.guardrail_level)} ({(agent.guardrail_level * 100).toFixed(0)}%)
                                            </span>
                                        </div>
                                        <div className="h-1.5 bg-gray-700/50 rounded-full overflow-hidden">
                                            <div
                                                className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-blue-500 to-indigo-500"
                                                style={{ width: `${agent.guardrail_level * 100}%` }}
                                            />
                                        </div>
                                    </div>

                                    {/* Info row + Action */}
                                    <div className="flex items-center justify-between pt-4 border-t border-white/5">
                                        <div className="flex gap-3 text-xs text-gray-500">
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
                                </div>
                            </Link>
                        );
                    })}
                </div>
            )}

            {/* Test Call Modal */}
            {selectedAgent && (
                <TestCallModal
                    isOpen={isTestModalOpen}
                    onClose={() => setIsTestModalOpen(false)}
                    agentId={selectedAgent.id}
                    agentName={selectedAgent.name}
                />
            )}
        </div>
    );
}
