"use client"

import { ColumnDef } from "@tanstack/react-table"
import { Client, ClientStatus } from "@prisma/client"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ExternalLink, FileText } from "lucide-react"
import { CLIENT_STATUS_LABELS } from "@/lib/dict"

export const columns: ColumnDef<Client>[] = [
    {
        accessorKey: "name",
        header: "Клиент",
        cell: ({ row }) => {
            return (
                <Link
                    href={`/stats/${row.original.id}`}
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
            return <Badge variant="outline">{CLIENT_STATUS_LABELS[status]}</Badge>
        },
    },
    {
        id: "actions",
        header: "Перейти",
        cell: ({ row }) => {
            return (
                <div className="flex gap-2">
                    <Link href={`/stats/${row.original.id}`}>
                        <Button variant="ghost" size="sm">
                            <ExternalLink className="w-4 h-4 mr-2" />
                            Статистика
                        </Button>
                    </Link>
                    <Link href={`/stats/${row.original.id}/details`}>
                        <Button variant="ghost" size="sm">
                            <FileText className="w-4 h-4 mr-2" />
                            Детали
                        </Button>
                    </Link>
                </div>
            )
        }
    }
]
