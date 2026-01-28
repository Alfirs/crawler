"use client"

import * as React from "react"
import { StatRow, Role } from "@prisma/client"
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
import { format, getMonth, getYear } from "date-fns"
import { ru } from "date-fns/locale"
import { AddMonthDialog } from "./add-month-dialog"
import { ChevronDown, ChevronRight, Trash } from "lucide-react"

interface StatTableProps {
    rows: StatRow[]
    clientId: string
    isViewer: boolean
    userRole?: Role
}

// Helper to calc CPL/ROI
const calcMetrics = (spend: number, leads: number, sales: number, revenue: number) => {
    const cpl = leads > 0 ? (spend / leads).toFixed(0) : "-"
    const roi = spend > 0 ? ((revenue - spend) / spend * 100).toFixed(0) : "-"
    return { cpl, roi }
}

function StatTableRow({ row, isViewer, onUpdate }: { row: StatRow, isViewer: boolean, onUpdate?: (id: string, updates: Partial<StatRow>) => void }) {
    // Local state for smooth typing without lag
    const [localData, setLocalData] = React.useState(row)
    const [isSaving, setIsSaving] = React.useState(false)

    // Track the last saved values to compare against (not the prop which can change)
    const savedDataRef = React.useRef(row)

    // Sync when row.id changes (different row) but NOT when parent updates same row
    React.useEffect(() => {
        console.log("[StatRow] Row ID changed, syncing:", row.id)
        setLocalData(row)
        savedDataRef.current = row
    }, [row.id])

    const { cpl, roi } = calcMetrics(localData.spend, localData.leads, localData.sales, localData.revenue)

    async function saveField(field: keyof StatRow, value: any) {
        console.log(`[StatRow] saveField called: ${field} = ${value}`)
        console.log(`[StatRow] savedDataRef[${field}] =`, savedDataRef.current[field])

        // Skip if value hasn't actually changed from last save
        if (savedDataRef.current[field] === value) {
            console.log(`[StatRow] Skipping save - value unchanged`)
            return
        }

        console.log(`[StatRow] Saving to API: /api/stats/${row.id}`)
        setIsSaving(true)
        try {
            const res = await fetch(`/api/stats/${row.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ [field]: value })
            })
            console.log(`[StatRow] API response status: ${res.status}`)
            if (!res.ok) throw new Error("Failed")

            // Update our ref to reflect the saved value
            savedDataRef.current = { ...savedDataRef.current, [field]: value }
            console.log(`[StatRow] Save successful, updated savedDataRef`)

            // Notify parent for aggregation update
            onUpdate?.(row.id, { [field]: value })
        } catch (e) {
            console.error("[StatRow] Save error:", e)
            toast.error("Ошибка сохранения")
        } finally {
            setIsSaving(false)
        }
    }

    const handleChange = (field: keyof StatRow, value: any) => {
        setLocalData(prev => ({ ...prev, [field]: value }))
    }

    const handleBlur = (field: keyof StatRow, value: any) => {
        console.log(`[StatRow] handleBlur: ${field} = ${value}`)
        saveField(field, value)
    }

    // Colors
    const roiVal = parseFloat(roi)
    const roiColor = isNaN(roiVal) ? "" : roiVal > 0 ? "text-green-600 font-bold" : "text-red-500 font-bold"

    return (
        <TableRow className={isSaving ? "opacity-70 transition-opacity" : ""}>
            <TableCell>{format(new Date(localData.date), "dd.MM.yyyy")}</TableCell>
            <TableCell>
                <Input
                    type="number"
                    value={localData.spend || ''}
                    onChange={(e) => handleChange("spend", parseFloat(e.target.value) || 0)}
                    onBlur={(e) => handleBlur("spend", parseFloat(e.target.value) || 0)}
                    disabled={isViewer}
                    className="w-20 px-2 h-8"
                />
            </TableCell>
            <TableCell>
                <Input
                    type="number"
                    value={localData.reach || ''}
                    onChange={(e) => handleChange("reach", parseInt(e.target.value) || 0)}
                    onBlur={(e) => handleBlur("reach", parseInt(e.target.value) || 0)}
                    disabled={isViewer}
                    className="w-20 px-2 h-8"
                />
            </TableCell>
            <TableCell>
                <Input
                    type="number"
                    value={localData.clicks || ''}
                    onChange={(e) => handleChange("clicks", parseInt(e.target.value) || 0)}
                    onBlur={(e) => handleBlur("clicks", parseInt(e.target.value) || 0)}
                    disabled={isViewer}
                    className="w-20 px-2 h-8"
                />
            </TableCell>
            <TableCell>
                <Input
                    type="number"
                    value={localData.leads || ''}
                    onChange={(e) => handleChange("leads", parseInt(e.target.value) || 0)}
                    onBlur={(e) => handleBlur("leads", parseInt(e.target.value) || 0)}
                    disabled={isViewer}
                    className="w-20 px-2 h-8"
                />
            </TableCell>
            <TableCell className="font-mono text-xs">{cpl}</TableCell>
            <TableCell>
                <Input
                    type="number"
                    value={localData.sales || ''}
                    onChange={(e) => handleChange("sales", parseInt(e.target.value) || 0)}
                    onBlur={(e) => handleBlur("sales", parseInt(e.target.value) || 0)}
                    disabled={isViewer}
                    className="w-20 px-2 h-8"
                />
            </TableCell>
            <TableCell>
                <Input
                    type="number"
                    value={localData.revenue || ''}
                    onChange={(e) => handleChange("revenue", parseFloat(e.target.value) || 0)}
                    onBlur={(e) => handleBlur("revenue", parseFloat(e.target.value) || 0)}
                    disabled={isViewer}
                    className="w-24 px-2 h-8"
                />
            </TableCell>
            <TableCell className={`text-xs ${roiColor}`}>{roi}%</TableCell>
            <TableCell>
                <Input
                    value={localData.notes || ""}
                    onChange={(e) => handleChange("notes", e.target.value)}
                    onBlur={(e) => handleBlur("notes", e.target.value)}
                    disabled={isViewer}
                    className="w-full min-w-[100px] h-8"
                    placeholder="..."
                />
            </TableCell>
        </TableRow>
    )
}

function MonthSection({ groupKey, rows, isViewer, onUpdate, canDeleteMonth }: { groupKey: string, rows: StatRow[], isViewer: boolean, onUpdate: (id: string, up: Partial<StatRow>) => void, canDeleteMonth?: boolean }) {
    const [isOpen, setIsOpen] = React.useState(false)
    const [isDeleting, setIsDeleting] = React.useState(false)
    const router = useRouter()

    // Aggr
    const totalSpend = rows.reduce((acc, r) => acc + r.spend, 0)
    const totalReach = rows.reduce((acc, r) => acc + r.reach, 0)
    const totalClicks = rows.reduce((acc, r) => acc + r.clicks, 0)
    const totalLeads = rows.reduce((acc, r) => acc + r.leads, 0)
    const totalSales = rows.reduce((acc, r) => acc + r.sales, 0)
    const totalRevenue = rows.reduce((acc, r) => acc + r.revenue, 0)
    const { cpl, roi } = calcMetrics(totalSpend, totalLeads, totalSales, totalRevenue)

    // ROI color
    const roiVal = parseFloat(roi)
    const roiColor = isNaN(roiVal) ? "" : roiVal > 0 ? "text-green-600" : "text-red-500"

    const dateObj = new Date(rows[0].date)
    const monthName = format(dateObj, "LLLL yyyy", { locale: ru })

    async function deleteMonth(e: React.MouseEvent) {
        e.stopPropagation()
        if (!confirm(`Удалить статистику за ${monthName}?`)) return
        setIsDeleting(true)
        try {
            const dateStr = format(dateObj, "yyyy-MM-dd")
            const res = await fetch(`/api/stats/month?clientId=${rows[0].clientId}&date=${dateStr}`, {
                method: "DELETE"
            })
            if (!res.ok) throw new Error("Delete failed")
            toast.success("Месяц удален")
            router.refresh()
        } catch (err) {
            toast.error("Ошибка удаления")
            setIsDeleting(false)
        }
    }

    return (
        <div className="border rounded-md mb-4 bg-white dark:bg-zinc-950 shadow-sm">
            <div
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex items-center gap-2">
                    {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    <h3 className="font-bold capitalize">{monthName}</h3>
                </div>
                <div className="flex gap-4 text-sm font-medium text-muted-foreground">
                    <div title="Затраты">₽ {totalSpend.toLocaleString()}</div>
                    <div title="Клики">Кл: {totalClicks}</div>
                    <div title="Лиды">Лиды: {totalLeads}</div>
                    <div title="ROI" className={roiColor}>ROI: {roi}%</div>

                    {canDeleteMonth && (
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground hover:text-red-500 hover:bg-red-50"
                            disabled={isDeleting}
                            onClick={deleteMonth}
                        >
                            <Trash className="w-4 h-4" />
                        </Button>
                    )}
                </div>
            </div>

            {isOpen && (
                <div className="border-t">
                    {/* Aggregation Row (Summary) */}
                    <div className="bg-muted/30 p-2 text-xs font-semibold grid grid-cols-1 md:grid-cols-2 gap-2 border-b">
                        <div className="flex gap-4 ml-4">
                            <span>Итого за месяц: </span>
                            <span className="text-blue-600">Расход: {totalSpend.toLocaleString()}</span>
                            <span className="text-green-600">Выручка: {totalRevenue.toLocaleString()}</span>
                            <span>Лиды: {totalLeads} ({cpl} ₽/шт)</span>
                        </div>
                    </div>

                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-muted/50">
                                    <TableHead className="w-[100px]">Дата</TableHead>
                                    <TableHead>Расход</TableHead>
                                    <TableHead>Охват</TableHead>
                                    <TableHead>Клики</TableHead>
                                    <TableHead>Заявки</TableHead>
                                    <TableHead>CPL</TableHead>
                                    <TableHead>Продажи</TableHead>
                                    <TableHead>Выручка</TableHead>
                                    <TableHead>ROI</TableHead>
                                    <TableHead className="w-[150px]">Заметки</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {rows.map(row => (
                                    <StatTableRow key={row.id} row={row} isViewer={isViewer} onUpdate={onUpdate} />
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                </div>
            )}
        </div>
    )
}

export function StatTable({ rows, clientId, isViewer, userRole }: StatTableProps) {
    const router = useRouter()

    // Check global permission
    const canDeleteMonth = userRole === Role.ADMIN || userRole === Role.ADMIN_STAFF
    // Prepare initial data
    const sorted = [...rows].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    const [data, setData] = React.useState(sorted)

    React.useEffect(() => {
        setData([...rows].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()))
    }, [rows])

    const handleUpdate = (id: string, updates: Partial<StatRow>) => {
        setData(prev => prev.map(r => r.id === id ? { ...r, ...updates } : r))
    }

    // Grouping
    const groups: Record<string, StatRow[]> = {}
    data.forEach(row => {
        const d = new Date(row.date)
        const key = `${d.getFullYear()}-${d.getMonth()}` // YYYY-M (0-11)
        if (!groups[key]) groups[key] = []
        groups[key].push(row)
    })

    // Sort keys desc
    const groupKeys = Object.keys(groups).sort((a, b) => {
        const [yA, mA] = a.split('-').map(Number)
        const [yB, mB] = b.split('-').map(Number)
        if (yA !== yB) return yB - yA
        return mB - mA
    })

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold">Ежедневная статистика</h2>
                {!isViewer && <AddMonthDialog clientId={clientId} />}
            </div>

            {groupKeys.length === 0 && <p className="text-muted-foreground">Нет данных. Добавьте месяц.</p>}

            {groupKeys.map(key => (
                <MonthSection
                    key={key}
                    groupKey={key}
                    rows={groups[key]}
                    isViewer={isViewer}
                    onUpdate={handleUpdate}
                    canDeleteMonth={canDeleteMonth}
                />
            ))}
        </div>
    )
}
