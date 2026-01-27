"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSession, signOut } from "next-auth/react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Role } from "@prisma/client"
import {
    Users,
    BarChart,
    UserCog,
    LogOut,
    LayoutDashboard
} from "lucide-react"

export function Sidebar() {
    const pathname = usePathname()
    const { data: session } = useSession()
    const role = session?.user?.role

    if (!session) return null // Or skeleton

    const links = [
        {
            href: "/clients",
            label: "Clients",
            icon: Users,
        },
        {
            href: "/stats",
            label: "Statistics",
            icon: BarChart,
        },
    ]

    if (role === Role.ADMIN || role === Role.MANAGER) {
        links.push({
            href: "/employees",
            label: "Employees",
            icon: UserCog,
        })
    }

    return (
        <div className="flex flex-col w-64 border-r bg-white h-screen sticky top-0 dark:bg-zinc-950 dark:border-zinc-800">
            <div className="p-6">
                <h1 className="text-xl font-bold flex items-center gap-2">
                    <LayoutDashboard className="h-6 w-6" />
                    PBgroup CRM
                </h1>
            </div>
            <nav className="flex-1 flex flex-col p-4 gap-2">
                {links.map((link) => {
                    const isActive = pathname.startsWith(link.href)
                    return (
                        <Link key={link.href} href={link.href}>
                            <Button
                                variant={isActive ? "secondary" : "ghost"}
                                className={cn(
                                    "w-full justify-start gap-2",
                                    isActive && "bg-slate-100 dark:bg-zinc-800"
                                )}
                            >
                                <link.icon className="h-4 w-4" />
                                {link.label}
                            </Button>
                        </Link>
                    )
                })}
            </nav>
            <div className="p-4 border-t dark:border-zinc-800">
                <Button variant="outline" className="w-full gap-2" onClick={() => signOut()}>
                    <LogOut className="h-4 w-4" />
                    Sign Out
                </Button>
            </div>
        </div>
    )
}
