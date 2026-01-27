"use client"

import { useState, useEffect } from "react"
import { DetailCategory, DetailItem as DetailItemType, FileAsset } from "@prisma/client"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { toast } from "sonner"
import { Plus, Upload, File as FileIcon } from "lucide-react"

interface DetailsManagerProps {
    clientId: string
}

type DetailWithFiles = DetailItemType & { files: FileAsset[] }

export function DetailsManager({ clientId }: DetailsManagerProps) {
    const [activeTab, setActiveTab] = useState<DetailCategory>(DetailCategory.PAINS)
    const [items, setItems] = useState<DetailWithFiles[]>([])
    const [loading, setLoading] = useState(false)

    // Dialog State
    const [isDialogOpen, setIsDialogOpen] = useState(false)
    const [editingItem, setEditingItem] = useState<DetailWithFiles | null>(null)
    const [title, setTitle] = useState("")
    const [desc, setDesc] = useState("")
    const [uploadFile, setUploadFile] = useState<File | null>(null)

    const fetchItems = async () => {
        setLoading(true)
        try {
            const res = await fetch(`/api/clients/${clientId}/details?category=${activeTab}`)
            if (res.ok) {
                const data = await res.json()
                setItems(data)
            }
        } catch (e) {
            toast.error("Failed to load items")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchItems()
    }, [activeTab, clientId])

    const handleSubmit = async () => {
        try {
            let itemId = editingItem?.id

            // 1. Create/Update Item
            const url = editingItem ? `/api/details/${editingItem.id}` : `/api/clients/${clientId}/details`
            const method = editingItem ? "PATCH" : "POST"

            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    category: activeTab,
                    title,
                    description: desc
                })
            })

            if (!res.ok) throw new Error("Failed to save item")
            const savedItem = await res.json()
            itemId = savedItem.id

            // 2. Upload File if present and new item or editing
            if (uploadFile && itemId) {
                const formData = new FormData()
                formData.append("file", uploadFile)
                formData.append("clientId", clientId)
                formData.append("detailItemId", itemId)

                const uploadRes = await fetch("/api/files/upload", {
                    method: "POST",
                    body: formData
                })

                if (!uploadRes.ok) toast.error("File upload failed")
                else toast.success("File uploaded")
            }

            toast.success("Saved")
            setIsDialogOpen(false)
            fetchItems()
            resetForm()
        } catch (e) {
            toast.error("Error saving")
        }
    }

    const resetForm = () => {
        setEditingItem(null)
        setTitle("")
        setDesc("")
        setUploadFile(null)
    }

    const openEdit = (item: DetailWithFiles) => {
        setEditingItem(item)
        setTitle(item.title)
        setDesc(item.description || "")
        setIsDialogOpen(true)
    }

    return (
        <div>
            <Tabs defaultValue={DetailCategory.PAINS} onValueChange={(v) => setActiveTab(v as DetailCategory)}>
                <TabsList className="mb-4">
                    {Object.values(DetailCategory).map(cat => (
                        <TabsTrigger key={cat} value={cat}>{cat}</TabsTrigger>
                    ))}
                </TabsList>

                <div className="flex justify-end mb-4">
                    <Dialog open={isDialogOpen} onOpenChange={(open) => { setIsDialogOpen(open); if (!open) resetForm(); }}>
                        <DialogTrigger asChild>
                            <Button><Plus className="mr-2 h-4 w-4" /> Add Item</Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>{editingItem ? "Edit Item" : "New Item"}</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                    <label>Title</label>
                                    <Input value={title} onChange={e => setTitle(e.target.value)} />
                                </div>
                                <div className="space-y-2">
                                    <label>Description</label>
                                    <Textarea value={desc} onChange={e => setDesc(e.target.value)} />
                                </div>
                                {activeTab === DetailCategory.CREATIVES && (
                                    <div className="space-y-2">
                                        <label>Attachment (Image/Video)</label>
                                        <Input type="file" onChange={e => setUploadFile(e.target.files?.[0] || null)} />
                                    </div>
                                )}
                                <Button onClick={handleSubmit} className="w-full">Save</Button>
                            </div>
                        </DialogContent>
                    </Dialog>
                </div>

                <TabsContent value={activeTab} className="space-y-4">
                    {items.map(item => (
                        <Card key={item.id} className="relative group">
                            <CardHeader>
                                <div className="flex justify-between">
                                    <CardTitle className="text-lg">{item.title}</CardTitle>
                                    <Button variant="ghost" size="sm" onClick={() => openEdit(item)}>Edit</Button>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <p className="whitespace-pre-wrap text-sm text-slate-600 mb-4">{item.description}</p>
                                {item.files && item.files.length > 0 && (
                                    <div className="flex gap-4 flex-wrap">
                                        {item.files.map(f => (
                                            <div key={f.id} className="border p-2 rounded max-w-xs">
                                                {f.mimeType.startsWith("image") ? (
                                                    <img src={`/uploads/${f.diskPath.split('/').pop()}`} alt={f.originalName} className="max-h-32 object-contain" />
                                                ) : (
                                                    <div className="flex items-center gap-2">
                                                        <FileIcon className="h-4 w-4" />
                                                        <span className="text-xs truncate">{f.originalName}</span>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                    {items.length === 0 && <p className="text-center text-slate-500 py-8">No items yet</p>}
                </TabsContent>
            </Tabs>
        </div>
    )
}
