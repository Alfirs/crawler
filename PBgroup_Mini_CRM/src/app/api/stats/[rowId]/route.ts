import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { statRowSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"

export async function PATCH(
    req: Request,
    { params }: { params: Promise<{ rowId: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    if (session.user.role === Role.VIEWER) return new NextResponse("Forbidden", { status: 403 })

    const { rowId } = await params

    const currentRow = await prisma.statRow.findUnique({ where: { id: rowId } })
    if (!currentRow) return new NextResponse("Not Found", { status: 404 })

    // Access check
    if (session.user.role === Role.EDITOR) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId: currentRow.clientId, userId: session.user.id } }
        })
        if (!isAssigned) return new NextResponse("Forbidden", { status: 403 })
    }

    try {
        const json = await req.json()
        const body = statRowSchema.partial().parse(json)

        const updated = await prisma.statRow.update({
            where: { id: rowId },
            data: body
        })

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
        return new NextResponse("Invalid Request", { status: 400 })
    }
}
