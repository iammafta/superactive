"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [businessName, setBusinessName] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const router = useRouter();

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            const res = await fetch("http://localhost:8765/api/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ email, password, business_name: businessName }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Registration failed");
            }

            // Token is now set as HttpOnly cookie by the server
            await res.json();

            router.push("/");
            router.refresh();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA]">
            <div className="w-full max-w-md bg-white p-10 rounded-2xl shadow-xl border border-gray-100">
                <div className="text-center mb-10">
                    <h1 className="text-3xl font-extrabold tracking-tight text-gray-900 mb-2">
                        Create your account
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Start deploying AI voice agents in minutes
                    </p>
                </div>

                {error && (
                    <div className="mb-6 p-4 bg-red-50 text-red-600 rounded-xl text-sm font-medium border border-red-100">
                        {error}
                    </div>
                )}

                <form onSubmit={handleRegister} className="space-y-5">
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Business Name
                        </label>
                        <input
                            type="text"
                            required
                            value={businessName}
                            onChange={(e) => setBusinessName(e.target.value)}
                            className="w-full px-4 py-3 bg-gray-50 text-gray-900 placeholder-gray-400 border border-gray-200 rounded-xl focus:ring-2 focus:ring-black focus:border-black outline-none transition-all"
                            placeholder="Acme Corp"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Email Address
                        </label>
                        <input
                            type="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full px-4 py-3 bg-gray-50 text-gray-900 placeholder-gray-400 border border-gray-200 rounded-xl focus:ring-2 focus:ring-black focus:border-black outline-none transition-all"
                            placeholder="founder@acme.com"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Password
                        </label>
                        <input
                            type="password"
                            required
                            minLength={6}
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full px-4 py-3 bg-gray-50 text-gray-900 placeholder-gray-400 border border-gray-200 rounded-xl focus:ring-2 focus:ring-black focus:border-black outline-none transition-all"
                            placeholder="At least 6 characters"
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-4 bg-black text-white rounded-xl font-bold flex justify-center items-center hover:bg-gray-800 transition-colors disabled:opacity-50 mt-4"
                    >
                        {loading ? "Creating account..." : "Continue"}
                    </button>
                </form>

                <div className="mt-8 text-center text-sm font-medium text-gray-500">
                    Already have an account?{" "}
                    <button
                        onClick={() => router.push("/login")}
                        className="text-black hover:underline"
                    >
                        Sign in
                    </button>
                </div>
            </div>
        </div>
    );
}
