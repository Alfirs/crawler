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

interface EmployeeTableProps {
    users: User[]
}

export function EmployeeList({ users }: EmployeeTableProps) {
    const router = useRouter()
    const [isOpen, setIsOpen] = useState(false)
    const [isCreating, setIsCreating] = useState(false)

    // Form state
    const [fullName, setFullName] = useState("")
    const [login, setLogin] = useState("")
    const [pass, setPass] = useState("")
    const [role, setRole] = useState<Role>(Role.EDITOR)
    const [spec, setSpec] = useState("")

    async function handleCreate() {
        if (!fullName || !login) return
        setIsCreating(true)
        try {
            const res = await fetch("/api/employees", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    fullName,
                    login,
                    password: pass || undefined,
                    role,
                    specialization: spec
                })
            })
            if (!res.ok) throw new Error("Failed")
            toast.success("Employee created")
            setIsOpen(false)
            setFullName(""); setLogin(""); setPass("");
            router.refresh()
        } catch (e) {
            toast.error("Error creating employee")
        } finally {
            setIsCreating(false)
        }
    }

    return (
        <div className="space-y-4">
            <div className="flex justify-end">
                <Dialog open={isOpen} onOpenChange={setIsOpen}>
                    <DialogTrigger asChild>
                        <Button>Add Employee</Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader><DialogTitle>New Employee</DialogTitle></DialogHeader>
                        <div className="grid gap-4 py-4">
                            <Input placeholder="Full Name" value={fullName} onChange={e => setFullName(e.target.value)} />
                            <Input placeholder="Login" value={login} onChange={e => setLogin(e.target.value)} />
                            <Input placeholder="Password (default 123456)" type="password" value={pass} onChange={e => setPass(e.target.value)} />
                            <Select value={role} onValueChange={(r) => setRole(r as Role)}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    {Object.values(Role).map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                                </SelectContent>
                            </Select>
                            <Input placeholder="Specialization (optional)" value={spec} onChange={e => setSpec(e.target.value)} />
                        </div>
                        <DialogFooter>
                            <Button onClick={handleCreate} disabled={isCreating}>Create</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            <div className="rounded-md border bg-white dark:bg-zinc-950">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Name</TableHead>
                            <TableHead>Login</TableHead>
                            <TableHead>Role</TableHead>
                            <TableHead>Specialization</TableHead>
                            <TableHead>Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {users.map(u => (
                            <TableRow key={u.id}>
                                <TableCell className="font-medium">{u.fullName}</TableCell>
                                <TableCell>{u.login}</TableCell>
                                <TableCell><Badge variant="outline">{u.role}</Badge></TableCell>
                                <TableCell>{u.specialization || "-"}</TableCell>
                                <TableCell>
                                    {/* Edit Logic could be added here */}
                                    <Button variant="ghost" size="sm" onClick={() => toast.info("Edit not implemented in MVP List, use DB or expand")}>Edit</Button>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}
