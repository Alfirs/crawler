"use client"

import { DetailItem, FileAsset, DetailCategory } from "@prisma/client"
import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogTrigger, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Upload, FileIcon } from "lucide-react"

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
            toast.success("Created")
            setTitle("")
            setDesc("")
            setIsOpen(false)
            router.refresh()
        } catch (e) {
            toast.error("Error creating item")
        } finally {
            setIsCreating(false)
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

            toast.success("File uploaded")
            router.refresh()
        } catch (e) {
            toast.error("Upload failed")
        } finally {
            setUploadingId(null)
        }
    }

    return (
        <div className="space-y-4">
            {!isViewer && (
                <Dialog open={isOpen} onOpenChange={setIsOpen}>
                    <DialogTrigger asChild>
                        <Button>Add {category}</Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader><DialogTitle>Add {category}</DialogTitle></DialogHeader>
                        <div className="space-y-4 py-4">
                            <Input placeholder="Title" value={title} onChange={e => setTitle(e.target.value)} />
                            <Textarea placeholder="Description" value={desc} onChange={e => setDesc(e.target.value)} />
                        </div>
                        <DialogFooter>
                            <Button onClick={handleCreate} disabled={!title || isCreating}>Create</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            <div className="grid gap-4">
                {items.length === 0 && <p className="text-muted-foreground">No items.</p>}
                {items.map(item => (
                    <Card key={item.id}>
                        <CardHeader className="py-2">
                            <div className="flex justify-between items-center">
                                <CardTitle className="text-base font-semibold">{item.title}</CardTitle>
                            </div>
                        </CardHeader>
                        <CardContent className="py-2 space-y-2">
                            {item.description && <p className="whitespace-pre-wrap text-sm">{item.description}</p>}

                            {/* Files */}
                            {item.files.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
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
                                <div className="mt-2">
                                    <label className="cursor-pointer inline-flex items-center gap-2 text-xs text-blue-500 hover:text-blue-600">
                                        <Upload className="h-3 w-3" />
                                        {uploadingId === item.id ? "Uploading..." : "Upload File"}
                                        <input type="file" className="hidden" onChange={(e) => handleUpload(e, item.id)} />
                                    </label>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
