"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { API_BASE_URL } from "@/lib/api";

export type CallLogSummary = {
    call_id: string;
    agent_id: string;
    business_type: string;
    tenant_id: string;
    started_at: string;
    duration_seconds: number;
    current_state: string;
    total_turns: number;
};

export type TranscriptMessage = {
    role: "user" | "agent";
    text: string;
    ts: string;
};

function getToken(): string | null {
    if (typeof document === "undefined") return null;
    const match = document.cookie.match(/(?:^|; )superactive_auth=([^;]*)/);
    return match ? match[1] : null;
}

function getWsUrl(): string {
    // Derive WebSocket URL from API_BASE_URL
    const base = API_BASE_URL.replace(/\/api$/, "");
    const wsScheme = base.startsWith("https") ? "wss" : "ws";
    const host = base.replace(/^https?:\/\//, "");
    const token = getToken();
    return `${wsScheme}://${host}/ws/monitor${token ? `?token=${token}` : ""}`;
}

export function useCallMonitor() {
    const [activeCalls, setActiveCalls] = useState<CallLogSummary[]>([]);
    const [focusedCallId, setFocusedCallId] = useState<string | null>(null);
    const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
    const [statesVisited, setStatesVisited] = useState<string[]>([]);
    const [isConnected, setIsConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const focusedCallIdRef = useRef<string | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const reconnectAttemptRef = useRef(0);
    const mountedRef = useRef(true);

    useEffect(() => {
        focusedCallIdRef.current = focusedCallId;
    }, [focusedCallId]);

    const handleMessage = useCallback((event: MessageEvent) => {
        try {
            const message = JSON.parse(event.data);
            const { type, call_id, data } = message;
            const currentFocus = focusedCallIdRef.current;

            if (type === "active_calls_update") {
                setActiveCalls(data.calls || []);
            } else if (type === "call_started") {
                setActiveCalls(prev => {
                    if (!prev.find(c => c.call_id === data.call_id)) {
                        return [...prev, data];
                    }
                    return prev;
                });
            } else if (type === "call_ended") {
                setActiveCalls(prev => prev.filter(c => c.call_id !== call_id));
            } else if (type === "transcript_history") {
                if (call_id === currentFocus) {
                    setTranscript(data.transcript || []);
                    setStatesVisited(data.states_visited || []);
                }
            } else if (type === "transcript") {
                if (call_id === currentFocus) {
                    setTranscript(prev => [...prev, data]);
                }
            } else if (type === "state_transition") {
                if (call_id === currentFocus) {
                    setStatesVisited(data.states_visited || []);
                }
                setActiveCalls(prev => prev.map(c =>
                    c.call_id === call_id ? { ...c, current_state: data.to_state } : c
                ));
            }
        } catch (err) {
            console.error("WS Parse error", err);
        }
    }, []);

    const connect = useCallback(() => {
        if (!mountedRef.current) return;

        const wsUrl = getWsUrl();
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
            reconnectAttemptRef.current = 0;
            // Re-subscribe to focused call after reconnect
            const currentFocus = focusedCallIdRef.current;
            if (currentFocus) {
                ws.send(JSON.stringify({ action: "subscribe", call_id: currentFocus }));
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
            if (!mountedRef.current) return;
            // Exponential backoff reconnect: 1s, 2s, 4s, 8s, max 30s
            const attempt = reconnectAttemptRef.current;
            const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
            reconnectAttemptRef.current = attempt + 1;
            console.log(`Monitor WS disconnected. Reconnecting in ${delay}ms (attempt ${attempt + 1})`);
            reconnectTimeoutRef.current = setTimeout(connect, delay);
        };

        ws.onerror = (err) => console.error("Monitor WS Error:", err);
        ws.onmessage = handleMessage;
    }, [handleMessage]);

    useEffect(() => {
        mountedRef.current = true;
        connect();

        return () => {
            mountedRef.current = false;
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [connect]);

    const subscribeToCall = useCallback((callId: string) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            if (focusedCallIdRef.current) {
                wsRef.current.send(JSON.stringify({ action: "unsubscribe" }));
            }
            setFocusedCallId(callId);
            setTranscript([]);
            setStatesVisited([]);
            wsRef.current.send(JSON.stringify({ action: "subscribe", call_id: callId }));
        }
    }, []);

    const triggerTakeover = async (callId: string) => {
        try {
            const token = getToken();
            const res = await fetch(`${API_BASE_URL}/calls/${callId}/takeover`, {
                method: "POST",
                headers: {
                    ...(token ? { "Authorization": `Bearer ${token}` } : {})
                }
            });
            if (!res.ok) throw new Error("Takeover failed");
            return await res.json();
        } catch (error) {
            console.error(error);
            alert("Failed to initiate takeover");
        }
    };

    return {
        activeCalls,
        focusedCallId,
        transcript,
        statesVisited,
        isConnected,
        subscribeToCall,
        triggerTakeover
    };
}
