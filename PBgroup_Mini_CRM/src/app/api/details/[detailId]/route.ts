import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { detailItemSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"

export async function PATCH(
    req: Request,
    { params }: { params: Promise<{ detailId: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })
    if (session.user.role === Role.VIEWER) return new NextResponse("Forbidden", { status: 403 })

    const { detailId } = await params

    const current = await prisma.detailItem.findUnique({ where: { id: detailId } })
    if (!current) return new NextResponse("Not Found", { status: 404 })

    if (session.user.role === Role.EDITOR) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId: current.clientId, userId: session.user.id } }
        })
        if (!isAssigned) return new NextResponse("Forbidden", { status: 403 })
    }

    try {
        const json = await req.json()
        const body = detailItemSchema.partial().parse(json)

        const updated = await prisma.detailItem.update({
            where: { id: detailId },
            data: body
        })

        await logAudit({
            userId: session.user.id,
            action: "UPDATE_DETAIL",
            entityType: "DETAIL",
            entityId: detailId,
            before: current,
            after: updated
        })

        return NextResponse.json(updated)
    } catch (error) {
        return new NextResponse("Invalid Request", { status: 400 })
    }
}

// DELETE? Section 4.7: "удаление запрещено EDITOR"
export async function DELETE(
    req: Request,
    { params }: { params: Promise<{ detailId: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    // Forbidden for Editor/Viewer
    if (session.user.role === Role.EDITOR || session.user.role === Role.VIEWER) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { detailId } = await params

    try {
        await prisma.detailItem.delete({ where: { id: detailId } })

        await logAudit({
            userId: session.user.id,
            action: "DELETE_DETAIL",
            entityType: "DETAIL",
            entityId: detailId
        })

        return NextResponse.json({ success: true })
    } catch (e) {
        return new NextResponse("Error", { status: 500 })
    }
}
