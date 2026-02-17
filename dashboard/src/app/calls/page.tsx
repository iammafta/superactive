"use client";

import { useState } from "react";

import useSWR from "swr";
import {
    Search,
    Filter,
    Phone,
    Clock,
    MessageSquare,
    User,
    Bot,
    Shield,
    Stethoscope,
    Utensils,
    CheckCircle,
    XCircle,
    ArrowRightCircle,
    HelpCircle,
    Loader2
} from "lucide-react";
import { API_BASE_URL, fetcher } from "@/lib/api";

interface CallRecord {
    call_id: string;
    agent_id: string;
    business_type: string;
    started_at: string;
    duration_seconds: number;
    outcome: "booked" | "transferred" | "completed" | "hung_up" | "in_progress";
    total_turns: number;
    transcript: { role: string; text: string; ts: string }[];
    states_visited: string[];
}



const TYPE_ICONS: Record<string, any> = {
    insurance: Shield,
    medical: Stethoscope,
    restaurant: Utensils,
};

function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatDate(isoString: string): string {
    return new Date(isoString).toLocaleString();
}

const OUTCOME_STYLES = {
    booked: { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", icon: CheckCircle },
    transferred: { color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20", icon: ArrowRightCircle },
    completed: { color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", icon: CheckCircle },
    hung_up: { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20", icon: XCircle },
    in_progress: { color: "text-gray-400", bg: "bg-gray-500/10", border: "border-gray-500/20", icon: HelpCircle },
};

export default function CallsPage() {
    const { data: calls, error } = useSWR<CallRecord[]>(`${API_BASE_URL}/calls`, fetcher);
    const [selectedCall, setSelectedCall] = useState<CallRecord | null>(null);
    const [filter, setFilter] = useState("all");

    if (error) return <div className="p-8 text-red-400">Failed to load calls.</div>;
    if (!calls) return (
        <div className="flex items-center justify-center h-screen text-gray-400 gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            Loading call history...
        </div>
    );

    const filteredCalls = filter === "all" ? calls : calls.filter((c) => c.outcome === filter);

    return (
        <div className="flex h-[calc(100vh-140px)] gap-6">
            {/* Left: List */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Controls */}
                <div className="flex justify-between items-center mb-6">
                    <div>
                        <h1 className="text-2xl font-bold mb-1 text-white">Call History</h1>
                        <p className="text-sm text-gray-400">Review past conversations</p>
                    </div>
                    <div className="flex gap-3">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                            <input
                                type="text"
                                placeholder="Search..."
                                className="pl-9 pr-4 py-2 bg-black/20 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
                            />
                        </div>
                        <div className="relative">
                            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                            <select
                                value={filter}
                                onChange={(e) => setFilter(e.target.value)}
                                className="pl-9 pr-8 py-2 bg-black/20 border border-white/10 rounded-lg text-sm text-white appearance-none focus:outline-none focus:border-blue-500 cursor-pointer"
                            >
                                <option value="all">All Outcomes</option>
                                <option value="booked">Booked</option>
                                <option value="transferred">Transferred</option>
                                <option value="completed">Completed</option>
                                <option value="hung_up">Hung Up</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* Table */}
                <div className="glass-card flex-1 overflow-hidden flex flex-col">
                    <div className="overflow-y-auto flex-1">
                        <table className="w-full text-left border-collapse">
                            <thead className="sticky top-0 bg-[#0f0f11] z-10 text-xs uppercase text-gray-500 font-semibold border-b border-white/5">
                                <tr>
                                    <th className="p-4 pl-6">Agent</th>
                                    <th className="p-4">Time</th>
                                    <th className="p-4">Duration</th>
                                    <th className="p-4">Outcome</th>
                                    <th className="p-4 text-right pr-6">Turns</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {filteredCalls.map((call) => {
                                    const style = OUTCOME_STYLES[call.outcome] || OUTCOME_STYLES.in_progress;
                                    const OutcomeIcon = style.icon;
                                    const AgentIcon = TYPE_ICONS[call.business_type] || Bot;

                                    return (
                                        <tr
                                            key={call.call_id}
                                            onClick={() => setSelectedCall(call)}
                                            className={`
                                                cursor-pointer transition-colors hover:bg-white/[0.02]
                                                ${selectedCall?.call_id === call.call_id ? "bg-white/[0.04]" : ""}
                                            `}
                                        >
                                            <td className="p-4 pl-6">
                                                <div className="flex items-center gap-3">
                                                    <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                                                        <AgentIcon className="w-4 h-4" />
                                                    </div>
                                                    <div>
                                                        <div className="font-medium text-white text-sm">
                                                            {call.agent_id}
                                                        </div>
                                                        <div className="text-xs text-gray-500 capitalize">
                                                            {call.business_type}
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="p-4 text-sm text-gray-400">
                                                {formatDate(call.started_at)}
                                            </td>
                                            <td className="p-4 text-sm text-gray-400 font-mono">
                                                {formatDuration(call.duration_seconds)}
                                            </td>
                                            <td className="p-4">
                                                <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${style.bg} ${style.color} ${style.border}`}>
                                                    <OutcomeIcon className="w-3 h-3" />
                                                    <span className="capitalize">{call.outcome.replace("_", " ")}</span>
                                                </div>
                                            </td>
                                            <td className="p-4 text-right pr-6 text-sm text-gray-400">
                                                {call.total_turns}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Right: Details Panel */}
            {selectedCall && (
                <div className="w-[400px] flex flex-col gap-4 animate-in slide-in-from-right-4 duration-300">
                    {/* Transcript Panel */}
                    <div className="glass-card flex-1 flex flex-col min-h-0">
                        <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                            <h3 className="font-semibold text-white flex items-center gap-2">
                                <MessageSquare className="w-4 h-4 text-blue-400" />
                                Transcript
                            </h3>
                            <span className="text-xs text-gray-500 font-mono">{selectedCall.call_id.slice(0, 8)}...</span>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {selectedCall.transcript && selectedCall.transcript.length > 0 ? (
                                selectedCall.transcript.map((msg, i) => (
                                    <div
                                        key={i}
                                        className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"
                                            }`}
                                    >
                                        <div className={`
                                            max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed
                                            ${msg.role === "user"
                                                ? "bg-blue-600 text-white rounded-tr-sm"
                                                : "bg-[#27272a] text-gray-200 border border-white/5 rounded-tl-sm"
                                            }
                                        `}>
                                            {msg.text}
                                        </div>
                                        <span className="text-[10px] text-gray-600 px-1">
                                            {msg.role === "user" ? "Caller" : "AI"} • {new Date(msg.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                        </span>
                                    </div>
                                ))
                            ) : (
                                <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-2">
                                    <MessageSquare className="w-8 h-8 opacity-20" />
                                    <p className="text-sm">No transcript available</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Metadata Panel */}
                    <div className="glass-card p-4">
                        <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">
                            State Transition Flow
                        </h4>
                        <div className="flex flex-wrap gap-2">
                            {selectedCall.states_visited && selectedCall.states_visited.length > 0 ? (
                                selectedCall.states_visited.map((state, i) => (
                                    <div key={i} className="flex items-center gap-2">
                                        <div className="px-3 py-1.5 rounded-md bg-white/5 border border-white/10 text-xs text-gray-300 font-mono">
                                            {state}
                                        </div>
                                        {i < selectedCall.states_visited.length - 1 && (
                                            <span className="text-gray-600">→</span>
                                        )}
                                    </div>
                                ))
                            ) : (
                                <span className="text-gray-500 text-sm italic">No state data</span>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
