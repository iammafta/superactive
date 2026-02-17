
"use client";

import { useState } from "react";
import { X, Phone, Loader2 } from "lucide-react";
import { triggerCall } from "@/lib/api";

interface TestCallModalProps {
    isOpen: boolean;
    onClose: () => void;
    agentId: string;
    agentName: string;
}

export default function TestCallModal({ isOpen, onClose, agentId, agentName }: TestCallModalProps) {
    const [phoneNumber, setPhoneNumber] = useState("");
    const [status, setStatus] = useState<"idle" | "calling" | "success" | "error">("idle");
    const [errorMsg, setErrorMsg] = useState("");

    if (!isOpen) return null;

    const handleCall = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatus("calling");
        setErrorMsg("");

        try {
            await triggerCall(phoneNumber, agentId);
            setStatus("success");
        } catch (err: any) {
            setStatus("error");
            setErrorMsg(err.message || "Failed to initiate call");
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <div className="bg-[#1e1e1e] border border-white/10 rounded-xl w-full max-w-md shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                        <Phone className="w-5 h-5 text-blue-400" />
                        Test Agent: <span className="text-blue-400">{agentName}</span>
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6">
                    {status === "success" ? (
                        <div className="text-center py-4">
                            <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                                <Phone className="w-8 h-8 text-green-500" />
                            </div>
                            <h4 className="text-xl font-bold text-white mb-2">Call Initiated!</h4>
                            <p className="text-gray-400 mb-6">
                                Calling <strong>{phoneNumber}</strong>...<br />
                                Check the "Call History" page for details.
                            </p>
                            <button
                                onClick={onClose}
                                className="w-full py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    ) : (
                        <form onSubmit={handleCall}>
                            <div className="mb-6">
                                <label className="block text-sm font-medium text-gray-400 mb-2">
                                    Phone Number
                                </label>
                                <input
                                    type="tel"
                                    required
                                    placeholder="+1 (555) 000-0000"
                                    value={phoneNumber}
                                    onChange={(e) => setPhoneNumber(e.target.value)}
                                    className="w-full px-4 py-3 bg-black/20 border border-white/10 rounded-lg text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                                />
                                <p className="text-xs text-gray-500 mt-2">
                                    Must include country code (e.g. +1)
                                </p>
                            </div>

                            {status === "error" && (
                                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                                    {errorMsg}
                                </div>
                            )}

                            <div className="flex justify-end gap-3">
                                <button
                                    type="button"
                                    onClick={onClose}
                                    className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={status === "calling" || !phoneNumber}
                                    className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                >
                                    {status === "calling" ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            Calling...
                                        </>
                                    ) : (
                                        "Call Now"
                                    )}
                                </button>
                            </div>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
}
