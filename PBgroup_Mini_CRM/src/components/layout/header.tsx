"use client"

import { useSession } from "next-auth/react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

export function Header() {
    const { data: session } = useSession()

    return (
        <header className="h-16 border-b flex items-center justify-between px-6 bg-white dark:bg-zinc-950 dark:border-zinc-800">
            <div>
                {/* Breadcrumbs could go here */}
            </div>
            <div className="flex items-center gap-4">
                <div className="text-right hidden sm:block">
                    <p className="text-sm font-medium">{session?.user?.name}</p>
                    <p className="text-xs text-muted-foreground">{session?.user?.role}</p>
                </div>
                <Avatar>
                    <AvatarImage src="" />
                    <AvatarFallback>{session?.user?.name?.[0] || "U"}</AvatarFallback>
                </Avatar>
            </div>
        </header>
    )
}
