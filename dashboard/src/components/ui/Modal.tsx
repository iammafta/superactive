"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title?: string;
    children: React.ReactNode;
    width?: string;
}

export default function Modal({ isOpen, onClose, title, children, width = "w-[500px]" }: ModalProps) {
    // Close on Escape key
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && isOpen) {
                onClose();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 bg-black/70 flex items-center justify-center z-[100]"
            onClick={onClose}
        >
            <div
                className={`glass-card p-8 ${width} max-h-[90vh] overflow-y-auto relative`}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Close Button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 bg-transparent border-none cursor-pointer text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1"
                    aria-label="Close modal"
                >
                    <X className="w-5 h-5" />
                </button>

                {title && <h2 className="text-xl font-bold mb-5 pr-8">{title}</h2>}

                {children}
            </div>
        </div>
    );
}
