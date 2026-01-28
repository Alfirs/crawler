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
    if (session.user.role === Role.SALES) return new NextResponse("Forbidden", { status: 403 })

    const { detailId } = await params

    const current = await prisma.detailItem.findUnique({ where: { id: detailId } })
    if (!current) return new NextResponse("Not Found", { status: 404 })

    if (session.user.role === Role.TARGETOLOGIST) {
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

// DELETE - allow ADMIN, ADMIN_STAFF, and TARGETOLOGIST (if assigned)
export async function DELETE(
    req: Request,
    { params }: { params: Promise<{ detailId: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    // Forbidden for Viewer only
    if (session.user.role === Role.SALES) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { detailId } = await params

    try {
        const current = await prisma.detailItem.findUnique({
            where: { id: detailId },
            include: { files: true }
        })
        if (!current) return new NextResponse("Not Found", { status: 404 })

        // Check if TARGETOLOGIST is assigned to this client
        if (session.user.role === Role.TARGETOLOGIST) {
            const isAssigned = await prisma.clientAssignment.findUnique({
                where: { clientId_userId: { clientId: current.clientId, userId: session.user.id } }
            })
            if (!isAssigned) return new NextResponse("Forbidden", { status: 403 })
        }

        // Delete associated files first
        if (current.files.length > 0) {
            await prisma.fileAsset.deleteMany({
                where: { detailItemId: detailId }
            })
        }

        await prisma.detailItem.delete({ where: { id: detailId } })

        await logAudit({
            userId: session.user.id,
            action: "DELETE_DETAIL",
            entityType: "DETAIL",
            entityId: detailId,
            before: current
        })

        return NextResponse.json({ success: true })
    } catch (e) {
        console.error("[DETAIL DELETE] Error:", e)
        return new NextResponse("Error", { status: 500 })
    }
}
