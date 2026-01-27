"use client"

import { useState } from "react"
import { User, Role } from "@prisma/client"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import { Plus } from "lucide-react"
import { useRouter } from "next/navigation"

type EmployeeWithCounts = User & { assignments: { clientId: string }[] }

export function EmployeesManager({ initialData }: { initialData: EmployeeWithCounts[] }) {
    const router = useRouter()
    const [open, setOpen] = useState(false)
    const [loading, setLoading] = useState(false)

    // Form State
    const [fullName, setFullName] = useState("")
    const [login, setLogin] = useState("")
    const [password, setPassword] = useState("")
    const [role, setRole] = useState<Role>(Role.EDITOR)
    const [spec, setSpec] = useState("")

    const handleSubmit = async () => {
        setLoading(true)
        try {
            const res = await fetch("/api/employees", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    fullName,
                    login,
                    password: password || "123456",
                    role,
                    specialization: spec
                })
            })

            if (!res.ok) throw new Error("Failed to create")

            toast.success("Employee created")
            setOpen(false)
            setFullName("")
            setLogin("")
            setPassword("")
            setSpec("")
            router.refresh()
        } catch (error) {
            toast.error("Error creating employee")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <div className="flex justify-end mb-4">
                <Dialog open={open} onOpenChange={setOpen}>
                    <DialogTrigger asChild>
                        <Button><Plus className="mr-2 h-4 w-4" /> Add Employee</Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Add Employee</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <Input placeholder="Full Name" value={fullName} onChange={e => setFullName(e.target.value)} />
                            <Input placeholder="Login (Email)" value={login} onChange={e => setLogin(e.target.value)} />
                            <Input placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} />
                            <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                                <SelectTrigger><SelectValue placeholder="Role" /></SelectTrigger>
                                <SelectContent>
                                    {Object.values(Role).map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                                </SelectContent>
                            </Select>
                            <Input placeholder="Specialization" value={spec} onChange={e => setSpec(e.target.value)} />
                            <Button onClick={handleSubmit} disabled={loading} className="w-full">Create</Button>
                        </div>
                    </DialogContent>
                </Dialog>
            </div>

            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Full Name</TableHead>
                            <TableHead>Role</TableHead>
                            <TableHead>Specialization</TableHead>
                            <TableHead>Assigned Clients</TableHead>
                            <TableHead>Login</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {initialData.map(emp => (
                            <TableRow key={emp.id}>
                                <TableCell className="font-medium">{emp.fullName}</TableCell>
                                <TableCell><Badge variant="outline">{emp.role}</Badge></TableCell>
                                <TableCell>{emp.specialization || "-"}</TableCell>
                                <TableCell>{emp.assignments.length}</TableCell>
                                <TableCell>{emp.login}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}
