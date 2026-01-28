"use client"

import { User, Role } from "@prisma/client"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTrigger, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { ROLE_LABELS } from "@/lib/dict"
import { Check, X, Trash } from "lucide-react"
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command"
import { cn } from "@/lib/utils"

interface EmployeeTableProps {
    users: (User & { assignments: { clientId: string }[] })[]
    clients: { id: string; name: string }[]
    currentUserRole?: Role
}

export function EmployeeList({ users, clients, currentUserRole }: EmployeeTableProps) {
    const router = useRouter()
    const [isOpen, setIsOpen] = useState(false)
    const [loading, setLoading] = useState(false)
    const [editId, setEditId] = useState<string | null>(null)

    // Form state
    const [fullName, setFullName] = useState("")
    const [login, setLogin] = useState("")
    const [pass, setPass] = useState("")
    const [role, setRole] = useState<Role>(Role.TARGETOLOGIST)
    const [spec, setSpec] = useState("")
    const [assignedClientIds, setAssignedClientIds] = useState<string[]>([])

    const resetForm = () => {
        setFullName("")
        setLogin("")
        setPass("")
        setRole(Role.TARGETOLOGIST)
        setSpec("")
        setAssignedClientIds([])
        setEditId(null)
    }

    const openCreate = () => {
        resetForm()
        setIsOpen(true)
    }

    const openEdit = (u: User & { assignments: { clientId: string }[] }) => {
        setEditId(u.id)
        setFullName(u.fullName)
        setLogin(u.login)
        setPass("") // Empty for edit implies no change
        setRole(u.role)
        setSpec(u.specialization || "")
        setAssignedClientIds(u.assignments.map(a => a.clientId))
        setIsOpen(true)
    }

    async function handleSubmit() {
        if (!fullName || !login) return
        setLoading(true)
        try {
            const url = editId ? `/api/employees/${editId}` : "/api/employees"
            const method = editId ? "PATCH" : "POST"

            const body: any = {
                fullName,
                login,
                role,
                specialization: spec,
                assignedClientIds
            }
            if (pass) body.password = pass

            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            })
            if (!res.ok) throw new Error("Failed")
            toast.success(editId ? "Сотрудник обновлен" : "Сотрудник создан")
            setIsOpen(false)
            resetForm()
            router.refresh()
        } catch (e) {
            toast.error("Ошибка сохранения")
        } finally {
            setLoading(false)
        }
    }

    const toggleClient = (clientId: string) => {
        setAssignedClientIds(prev =>
            prev.includes(clientId)
                ? prev.filter(id => id !== clientId)
                : [...prev, clientId]
        )
    }

    async function onDelete(userId: string) {
        if (!confirm("Удалить сотрудника?")) return
        setLoading(true)
        try {
            const res = await fetch(`/api/employees/${userId}`, { method: "DELETE" })
            if (!res.ok) {
                if (res.status === 400) toast.error("Нельзя удалить себя")
                else throw new Error("Failed")
                return
            }
            toast.success("Сотрудник удален")
            router.refresh()
        } catch (e) {
            toast.error("Ошибка удаления")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="space-y-4">
            <div className="flex justify-end">
                <Dialog open={isOpen} onOpenChange={(v) => { setIsOpen(v); if (!v) resetForm(); }}>
                    <DialogTrigger asChild>
                        <Button onClick={openCreate}>Добавить сотрудника</Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader><DialogTitle>{editId ? "Редактирование" : "Новый сотрудник"}</DialogTitle></DialogHeader>
                        <div className="grid gap-4 py-4">
                            <div className="grid grid-cols-2 gap-4">
                                <Input placeholder="ФИО" value={fullName} onChange={e => setFullName(e.target.value)} />
                                <Input placeholder="Логин" value={login} onChange={e => setLogin(e.target.value)} />
                                <Input placeholder={editId ? "Новый пароль (необязательно)" : "Пароль (по умолчанию 123456)"} type="password" value={pass} onChange={e => setPass(e.target.value)} />
                                <Select value={role} onValueChange={(r) => setRole(r as Role)}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {Object.values(Role).map(r => <SelectItem key={r} value={r}>{ROLE_LABELS[r]}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                                <Input className="col-span-2" placeholder="Специализация (необязательно)" value={spec} onChange={e => setSpec(e.target.value)} />
                            </div>

                            <div className="space-y-2 border rounded-md p-2">
                                <label className="text-sm font-medium">Привязать проекты (Клиенты)</label>
                                <div className="border rounded-md">
                                    <Command>
                                        <CommandInput placeholder="Поиск клиента..." />
                                        <CommandList className="max-h-[200px]">
                                            <CommandEmpty>Клиенты не найдены</CommandEmpty>
                                            <CommandGroup>
                                                {clients.map(client => {
                                                    const isSelected = assignedClientIds.includes(client.id)
                                                    return (
                                                        <CommandItem
                                                            key={client.id}
                                                            onSelect={() => toggleClient(client.id)}
                                                        >
                                                            <div className={cn(
                                                                "mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                                                                isSelected ? "bg-primary text-primary-foreground" : "opacity-50 [&_svg]:invisible"
                                                            )}>
                                                                <Check className={cn("h-4 w-4", isSelected ? "visible" : "invisible")} />
                                                            </div>
                                                            {client.name}
                                                        </CommandItem>
                                                    )
                                                })}
                                            </CommandGroup>
                                        </CommandList>
                                    </Command>
                                </div>
                                <div className="flex flex-wrap gap-1 mt-2">
                                    {assignedClientIds.map(id => {
                                        const c = clients.find(cl => cl.id === id)
                                        return c ? (
                                            <Badge key={id} variant="secondary" className="cursor-pointer" onClick={() => toggleClient(id)}>
                                                {c.name} <X className="w-3 h-3 ml-1" />
                                            </Badge>
                                        ) : null
                                    })}
                                </div>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button onClick={handleSubmit} disabled={loading}>{editId ? "Сохранить" : "Создать"}</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            <div className="rounded-md border bg-white dark:bg-zinc-950">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>ФИО</TableHead>
                            <TableHead>Логин</TableHead>
                            <TableHead>Роль</TableHead>
                            <TableHead>Специализация</TableHead>
                            <TableHead>Действия</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {users.map(u => (
                            <TableRow key={u.id}>
                                <TableCell className="font-medium">{u.fullName}</TableCell>
                                <TableCell>{u.login}</TableCell>
                                <TableCell><Badge variant="outline">{ROLE_LABELS[u.role]}</Badge></TableCell>
                                <TableCell>{u.specialization || "-"}</TableCell>
                                <TableCell className="flex gap-2">
                                    <Button variant="ghost" size="sm" onClick={() => openEdit(u)}>Редактировать</Button>
                                    {(currentUserRole === Role.ADMIN || currentUserRole === Role.ADMIN_STAFF) && (
                                        <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-600" onClick={() => onDelete(u.id)}>
                                            <Trash className="w-4 h-4" />
                                        </Button>
                                    )}
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}

