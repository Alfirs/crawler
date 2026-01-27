import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { StatTable } from "./stat-table"
import { Role } from "@prisma/client"
import { notFound, redirect } from "next/navigation"

export default async function ClientStatsPage({ params }: { params: Promise<{ clientId: string }> }) {
    const session = await getServerSession(authOptions)
    if (!session) redirect("/login")

    const { clientId } = await params

    // Access Security Check
    if (session.user.role === Role.EDITOR || session.user.role === Role.VIEWER) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId, userId: session.user.id } }
        })
        if (!isAssigned) return <div>Forbidden</div>
    }

    const client = await prisma.client.findUnique({ where: { id: clientId } })
    if (!client) notFound()

    const stats = await prisma.statRow.findMany({
        where: { clientId },
        orderBy: { date: "desc" }
    })

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">Stats: {client.name}</h1>
            <StatTable
                rows={stats}
                clientId={clientId}
                isViewer={session.user.role === Role.VIEWER}
            />
        </div>
    )
}
