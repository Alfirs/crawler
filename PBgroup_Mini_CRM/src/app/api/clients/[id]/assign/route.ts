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

        const created = await prisma.clientAssignment.create({
            data: {
                clientId: id,
                userId: userId
            }
        })

        await logAudit({
            userId: session.user.id,
            action: "ASSIGN_USER",
            entityType: "ASSIGNMENT",
            entityId: created.id,
            after: { clientId: id, assignedUserId: userId }
        })

        return NextResponse.json(created)
    } catch (error) {
        // Unique constraint violation check?
        return new NextResponse("Error assigning user", { status: 400 })
    }
}
