import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { statRowUpdateSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"

export async function PATCH(
    req: Request,
    { params }: { params: Promise<{ rowId: string }> }
) {
    console.log("[STATS API] PATCH request received")

    const session = await getServerSession(authOptions)
    if (!session) {
        console.log("[STATS API] Unauthorized - no session")
        return new NextResponse("Unauthorized", { status: 401 })
    }

    if (session.user.role === Role.SALES) {
        console.log("[STATS API] Forbidden - SALES role")
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { rowId } = await params
    console.log("[STATS API] rowId:", rowId)

    const currentRow = await prisma.statRow.findUnique({ where: { id: rowId } })
    if (!currentRow) {
        console.log("[STATS API] Not Found - row doesn't exist")
        return new NextResponse("Not Found", { status: 404 })
    }

    // Access check
    if (session.user.role === Role.TARGETOLOGIST) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId: currentRow.clientId, userId: session.user.id } }
        })
        if (!isAssigned) {
            console.log("[STATS API] Forbidden - not assigned")
            return new NextResponse("Forbidden", { status: 403 })
        }
    }

    try {
        const json = await req.json()
        console.log("[STATS API] Request body:", json)

        const body = statRowUpdateSchema.parse(json)
        console.log("[STATS API] Parsed body:", body)

        const updated = await prisma.statRow.update({
            where: { id: rowId },
            data: body
        })
        console.log("[STATS API] Updated row:", updated)

        await logAudit({
            userId: session.user.id,
            action: "UPDATE_STAT",
            entityType: "STAT",
            entityId: rowId,
            before: currentRow,
            after: updated
        })

        return NextResponse.json(updated)
    } catch (error) {
        console.error("[STATS API] Error:", error)
        return new NextResponse("Invalid Request", { status: 400 })
    }
}
