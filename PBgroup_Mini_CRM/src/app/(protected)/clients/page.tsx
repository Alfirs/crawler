import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { ClientTable } from "./client-table"
import { columns } from "./columns" // Import columns from columns.tsx
// wait, columns.tsx needs to be created. I just created it.
import { Role } from "@prisma/client"
import { redirect } from "next/navigation"

export default async function ClientsPage() {
    const session = await getServerSession(authOptions)
    if (!session) redirect("/login")

    const whereClause: any = { deletedAt: null }

    if (session.user.role === Role.TARGETOLOGIST || session.user.role === Role.SALES) {
        whereClause.assignments = {
            some: {
                userId: session.user.id,
            },
        }
    }

    const clients = await prisma.client.findMany({
        where: whereClause,
        include: {
            targetologist: { select: { fullName: true } },
            projectManager: { select: { fullName: true } },
            assignments: { include: { user: { select: { fullName: true } } } },
            sources: { select: { sourceType: true } },
            pauses: true
        },
        orderBy: { createdAt: "desc" },
    })

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight">Клиенты</h1>
            </div>
            <ClientTable columns={columns as any} data={clients as any} />
        </div>
    )
}
