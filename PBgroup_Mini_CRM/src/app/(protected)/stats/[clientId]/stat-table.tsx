"use client"

import * as React from "react"
import { StatRow } from "@prisma/client"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { useRouter } from "next/navigation"

interface StatTableProps {
    rows: StatRow[]
    clientId: string
    isViewer: boolean
}

// Columns: Date, Spend, Reach, Clicks, Leads, Sales, Revenue, CPL(c), ROI(c), Action
export function StatTable({ rows, clientId, isViewer }: StatTableProps) {
    const router = useRouter()

    async function handleUpdate(rowId: string, field: string, value: any) {
        if (isViewer) return
        try {
            const res = await fetch(`/api/stats/${rowId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ [field]: value })
            })
            if (!res.ok) throw new Error("Failed")
            toast.success("Saved")
            router.refresh()
        } catch (e) {
            toast.error("Error saving")
        }
    }

    async function handleAddRow() {
        if (isViewer) return
        try {
            const res = await fetch(`/api/clients/${clientId}/stats`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    date: new Date(),
                    spend: 0,
                    reach: 0,
                    clicks: 0,
                    leads: 0,
                    sales: 0,
                    revenue: 0,
                })
            })
            if (!res.ok) throw new Error("Failed")
            toast.success("Row added")
            router.refresh()
        } catch (e) {
            toast.error("Error adding row")
        }
    }

    // Sort by date desc
    const sortedRows = [...rows].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())

    return (
        <div className="space-y-4">
            {!isViewer && <Button onClick={handleAddRow}>Add Row</Button>}
            <div className="rounded-md border bg-white dark:bg-zinc-950 overflow-x-auto">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[150px]">Date</TableHead>
                            <TableHead>Spend</TableHead>
                            <TableHead>Reach</TableHead>
                            <TableHead>Clicks</TableHead>
                            <TableHead>Leads</TableHead>
                            <TableHead>CPL</TableHead>
                            <TableHead>Sales</TableHead>
                            <TableHead>Revenue</TableHead>
                            <TableHead>ROI %</TableHead>
                            <TableHead>Action</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {sortedRows.map(row => {
                            const cpl = row.leads > 0 ? (row.spend / row.leads).toFixed(2) : "-"
                            const roi = row.spend > 0 ? ((row.revenue - row.spend) / row.spend * 100).toFixed(2) : "-"

                            return (
                                <TableRow key={row.id}>
                                    <TableCell>
                                        <Input
                                            type="date"
                                            value={new Date(row.date).toISOString().split('T')[0]}
                                            onChange={(e) => handleUpdate(row.id, "date", e.target.value)}
                                            disabled={isViewer}
                                            className="w-[140px]"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Input
                                            type="number"
                                            value={row.spend}
                                            onChange={(e) => handleUpdate(row.id, "spend", parseFloat(e.target.value) || 0)}
                                            disabled={isViewer}
                                            className="w-24"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Input
                                            type="number"
                                            value={row.reach}
                                            onChange={(e) => handleUpdate(row.id, "reach", parseInt(e.target.value) || 0)}
                                            disabled={isViewer}
                                            className="w-24"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Input
                                            type="number"
                                            value={row.clicks}
                                            onChange={(e) => handleUpdate(row.id, "clicks", parseInt(e.target.value) || 0)}
                                            disabled={isViewer}
                                            className="w-24"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Input
                                            type="number"
                                            value={row.leads}
                                            onChange={(e) => handleUpdate(row.id, "leads", parseInt(e.target.value) || 0)}
                                            disabled={isViewer}
                                            className="w-24"
                                        />
                                    </TableCell>
                                    <TableCell className="font-mono">{cpl}</TableCell>
                                    <TableCell>
                                        <Input
                                            type="number"
                                            value={row.sales}
                                            onChange={(e) => handleUpdate(row.id, "sales", parseInt(e.target.value) || 0)}
                                            disabled={isViewer}
                                            className="w-24"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Input
                                            type="number"
                                            value={row.revenue}
                                            onChange={(e) => handleUpdate(row.id, "revenue", parseFloat(e.target.value) || 0)}
                                            disabled={isViewer}
                                            className="w-24"
                                        />
                                    </TableCell>
                                    <TableCell className={parseInt(roi) > 0 ? "text-green-600 font-bold" : "text-red-500 font-bold"}>
                                        {roi}%
                                    </TableCell>
                                    <TableCell>
                                        <Input
                                            placeholder="Action..."
                                            value={row.notes || ""}
                                            onChange={(e) => {
                                                // Debounce? Or onBlur?
                                                // For text inputs onBlur is better for performance
                                            }}
                                            onBlur={(e) => handleUpdate(row.id, "notes", e.target.value)}
                                            disabled={isViewer}
                                        />
                                    </TableCell>
                                </TableRow>
                            )
                        })}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}
