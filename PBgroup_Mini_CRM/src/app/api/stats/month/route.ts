import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { Role } from "@prisma/client"
import { logAudit } from "@/lib/audit"
import { startOfMonth, endOfMonth, parseISO } from "date-fns"

export async function DELETE(req: Request) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    const url = new URL(req.url)
    const clientId = url.searchParams.get("clientId")
    const dateStr = url.searchParams.get("date") // expected YYYY-MM-DD or similar representative date

    if (!clientId || !dateStr) return new NextResponse("Missing params", { status: 400 })

    // Access Check
    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        // Project managers?
        // Maybe allow checks
    }
    // Check assignment if limited role
    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        if (session.user.role === Role.SALES) return new NextResponse("Forbidden", { status: 403 })
        const assignment = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId, userId: session.user.id } }
        })
        if (!assignment) return new NextResponse("Forbidden", { status: 403 })
    }

    const date = parseISO(dateStr)
    const start = startOfMonth(date)
    const end = endOfMonth(date)

    const result = await prisma.statRow.deleteMany({
        where: {
            clientId,
            date: {
                gte: start,
                lte: end
            }
        }
    })

    await logAudit({
        userId: session.user.id,
        action: "DELETE_STATS_MONTH",
        entityType: "STAT",
        entityId: clientId, // Using clientId as we deleted many rows
        before: { month: dateStr, deletedCount: result.count }
    })

    return NextResponse.json(result)
}
