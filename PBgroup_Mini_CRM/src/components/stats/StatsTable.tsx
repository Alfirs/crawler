"use client"

import { useState } from "react"
import { StatRow } from "@prisma/client"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { format } from "date-fns"
import { toast } from "sonner"
import { Plus } from "lucide-react"

interface StatsTableProps {
    initialData: StatRow[]
    clientId: string
    canEdit: boolean
}

export function StatsTable({ initialData, clientId, canEdit }: StatsTableProps) {
    const [data, setData] = useState(initialData)
    const [loading, setLoading] = useState(false)

    const handleUpdate = async (rowId: string, field: keyof StatRow, value: any) => {
        if (!canEdit) return

        // Optimistic update
        const oldData = [...data]
        const updatedData = data.map(row =>
            row.id === rowId ? { ...row, [field]: value } : row
        )
        setData(updatedData)

        try {
            const res = await fetch(`/api/stats/${rowId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ [field]: value }),
            })
            if (!res.ok) throw new Error("Failed to update")
        } catch (error) {
            toast.error("Failed to save")
            setData(oldData) // Revert
        }
    }

    const handleAddRow = async () => {
        setLoading(true)
        try {
            const today = new Date().toISOString()
            const res = await fetch(`/api/clients/${clientId}/stats`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    date: today,
                    spend: 0,
                    reach: 0,
                    clicks: 0,
                    leads: 0,
                    sales: 0,
                    revenue: 0,
                    notes: ""
                }),
            })
            if (!res.ok) throw new Error("Failed to create row")
            const newRow = await res.json()
            setData([newRow, ...data])
            toast.success("Row added")
        } catch (error) {
            toast.error("Error adding row")
        } finally {
            setLoading(false)
        }
    }

    // Helper for safe number input
    const NumberCell = ({ row, field }: { row: StatRow, field: keyof StatRow }) => (
        <Input
            type="number"
            value={row[field] as number}
            className="h-8 w-20"
            disabled={!canEdit}
            onChange={(e) => {
                const val = parseFloat(e.target.value) || 0
                // Update local state is handled by onBlur or simple local state if performance matters
                // For simplicity, let's trigger update on blur
            }}
            onBlur={(e) => {
                const val = parseFloat(e.target.value) || 0
                if (row[field] !== val) {
                    handleUpdate(row.id, field, val)
                }
            }}
            defaultValue={row[field] as number} // Use defaultValue to avoid controlled input lag, but need key change if reorder
            // Better: Controlled with local state? Or just defaultValue and onBlur.
            // defaultValue is safer for "excel like" quick editing without re-rendering everything on every keystroke
            key={`${row.id}-${field}-${row[field]}`}
        />
    )

    return (
        <div className="space-y-4">
            {canEdit && (
                <Button onClick={handleAddRow} disabled={loading}>
                    <Plus className="mr-2 h-4 w-4" /> Add Row
                </Button>
            )}
            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Date</TableHead>
                            <TableHead>Spend</TableHead>
                            <TableHead>Reach</TableHead>
                            <TableHead>Clicks</TableHead>
                            <TableHead>Leads</TableHead>
                            <TableHead>CPL</TableHead>
                            <TableHead>Sales</TableHead>
                            <TableHead>Revenue</TableHead>
                            <TableHead>ROI %</TableHead>
                            <TableHead>ROMI %</TableHead>
                            <TableHead>Notes</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {data.map((row) => {
                            const cpl = row.leads > 0 ? (row.spend / row.leads).toFixed(2) : "-"
                            const roi = row.spend > 0 ? ((row.revenue - row.spend) / row.spend * 100).toFixed(1) : "-"

                            return (
                                <TableRow key={row.id}>
                                    <TableCell>
                                        {canEdit ? (
                                            <Input
                                                type="date"
                                                className="w-32 h-8"
                                                defaultValue={format(new Date(row.date), "yyyy-MM-dd")}
                                                onBlur={(e) => {
                                                    const newDate = new Date(e.target.value).toISOString()
                                                    if (newDate !== row.date.toString()) handleUpdate(row.id, "date", newDate)
                                                }}
                                            />
                                        ) : format(new Date(row.date), "dd.MM.yyyy")}
                                    </TableCell>
                                    <TableCell><NumberCell row={row} field="spend" /></TableCell>
                                    <TableCell><NumberCell row={row} field="reach" /></TableCell>
                                    <TableCell><NumberCell row={row} field="clicks" /></TableCell>
                                    <TableCell><NumberCell row={row} field="leads" /></TableCell>
                                    <TableCell className="bg-slate-50 font-medium">{cpl}</TableCell>
                                    <TableCell><NumberCell row={row} field="sales" /></TableCell>
                                    <TableCell><NumberCell row={row} field="revenue" /></TableCell>
                                    <TableCell className="bg-slate-50 font-medium">{roi}%</TableCell>
                                    <TableCell className="bg-slate-50 font-medium">{roi}%</TableCell>
                                    <TableCell>
                                        <Input
                                            className="h-8 min-w-[150px]"
                                            defaultValue={row.notes || ""}
                                            disabled={!canEdit}
                                            onBlur={(e) => {
                                                if (e.target.value !== row.notes) handleUpdate(row.id, "notes", e.target.value)
                                            }}
                                        />
                                    </TableCell>
                                </TableRow>
                            )
                        })}
                        {data.length === 0 && <TableRow><TableCell colSpan={11} className="text-center">No stats recorded</TableCell></TableRow>}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}
