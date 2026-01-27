import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { assignSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"

export async function POST(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    if (session.user.role !== Role.ADMIN && session.user.role !== Role.MANAGER) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { id } = await params

    try {
        const json = await req.json()
        const { userId } = assignSchema.parse(json)

        await prisma.clientAssignment.deleteMany({
            where: {
                clientId: id,
                userId: userId
            }
        })

        await logAudit({
            userId: session.user.id,
            action: "UNASSIGN_USER",
            entityType: "ASSIGNMENT",
            entityId: `${id}-${userId}`,
            after: { clientId: id, unassignedUserId: userId }
        })

        return NextResponse.json({ success: true })
    } catch (error) {
        return new NextResponse("Error unassigning user", { status: 400 })
    }
}
