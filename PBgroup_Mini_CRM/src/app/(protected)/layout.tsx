import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex-1 flex flex-col bg-slate-50 dark:bg-zinc-900">
                <Header />
                <main className="flex-1 p-6 overflow-auto">
                    {children}
                </main>
            </div>
        </div>
    )
}
