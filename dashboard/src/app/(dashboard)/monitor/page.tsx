"use client";

import { useEffect, useRef } from "react";
import { AlertTriangle } from "lucide-react";
import { useCallMonitor } from "@/hooks/useCallMonitor";

export default function MonitorPage() {
    const {
        activeCalls,
        focusedCallId,
        transcript,
        statesVisited,
        isConnected,
        subscribeToCall,
        triggerTakeover
    } = useCallMonitor();

    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll transcript
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [transcript]);

    const handleSelectCall = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const val = e.target.value;
        if (val) subscribeToCall(val);
    };

    const focusedCall = activeCalls.find(c => c.call_id === focusedCallId);

    return (
        <div className="flex flex-col h-[calc(100vh-56px)] gap-6 animate-in fade-in duration-500">
            {/* Header */}
            <header className="flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
                        <span className="text-white text-lg font-bold">📞</span>
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white tracking-tight">Live Monitor</h1>
                        <p className="text-xs text-gray-500 mt-0.5">Real-time call monitoring &amp; agent takeover</p>
                    </div>
                </div>

                <div className="flex items-center gap-6">
                    <select
                        className="input min-w-[200px] text-sm py-2"
                        value={focusedCallId || ""}
                        onChange={handleSelectCall}
                    >
                        <option value="">Select a Call ({activeCalls.length} active)</option>
                        {activeCalls.map(call => (
                            <option key={call.call_id} value={call.call_id}>
                                {call.business_type} — {call.call_id.substring(0, 8)}…
                            </option>
                        ))}
                    </select>

                    <div className={`flex items-center gap-2 glass-card px-4 py-2 rounded-full border shadow-sm ${isConnected ? 'border-emerald-500/20' : 'border-red-500/20'}`}>
                        <span className="relative flex h-2.5 w-2.5">
                            {isConnected && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
                            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
                        </span>
                        <span className="text-sm font-semibold text-white tracking-wide">
                            {isConnected ? 'Online' : 'Connecting…'}
                        </span>
                    </div>
                </div>
            </header>

            {/* Main Content Grid */}
            <div className={`flex-1 min-h-0 grid grid-cols-12 gap-6 relative transition-opacity duration-300 ${!focusedCallId ? 'opacity-50 pointer-events-none' : ''}`}>

                {/* LEFT: Live Transcript */}
                <div className="col-span-12 lg:col-span-5 flex flex-col glass-card shadow-2xl overflow-hidden relative z-10">
                    <div className="p-4 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                        <h2 className="font-bold text-white tracking-wide">Live Transcript</h2>
                        {focusedCall && (
                            <span className="text-xs text-gray-400">
                                Turn {focusedCall.total_turns} · {focusedCall.duration_seconds}s
                            </span>
                        )}
                    </div>

                    <div ref={scrollRef} className="flex-1 p-6 overflow-y-auto flex flex-col gap-4">
                        {transcript.length === 0 ? (
                            <div className="text-center text-gray-500 text-sm mt-10">Waiting for conversation…</div>
                        ) : (
                            transcript.map((msg, idx) => (
                                <div key={idx} className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-start' : 'items-end'}`}>
                                    <span className={`text-[10px] uppercase tracking-widest font-bold ${msg.role === 'user' ? 'text-gray-500 ml-1' : 'text-blue-400 mr-1'}`}>
                                        {msg.role === 'user' ? 'Customer' : 'AI Agent 🤖'}
                                    </span>
                                    <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed max-w-[85%] shadow-sm
                                        ${msg.role === 'user'
                                            ? 'bg-[#1f2128] border border-white/5 text-gray-200 rounded-tl-sm'
                                            : 'bg-blue-600 font-medium text-white rounded-tr-sm shadow-md shadow-blue-500/20'
                                        }`}
                                    >
                                        {msg.text}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>

                    <div className="p-4 border-t border-white/5 bg-[#0b0c10]/50 backdrop-blur-md">
                        <div className="flex items-center gap-2">
                            <span className="relative flex h-2 w-2">
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                            </span>
                            <span className="text-xs text-emerald-400 font-bold tracking-wider uppercase">Monitoring…</span>
                        </div>
                    </div>
                </div>

                {/* MIDDLE: Call Info & States */}
                <div className="col-span-12 lg:col-span-4 flex flex-col gap-6 relative z-10">
                    {/* Call Info */}
                    <div className="glass-card shadow-xl">
                        <div className="p-4 border-b border-white/5 bg-white/[0.02]">
                            <h2 className="font-bold text-white tracking-wide">Call Details</h2>
                        </div>
                        <div className="p-6">
                            {focusedCall ? (
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Call ID</div>
                                        <div className="font-mono text-gray-300 text-xs">{focusedCall.call_id.substring(0, 16)}…</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Agent</div>
                                        <div className="font-medium text-gray-200">{focusedCall.agent_id?.substring(0, 12) || "—"}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Type</div>
                                        <div className="font-medium text-gray-200 capitalize">{focusedCall.business_type}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">State</div>
                                        <div className="font-medium text-blue-400 capitalize">{focusedCall.current_state}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Duration</div>
                                        <div className="font-medium text-gray-200">{focusedCall.duration_seconds}s</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Turns</div>
                                        <div className="font-medium text-gray-200">{focusedCall.total_turns}</div>
                                    </div>
                                </div>
                            ) : (
                                <p className="text-sm text-gray-500 italic">Select a call to view details</p>
                            )}
                        </div>
                    </div>

                    {/* State Timeline */}
                    <div className="glass-card flex-1 flex flex-col shadow-xl">
                        <div className="p-4 border-b border-white/5 bg-white/[0.02]">
                            <h2 className="font-bold text-white tracking-wide">State Timeline</h2>
                        </div>
                        <div className="p-6 flex-1 overflow-y-auto">
                            <div className="relative pl-6 border-l-2 border-white/5 space-y-6">
                                {statesVisited.length === 0 ? (
                                    <div className="text-sm text-gray-500 italic">No states visited yet</div>
                                ) : (
                                    statesVisited.map((state, idx) => (
                                        <div key={idx} className="relative">
                                            <div className={`absolute -left-[29px] top-1 w-3 h-3 rounded-full ring-4 ring-[#0b0c10] ${idx === statesVisited.length - 1 ? 'bg-blue-500' : 'bg-gray-600'}`} />
                                            <div className="font-bold text-sm text-gray-200 capitalize">{state.replace(/_/g, " ")}</div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* RIGHT: Summary & Actions */}
                <div className="col-span-12 lg:col-span-3 flex flex-col gap-6 relative z-10">
                    {/* Live Summary */}
                    <div className="glass-card flex-1 p-6 shadow-xl flex flex-col">
                        <h2 className="font-bold text-white tracking-wide mb-4">Live Summary</h2>
                        <ul className="space-y-3 text-sm text-gray-300">
                            <li className="flex justify-between">
                                <span className="text-gray-500">Active Calls</span>
                                <span className="font-bold text-white">{activeCalls.length}</span>
                            </li>
                            <li className="flex justify-between">
                                <span className="text-gray-500">Focused Call</span>
                                <span className="font-bold text-white">{focusedCall ? focusedCall.call_id.substring(0, 8) : "—"}</span>
                            </li>
                            <li className="flex justify-between">
                                <span className="text-gray-500">Current State</span>
                                <span className="font-bold text-blue-400 capitalize">{focusedCall?.current_state || "—"}</span>
                            </li>
                            <li className="flex justify-between">
                                <span className="text-gray-500">Turns</span>
                                <span className="font-bold text-white">{focusedCall?.total_turns || 0}</span>
                            </li>
                        </ul>
                    </div>

                    {/* Takeover */}
                    <div className="glass-card p-6 shadow-xl">
                        <h2 className="font-bold text-white tracking-wide mb-3">Agent Takeover</h2>
                        <p className="text-xs text-gray-400 mb-4">
                            Take control of the call from the AI agent. The caller will be transferred to you.
                        </p>
                        <button
                            onClick={() => focusedCallId && triggerTakeover(focusedCallId)}
                            disabled={!focusedCallId}
                            className="w-full bg-red-600 hover:bg-red-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white px-6 py-3 rounded-lg flex items-center justify-center gap-2 font-black tracking-widest text-sm transition-all hover:scale-[1.02] active:scale-95 shadow-lg shadow-red-500/20"
                        >
                            <AlertTriangle className="w-4 h-4" />
                            TAKE OVER
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
