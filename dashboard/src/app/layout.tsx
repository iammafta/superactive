import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
    title: "Superactive — AI Voice Agent Platform",
    description: "Configure and monitor your AI voice agents in real-time",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <head>
                <link
                    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body className="antialiased">
                <div style={{ display: "flex", minHeight: "100vh" }}>
                    <Sidebar />
                    <main
                        style={{
                            flex: 1,
                            marginLeft: 240,
                            padding: "28px 32px",
                            minHeight: "100vh",
                        }}
                    >
                        {children}
                    </main>
                </div>
            </body>
        </html>
    );
}
