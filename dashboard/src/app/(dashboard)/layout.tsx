import Sidebar from "@/components/Sidebar";
import ErrorBoundary from "@/components/ErrorBoundary";
import { Toaster } from "sonner";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
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
                <ErrorBoundary>
                    {children}
                </ErrorBoundary>
            </main>
            <Toaster
                theme="dark"
                position="bottom-right"
                toastOptions={{
                    style: {
                        background: "rgba(17, 24, 39, 0.95)",
                        border: "1px solid rgba(55, 65, 81, 0.5)",
                        color: "#f1f5f9",
                    },
                }}
            />
        </div>
    );
}
