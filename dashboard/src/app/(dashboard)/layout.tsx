import Sidebar from "@/components/Sidebar";
import ErrorBoundary from "@/components/ErrorBoundary";

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
        </div>
    );
}
