"use client";

import React from "react";

interface ErrorBoundaryProps {
    children: React.ReactNode;
    fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

export default class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error("ErrorBoundary caught:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                this.props.fallback || (
                    <div className="flex flex-col items-center justify-center h-full gap-4 p-12">
                        <div className="text-4xl">⚠️</div>
                        <h2 className="text-lg font-bold text-white">Something went wrong</h2>
                        <p className="text-sm text-gray-400 text-center max-w-md">
                            {this.state.error?.message || "An unexpected error occurred."}
                        </p>
                        <button
                            onClick={() => this.setState({ hasError: false, error: null })}
                            className="btn-primary px-6 py-2 text-sm"
                        >
                            Try Again
                        </button>
                    </div>
                )
            );
        }

        return this.props.children;
    }
}
