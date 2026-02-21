import { useState, useRef, useEffect } from "react";
import { X, Send, User, Bot, Loader2, Sparkles, MessageSquare } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function TestChatModal({
    isOpen,
    onClose,
    agentName,
}: {
    isOpen: boolean;
    onClose: () => void;
    agentId: string;
    agentName: string;
}) {
    const [messages, setMessages] = useState<{ role: "user" | "agent"; text: string }[]>([]);
    const [input, setInput] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when messages update
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isTyping]);

    // Reset messages when modal opens
    useEffect(() => {
        if (isOpen) {
            setMessages([
                { role: "agent", text: "Hi! I'm the simulated chat version of your exact agent configuration. Note: The backend for pure text-simulation is still in development, but you can see how the UI looks right now!" }
            ]);
        }
    }, [isOpen]);

    const handleSend = async () => {
        if (!input.trim()) return;
        const userText = input.trim();
        setInput("");

        // Add user message
        setMessages(prev => [...prev, { role: "user", text: userText }]);
        setIsTyping(true);

        // TODO: Wire up to real /api/simulate-chat backend
        setTimeout(() => {
            setMessages(prev => [...prev, { role: "agent", text: "I acknowledge your input: '" + userText + "'. I am waiting for textual state-machine handlers to be wired to the backend API!" }]);
            setIsTyping(false);
        }, 1500);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

            <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 20 }}
                className="relative w-full max-w-lg bg-gray-900 border border-gray-700/50 rounded-2xl shadow-2xl shadow-blue-900/20 overflow-hidden flex flex-col"
                style={{ height: "600px" }}
            >
                {/* Header */}
                <div className="px-5 py-4 border-b border-gray-800 bg-gray-950/50 backdrop-blur-md flex justify-between items-center z-10">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-blue-400 relative">
                            <Bot className="w-5 h-5" />
                            <div className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 border-2 border-gray-950 rounded-full" />
                        </div>
                        <div>
                            <h2 className="text-white font-bold leading-tight">{agentName}</h2>
                            <p className="text-xs text-blue-400 font-medium flex items-center gap-1">
                                <Sparkles className="w-3 h-3" /> Chat Simulator Payload
                            </p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-5 pb-8 space-y-6">
                    {messages.length === 0 && (
                        <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-3">
                            <MessageSquare className="w-8 h-8 opacity-20" />
                            <p className="text-sm">Initiate conversation to begin simulation.</p>
                        </div>
                    )}

                    {messages.map((msg, i) => (
                        <div key={i} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                            <div className={`flex items-end gap-2 max-w-[85%] ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                                <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center border shadow-sm ${msg.role === "user" ? "bg-gray-800 border-gray-700 text-gray-400" : "bg-blue-600/20 border-blue-500/30 text-blue-400"}`}>
                                    {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                                </div>
                                <div className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${msg.role === "user" ? "bg-blue-600 text-white rounded-br-sm shadow-blue-900/50 shadow-lg" : "bg-gray-800 border border-gray-700 text-gray-200 rounded-bl-sm"}`}>
                                    {msg.text}
                                </div>
                            </div>
                        </div>
                    ))}

                    {isTyping && (
                        <div className="flex w-full justify-start">
                            <div className="flex items-end gap-2 max-w-[85%] flex-row">
                                <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center border shadow-sm bg-blue-600/20 border-blue-500/30 text-blue-400">
                                    <Bot className="w-4 h-4" />
                                </div>
                                <div className="px-4 py-3 rounded-2xl text-sm bg-gray-800 border border-gray-700 text-gray-400 rounded-bl-sm flex items-center gap-1.5 h-10 w-16 justify-center">
                                    <motion.div animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} className="w-1.5 h-1.5 bg-gray-500 rounded-full" />
                                    <motion.div animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }} className="w-1.5 h-1.5 bg-gray-500 rounded-full" />
                                    <motion.div animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }} className="w-1.5 h-1.5 bg-gray-500 rounded-full" />
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4 bg-gray-950/80 backdrop-blur-md border-t border-gray-800">
                    <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="relative flex items-center group">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Type a message to simulate context..."
                            className="w-full bg-gray-900 border border-gray-700/80 rounded-xl pl-4 pr-12 py-3.5 text-sm text-white focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all shadow-inner placeholder:text-gray-600"
                        />
                        <button type="submit" disabled={!input.trim() || isTyping} className="absolute right-2 p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-lg transition-colors flex items-center justify-center group-focus-within:shadow-md shadow-blue-500/20">
                            {isTyping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4 translate-x-[-1px] translate-y-[1px]" />}
                        </button>
                    </form>
                    <p className="text-center text-[10px] text-gray-600 font-mono tracking-tight mt-3">SUPERACTIVE LOGIC INFERENCE LAYER</p>
                </div>
            </motion.div>
        </div>
    );
}
