"use client"

import { ClientPause } from "@prisma/client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { format } from "date-fns"
import { ru } from "date-fns/locale"
import { toast } from "sonner"
import { useRouter } from "next/navigation"
import { Trash2, Plus } from "lucide-react"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
    DialogFooter
} from "@/components/ui/dialog"

interface ClientPausesProps {
    pauses: ClientPause[]
    clientId: string
    canEdit: boolean
}

export function ClientPauses({ pauses, clientId, canEdit }: ClientPausesProps) {
    const router = useRouter()
    const [isOpen, setIsOpen] = useState(false)
    const [isSaving, setIsSaving] = useState(false)

    // Form State
    const [startDate, setStartDate] = useState("")
    const [endDate, setEndDate] = useState("")
    const [comment, setComment] = useState("")

    async function handleCreate() {
        if (!startDate) return toast.error("Дата начала обязательна")
        setIsSaving(true)
        try {
            const res = await fetch(`/api/clients/${clientId}/pauses`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    startDate: new Date(startDate),
                    endDate: endDate ? new Date(endDate) : undefined,
                    comment
                })
            })
            if (!res.ok) throw new Error("Failed")
            toast.success("Пауза добавлена")
            setIsOpen(false)
            setStartDate("")
            setEndDate("")
            setComment("")
            router.refresh()
        } catch (e) {
            toast.error("Ошибка добавления")
        } finally {
            setIsSaving(false)
        }
    }

    async function handleDelete(id: string) {
        if (!confirm("Удалить эту паузу?")) return
        try {
            const res = await fetch(`/api/pauses/${id}`, { method: "DELETE" })
            if (!res.ok) throw new Error("Failed")
            toast.success("Пауза удалена")
            router.refresh()
        } catch (e) {
            toast.error("Ошибка удаления")
        }
    }

    // Sort pauses desc by startDate
    const sorted = [...pauses].sort((a, b) => new Date(b.startDate).getTime() - new Date(a.startDate).getTime())

    return (
        <div className="space-y-4 pt-4 border-t">
            <div className="flex items-center justify-between">
                <h3 className="font-medium text-lg">Паузы / Приостановки</h3>
                {canEdit && (
                    <Dialog open={isOpen} onOpenChange={setIsOpen}>
                        <DialogTrigger asChild>
                            <Button variant="outline" size="sm"><Plus className="w-4 h-4 mr-2" /> Добавить</Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader><DialogTitle>Добавить паузу</DialogTitle></DialogHeader>
                            <div className="grid gap-4 py-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>С даты</Label>
                                        <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>По дату (включительно)</Label>
                                        <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label>Комментарий</Label>
                                    <Input value={comment} onChange={e => setComment(e.target.value)} placeholder="Причина паузы..." />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button onClick={handleCreate} disabled={isSaving}>Сохранить</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                )}
            </div>

            <div className="space-y-2">
                {sorted.length === 0 && <p className="text-sm text-muted-foreground">Нет активных пауз</p>}
                {sorted.map(p => (
                    <div key={p.id} className="flex items-center justify-between p-3 border rounded-md bg-muted/30">
                        <div>
                            <div className="font-medium">
                                {format(new Date(p.startDate), "dd.MM.yyyy")}
                                {p.endDate ? ` — ${format(new Date(p.endDate), "dd.MM.yyyy")}` : " — ..."}
                            </div>
                            {p.comment && <div className="text-sm text-muted-foreground">{p.comment}</div>}
                        </div>
                        {canEdit && (
                            <Button variant="ghost" size="icon" onClick={() => handleDelete(p.id)}>
                                <Trash2 className="w-4 h-4 text-destructive" />
                            </Button>
                        )}
                    </div>
                ))}
            </div>
        </div>
    )
}
