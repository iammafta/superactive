"use client";

import { useState, useEffect, useRef } from "react";
import { Mic, PhoneOff, ArrowRightLeft, AlertTriangle } from "lucide-react";
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

    // Dynamic fake CRM data based on focused call
    const fakeCustomer = {
        name: focusedCall?.call_id ? `Customer ${focusedCall.call_id.substring(0, 4)}` : "Select a call",
        initials: "C",
        tier: "Standard",
        phone: "(---) --- ----",
        email: "unknown",
        status: focusedCall ? "Active" : "Waiting",
    };

    return (
        <div className="flex flex-col h-[calc(100vh-56px)] gap-6 animate-in fade-in duration-500">
            {/* Header */}
            <header className="flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
                        <span className="text-white text-lg font-bold">🏢</span>
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white tracking-tight">Enterprise-Grade Call Center</h1>
                        <div className="flex items-center gap-2 mt-1">
                            <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-xs font-semibold tracking-wide uppercase">
                                Service Cloud
                            </span>
                            <span className="text-xs text-gray-500">Live monitoring & agent takeover</span>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-6">
                    {/* Active Calls Dropdown */}
                    <select
                        className="input min-w-[200px] text-sm py-2"
                        value={focusedCallId || ""}
                        onChange={handleSelectCall}
                    >
                        <option value="">Select a Call to Monitor ({activeCalls.length})</option>
                        {activeCalls.map(call => (
                            <option key={call.call_id} value={call.call_id}>
                                {call.business_type} agent - {call.call_id.substring(0, 8)}...
                            </option>
                        ))}
                    </select>

                    <div className={`flex items-center gap-2 glass-card px-4 py-2 rounded-full border shadow-sm ${isConnected ? 'border-emerald-500/20' : 'border-red-500/20'}`}>
                        <span className="relative flex h-2.5 w-2.5">
                            {isConnected && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
                            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
                        </span>
                        <span className="text-sm font-semibold text-white tracking-wide">
                            {isConnected ? 'System Online' : 'Connecting...'}
                        </span>
                    </div>
                </div>
            </header>

            {/* Main Content Grid */}
            <div className={`flex-1 min-h-0 grid grid-cols-12 gap-6 relative transition-opacity duration-300 ${!focusedCallId ? 'opacity-50 pointer-events-none' : ''}`}>

                {/* Background decorative elements */}
                <div className="absolute top-[-100px] left-[-100px] w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
                <div className="absolute bottom-[-100px] right-[-100px] w-96 h-96 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

                {/* LEFT: Live Interaction Panel */}
                <div className="col-span-12 lg:col-span-4 flex flex-col glass-card shadow-2xl overflow-hidden relative z-10">
                    <div className="p-4 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                        <h2 className="font-bold text-white tracking-wide">Live Interaction</h2>
                        <span className="text-xs text-gray-400">Sentiment: <span className="text-yellow-400 font-medium tracking-wide">Neutral 😐</span></span>
                    </div>

                    <div ref={scrollRef} className="flex-1 p-6 overflow-y-auto flex flex-col gap-4">
                        {transcript.length === 0 ? (
                            <div className="text-center text-gray-500 text-sm mt-10">Waiting for conversation to begin...</div>
                        ) : (
                            transcript.map((msg, idx) => (
                                <div key={idx} className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-start' : 'items-end'}`}>
                                    {msg.role === 'user' ? (
                                        <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold ml-1">Customer</span>
                                    ) : (
                                        <span className="text-[10px] text-blue-400 uppercase tracking-widest font-bold mr-1 flex items-center gap-1">
                                            {focusedCall?.agent_id || "AI Agent"} <span className="text-base">🤖</span>
                                        </span>
                                    )}
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
                            <span className="text-xs text-emerald-400 font-bold tracking-wider uppercase">Monitoring...</span>
                        </div>
                    </div>
                </div>

                {/* MIDDLE: Customer 360 & Timeline */}
                <div className="col-span-12 lg:col-span-4 flex flex-col gap-6 relative z-10">
                    {/* Customer 360 */}
                    <div className="glass-card flex-1 flex flex-col shadow-xl">
                        <div className="p-4 border-b border-white/5 bg-white/[0.02]">
                            <h2 className="font-bold text-white tracking-wide">Customer 360</h2>
                        </div>
                        <div className="p-6 flex flex-col gap-6">
                            <div className="flex items-center gap-4">
                                <div className="w-14 h-14 rounded-full bg-gradient-to-r from-orange-400 to-pink-500 p-[2px]">
                                    <div className="w-full h-full bg-[#0b0c10] rounded-full flex items-center justify-center text-xl font-bold text-white">
                                        {fakeCustomer.initials}
                                    </div>
                                </div>
                                <div>
                                    <h3 className="text-lg font-bold text-white tracking-tight">{fakeCustomer.name}</h3>
                                    <span className="text-xs font-semibold text-yellow-500 bg-yellow-500/10 px-2 py-0.5 rounded border border-yellow-500/20 uppercase tracking-wider">Tier: {fakeCustomer.tier}</span>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4 text-sm mt-2">
                                <div><div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Phone</div><div className="font-mono text-gray-300">{fakeCustomer.phone}</div></div>
                                <div><div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Email</div><div className="font-medium text-blue-400">{fakeCustomer.email}</div></div>
                                <div><div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Status</div><div className="font-medium text-gray-200">{fakeCustomer.status}</div></div>
                                <div><div className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Duration</div><div className="font-medium text-gray-200">{focusedCall?.duration_seconds || 0}s</div></div>
                            </div>
                        </div>
                    </div>

                    {/* Recent Timeline */}
                    <div className="glass-card flex-1 flex flex-col shadow-xl">
                        <div className="p-4 border-b border-white/5 bg-white/[0.02]">
                            <h2 className="font-bold text-white tracking-wide">Conversation States (Live)</h2>
                        </div>
                        <div className="p-6 flex-1 overflow-y-auto">
                            <div className="relative pl-6 border-l-2 border-white/5 space-y-6">
                                {statesVisited.length === 0 ? (
                                    <div className="text-sm text-gray-500 italic">No states visited yet</div>
                                ) : (
                                    statesVisited.map((state, idx) => (
                                        <div key={idx} className="relative">
                                            <div className="absolute -left-[29px] top-1 w-3 h-3 bg-blue-500 rounded-full ring-4 ring-[#0b0c10]" />
                                            <div className="flex justify-between items-start mb-1">
                                                <div className="font-bold text-sm text-gray-200 capitalize">{state.replace(/_/g, " ")}</div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* RIGHT: AI Assistant & Summary */}
                <div className="col-span-12 lg:col-span-4 flex flex-col gap-6 relative z-10">
                    {/* Gemini AI Assistant */}
                    <div className="glass-card p-6 flex flex-col gap-6 shadow-xl">
                        <div className="flex items-center gap-2 mb-2">
                            <h2 className="font-bold text-white tracking-wide text-lg">AI Toolkit</h2>
                        </div>
                        <div>
                            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Suggested Context</h3>
                            <div className="text-sm text-gray-400 bg-white/[0.02] border border-white/5 p-3 rounded-xl italic">
                                Agent {focusedCall?.agent_id || "..."} handling a {focusedCall?.business_type || "..."} call.
                            </div>
                        </div>
                    </div>

                    {/* Real-time Summary */}
                    <div className="glass-card flex-1 p-6 shadow-xl flex flex-col">
                        <h2 className="font-bold text-white tracking-wide mb-4">Live Summary</h2>
                        <ul className="list-disc pl-5 space-y-3 text-sm text-gray-300">
                            <li>Turns advanced: {focusedCall?.total_turns || 0}</li>
                            <li>Current State: {focusedCall?.current_state || "initiating"}</li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* BOTTOM: Softphone Controls */}
            <div className={`h-[72px] bg-[#161b22]/90 backdrop-blur-xl border border-white/10 rounded-2xl flex items-center justify-between px-8 shrink-0 shadow-2xl z-20 sticky bottom-0 transition-opacity duration-300 ${!focusedCallId ? 'opacity-50 pointer-events-none' : ''}`}>
                <div className="flex items-center gap-4">
                    <h3 className="text-white font-bold tracking-wide">Softphone Controls</h3>
                </div>

                <div className="flex items-center gap-10">
                    <button className="flex flex-col items-center gap-1.5 text-gray-400 hover:text-white transition-colors group">
                        <div className="p-2 rounded-full group-hover:bg-white/10 transition-colors">
                            <Mic className="w-5 h-5" />
                        </div>
                        <span className="text-[10px] uppercase font-bold tracking-widest opacity-80">Mute</span>
                    </button>
                    <button className="flex flex-col items-center gap-1.5 text-gray-400 hover:text-white transition-colors group">
                        <div className="p-2 rounded-full group-hover:bg-white/10 transition-colors">
                            <PhoneOff className="w-5 h-5" />
                        </div>
                        <span className="text-[10px] uppercase font-bold tracking-widest opacity-80">Hold</span>
                    </button>
                    <button className="flex flex-col items-center gap-1.5 text-gray-400 hover:text-white transition-colors group">
                        <div className="p-2 rounded-full group-hover:bg-white/10 transition-colors">
                            <ArrowRightLeft className="w-5 h-5" />
                        </div>
                        <span className="text-[10px] uppercase font-bold tracking-widest opacity-80">Transfer</span>
                    </button>
                </div>

                <div className="flex items-center gap-8">
                    <button
                        onClick={() => focusedCallId && triggerTakeover(focusedCallId)}
                        className="bg-red-600 hover:bg-red-500 text-white px-8 py-3 rounded-lg flex items-center gap-2 font-black tracking-widest text-sm transition-transform hover:scale-105 active:scale-95 shadow-lg shadow-red-500/20"
                    >
                        <AlertTriangle className="w-4 h-4" />
                        TAKE OVER
                    </button>

                    <div className="text-right flex flex-col justify-center">
                        <div className="text-[11px] text-emerald-400 font-bold tracking-widest uppercase flex items-center gap-1.5 justify-end">
                            <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                            Connected
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
