"use client"

import { ColumnDef } from "@tanstack/react-table"
import { Client, ClientStatus, User } from "@prisma/client"
import { Badge } from "@/components/ui/badge"
import { format } from "date-fns"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ArrowUpDown } from "lucide-react"

export type ClientWithRelations = Client & {
    targetologist: { fullName: string } | null
}

export const columns: ColumnDef<ClientWithRelations>[] = [
    {
        accessorKey: "name",
        header: ({ column }) => {
            return (
                <Button
                    variant="ghost"
                    onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                >
                    Name
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
            )
        },
        cell: ({ row }) => (
            <Link href={`/clients/${row.original.id}`} className="font-medium hover:underline text-blue-600">
                {row.getValue("name")}
            </Link>
        ),
    },
    {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => {
            const status = row.getValue("status") as ClientStatus
            const colors = {
                [ClientStatus.IN_PROGRESS]: "bg-green-100 text-green-800",
                [ClientStatus.STOPPED]: "bg-red-100 text-red-800",
                [ClientStatus.WAITING_RENEWAL]: "bg-yellow-100 text-yellow-800",
                [ClientStatus.REGISTRATION]: "bg-blue-100 text-blue-800",
                [ClientStatus.ANALYSIS]: "bg-purple-100 text-purple-800",
            }
            return <Badge className={colors[status]}>{status}</Badge>
        },
    },
    {
        accessorKey: "targetologist.fullName",
        header: "Targetologist",
        cell: ({ row }) => row.original.targetologist?.fullName || "-",
    },
    {
        accessorKey: "daysInWork",
        header: "Days",
        cell: ({ row }) => {
            const start = new Date(row.original.startedAt)
            const diff = Math.ceil((new Date().getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
            return diff
        }
    },
    {
        accessorKey: "createdAt",
        header: "Created",
        cell: ({ row }) => format(new Date(row.original.createdAt), "dd.MM.yyyy"),
    },
]
