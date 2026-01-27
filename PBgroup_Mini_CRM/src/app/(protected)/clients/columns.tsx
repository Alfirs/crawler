"use client"

import { ColumnDef } from "@tanstack/react-table"
import { Client, ClientStatus, ClientAssignment, User } from "@prisma/client"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { differenceInDays } from "date-fns"

// Extended type to include relations
export type ClientWithRelations = Client & {
    assignments: (ClientAssignment & { user: { fullName: string } })[]
    targetologist: { fullName: string } | null
}

export const columns: ColumnDef<ClientWithRelations>[] = [
    {
        accessorKey: "name",
        header: "Client Name",
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
        header: "Status",
        cell: ({ row }) => {
            const status = row.getValue("status") as ClientStatus
            return <Badge variant="outline">{status}</Badge>
        },
    },
    {
        accessorKey: "targetologist", // Custom getter
        header: "Targetologist",
        cell: ({ row }) => {
            // Use targetologist relation OR assignments?
            // Requirement says table column: "Таргетолог (пользователь)"
            // And we have specific field `targetologist`.
            const t = row.original.targetologist
            if (t) return <span>{t.fullName}</span>

            // Fallback to assignments if targetologist field is empty?
            // Just show targetologist field as per schema design.
            return <span className="text-muted-foreground">-</span>
        }
    },
    {
        id: "daysInWork",
        header: "Days in Work",
        cell: ({ row }) => {
            const days = differenceInDays(new Date(), new Date(row.original.startedAt))
            return <span>{days} days</span>
        }
    },
    {
        accessorKey: "city",
        header: "City",
    }
]
