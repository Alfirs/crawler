import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { Role } from "@prisma/client"
import { redirect } from "next/navigation"
import { EmployeeList } from "./employee-list"

export default async function EmployeesPage() {
    const session = await getServerSession(authOptions)
    if (!session) redirect("/login")

    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        return <div>Forbidden</div>
    }

    const users = await prisma.user.findMany({
        where: { deletedAt: null },
        orderBy: { fullName: "asc" },
        include: {
            assignments: {
                select: { clientId: true }
            }
        }
    })

    const clients = await prisma.client.findMany({
        where: { deletedAt: null },
        select: { id: true, name: true, status: true },
        orderBy: { name: "asc" }
    })

    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">Сотрудники</h1>
            <EmployeeList users={users} clients={clients} currentUserRole={session.user.role} />
        </div>
    )
}
