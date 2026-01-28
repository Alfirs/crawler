"use client"

import { DetailItem, FileAsset, DetailCategory } from "@prisma/client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogTrigger, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Upload, FileIcon, Trash2, Pencil } from "lucide-react"
import { DETAIL_CATEGORY_LABELS } from "@/lib/dict"

interface DetailListProps {
    items: (DetailItem & { files: FileAsset[] })[]
    category: DetailCategory
    clientId: string
    isViewer: boolean
}

export function DetailList({ items, category, clientId, isViewer }: DetailListProps) {
    const router = useRouter()
    const [title, setTitle] = useState("")
    const [desc, setDesc] = useState("")
    const [isCreating, setIsCreating] = useState(false)
    const [isOpen, setIsOpen] = useState(false)

    // Edit state
    const [editingId, setEditingId] = useState<string | null>(null)
    const [editTitle, setEditTitle] = useState("")
    const [editDesc, setEditDesc] = useState("")
    const [isEditOpen, setIsEditOpen] = useState(false)

    // Upload state
    const [uploadingId, setUploadingId] = useState<string | null>(null)

    async function handleCreate() {
        if (!title) return
        setIsCreating(true)
        try {
            const res = await fetch(`/api/clients/${clientId}/details`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    category,
                    title,
                    description: desc
                })
            })
            if (!res.ok) throw new Error("Failed")
            toast.success("Создано")
            setTitle("")
            setDesc("")
            setIsOpen(false)
            router.refresh()
        } catch (e) {
            toast.error("Ошибка при создании")
        } finally {
            setIsCreating(false)
        }
    }

    function openEdit(item: DetailItem) {
        setEditingId(item.id)
        setEditTitle(item.title)
        setEditDesc(item.description || "")
        setIsEditOpen(true)
    }

    async function handleUpdate() {
        if (!editingId || !editTitle) return
        try {
            const res = await fetch(`/api/details/${editingId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: editTitle,
                    description: editDesc
                })
            })
            if (!res.ok) throw new Error("Failed")
            toast.success("Обновлено")
            setIsEditOpen(false)
            setEditingId(null)
            router.refresh()
        } catch (e) {
            toast.error("Ошибка при обновлении")
        }
    }

    async function handleDelete(id: string) {
        if (!confirm("Удалить эту запись?")) return
        try {
            const res = await fetch(`/api/details/${id}`, { method: "DELETE" })
            if (!res.ok) throw new Error("Failed")
            toast.success("Удалено")
            router.refresh()
        } catch (e) {
            toast.error("Ошибка при удалении")
        }
    }

    async function handleUpload(e: React.ChangeEvent<HTMLInputElement>, itemId: string) {
        if (!e.target.files?.[0]) return
        const file = e.target.files[0]
        setUploadingId(itemId)

        try {
            const formData = new FormData()
            formData.append("file", file)
            formData.append("clientId", clientId)
            formData.append("detailItemId", itemId)

            const res = await fetch("/api/files/upload", {
                method: "POST",
                body: formData
            })
            if (!res.ok) throw new Error("Upload failed")

            toast.success("Файл загружен")
            router.refresh()
        } catch (e) {
            toast.error("Ошибка загрузки")
        } finally {
            setUploadingId(null)
        }
    }

    return (
        <div className="space-y-4">
            {!isViewer && (
                <Dialog open={isOpen} onOpenChange={setIsOpen}>
                    <DialogTrigger asChild>
                        <Button>Добавить {DETAIL_CATEGORY_LABELS[category]}</Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader><DialogTitle>Добавить {DETAIL_CATEGORY_LABELS[category]}</DialogTitle></DialogHeader>
                        <div className="space-y-4 py-4">
                            <Input placeholder="Название" value={title} onChange={e => setTitle(e.target.value)} />
                            <Textarea placeholder="Описание" value={desc} onChange={e => setDesc(e.target.value)} />
                        </div>
                        <DialogFooter>
                            <Button onClick={handleCreate} disabled={!title || isCreating}>Создать</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {/* Edit Dialog */}
            <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
                <DialogContent>
                    <DialogHeader><DialogTitle>Редактировать</DialogTitle></DialogHeader>
                    <div className="space-y-4 py-4">
                        <Input placeholder="Название" value={editTitle} onChange={e => setEditTitle(e.target.value)} />
                        <Textarea placeholder="Описание" value={editDesc} onChange={e => setEditDesc(e.target.value)} />
                    </div>
                    <DialogFooter>
                        <Button onClick={handleUpdate} disabled={!editTitle}>Сохранить</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <div className="grid gap-3">
                {items.length === 0 && <p className="text-muted-foreground">Нет записей.</p>}
                {items.map(item => (
                    <Card key={item.id} className="py-0">
                        <CardHeader className="py-2 px-4">
                            <div className="flex justify-between items-center">
                                <CardTitle className="text-sm font-medium">{item.title}</CardTitle>
                                {!isViewer && (
                                    <div className="flex gap-1">
                                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(item)}>
                                            <Pencil className="h-3.5 w-3.5" />
                                        </Button>
                                        <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-600" onClick={() => handleDelete(item.id)}>
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </Button>
                                    </div>
                                )}
                            </div>
                        </CardHeader>
                        {/* Files and Upload only - no description shown */}
                        {(item.files.length > 0 || (!isViewer && category === DetailCategory.CREATIVES)) && (
                            <CardContent className="py-2 px-4">
                                {/* Files */}
                                {item.files.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {item.files.map(f => (
                                            <div key={f.id} className="relative group border rounded p-1 flex items-center gap-1 bg-slate-50 dark:bg-zinc-800">
                                                {f.mimeType?.startsWith("image/") ? (
                                                    <img src={f.diskPath} alt={f.originalName} className="h-10 w-10 object-cover rounded" />
                                                ) : (
                                                    <FileIcon className="h-6 w-6 text-muted-foreground" />
                                                )}
                                                <a href={f.diskPath} target="_blank" className="text-xs hover:underline truncate max-w-[100px]" title={f.originalName}>
                                                    {f.originalName}
                                                </a>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Upload Button */}
                                {!isViewer && category === DetailCategory.CREATIVES && (
                                    <label className="cursor-pointer inline-flex items-center gap-2 text-xs text-blue-500 hover:text-blue-600 mt-2">
                                        <Upload className="h-3 w-3" />
                                        {uploadingId === item.id ? "Загрузка..." : "Загрузить файл"}
                                        <input type="file" className="hidden" onChange={(e) => handleUpload(e, item.id)} />
                                    </label>
                                )}
                            </CardContent>
                        )}
                    </Card>
                ))}
            </div>
        </div>
    )
}
