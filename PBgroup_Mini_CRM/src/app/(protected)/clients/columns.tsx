"use client"

import { ColumnDef } from "@tanstack/react-table"
import { Client, ClientStatus, ClientAssignment, User } from "@prisma/client"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { differenceInDays } from "date-fns"
import { CLIENT_STATUS_LABELS } from "@/lib/dict"

// Extended type to include relations
export type ClientWithRelations = Client & {
    assignments: (ClientAssignment & { user: { fullName: string } })[]
    targetologist: { fullName: string } | null
    projectManager: { fullName: string } | null
    sources: { sourceType: string }[]
    pauses: { startDate: Date; endDate: Date | null }[]
}

export const columns: ColumnDef<ClientWithRelations>[] = [
    {
        accessorKey: "name",
        header: "Имя клиента",
        cell: ({ row }) => {
            return (
                <Link
                    href={`/clients/${row.original.id}`}
                    className="font-medium hover:underline text-blue-600 dark:text-blue-400"
                >
                    {row.getValue("name")}
                </Link>
            )
        },
    },
    {
        accessorKey: "status",
        header: "Статус",
        cell: ({ row }) => {
            const status = row.getValue("status") as ClientStatus
            const label = CLIENT_STATUS_LABELS[status] || status
            return <Badge variant="outline">{label}</Badge>
        },
    },
    {
        accessorKey: "targetologist", // Custom getter
        header: "Таргетолог",
        cell: ({ row }) => {
            const t = row.original.targetologist
            if (t) return <span>{t.fullName}</span>
            return <span className="text-muted-foreground">-</span>
        }
    },
    {
        accessorKey: "projectManager", // Custom getter
        header: "Проджект",
        cell: ({ row }) => {
            const pm = row.original.projectManager
            if (pm) return <span>{pm.fullName}</span>
            return <span className="text-muted-foreground">-</span>
        }
    },
    {
        accessorKey: "sources",
        header: "Источник",
        cell: ({ row }) => {
            // Display joined source types or utmSource?
            // The user screenshot had "Targetolog / Source".
            // But here we implement a dedicated column.
            const sources = row.original.sources?.map(s => s.sourceType).join(", ")
            const utm = row.original.utmSource

            if (sources) return <Badge variant="secondary" className="text-xs">{sources}</Badge>
            if (utm) return <span className="text-xs text-muted-foreground">{utm}</span>
            return <span className="text-muted-foreground">-</span>
        }
    },
    {
        id: "daysInWork",
        header: "В работе",
        cell: ({ row }) => {
            const paymentDate = row.original.paymentDate
            if (!paymentDate) return <span className="text-muted-foreground">-</span>

            const today = new Date()
            const totalDays = differenceInDays(today, new Date(paymentDate))

            const pauses = row.original.pauses || []
            let pauseDays = 0

            pauses.forEach(p => {
                const start = new Date(p.startDate)
                // If endDate is null, it's active until now
                const end = p.endDate ? new Date(p.endDate) : today
                // Add +1 to include both start and end days
                const itemsDuration = differenceInDays(end, start) + 1
                if (itemsDuration > 0) pauseDays += itemsDuration
            })

            const finalDays = Math.max(0, totalDays - pauseDays)

            return (
                <div className="flex flex-col text-sm">
                    <span className="font-medium">{finalDays} дн.</span>
                    {pauseDays > 0 && <span className="text-xs text-muted-foreground">(Пауза: {pauseDays})</span>}
                </div>
            )
        }
    },
    {
        accessorKey: "city",
        header: "Город",
    }
]
