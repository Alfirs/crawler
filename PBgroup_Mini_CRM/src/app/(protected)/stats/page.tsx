import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { Role } from "@prisma/client"
import { redirect } from "next/navigation"
import { StatsClientTable } from "./stats-client-table"
import { columns } from "./columns" // Import columns from columns.tsx

export default async function StatsPage() {
    const session = await getServerSession(authOptions)
    if (!session) redirect("/login")

    const whereClause: any = { deletedAt: null }

    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        whereClause.assignments = {
            some: {
                userId: session.user.id,
            },
        }
    }

    const clients = await prisma.client.findMany({
        where: whereClause,
        orderBy: { createdAt: "desc" },
    })

    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">Статистика</h1>
            <StatsClientTable columns={columns} data={clients} />
        </div>
    )
}

