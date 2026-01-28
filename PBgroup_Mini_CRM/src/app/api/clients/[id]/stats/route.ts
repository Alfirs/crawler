import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { statRowSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"

export async function GET(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    const { id } = await params

    // Access check
    if (session.user.role === Role.TARGETOLOGIST || session.user.role === Role.SALES) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId: id, userId: session.user.id } }
        })
        if (!isAssigned) return new NextResponse("Forbidden", { status: 403 })
    }

    const stats = await prisma.statRow.findMany({
        where: { clientId: id },
        orderBy: { date: "desc" }
    })

    return NextResponse.json(stats)
}

export async function POST(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    // Viewer cannot add stats
    if (session.user.role === Role.SALES) return new NextResponse("Forbidden", { status: 403 })

    const { id } = await params

    // Editor check
    if (session.user.role === Role.TARGETOLOGIST) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId: id, userId: session.user.id } }
        })
        if (!isAssigned) return new NextResponse("Forbidden", { status: 403 })
    }

    try {
        const json = await req.json()
        const body = statRowSchema.parse(json)

        const stat = await prisma.statRow.create({
            data: {
                clientId: id,
                ...body,
                createdById: session.user.id
            }
        })

        await logAudit({
            userId: session.user.id,
            action: "CREATE_STAT",
            entityType: "STAT",
            entityId: stat.id,
            after: body
        })

        return NextResponse.json(stat)
    } catch (error) {
        return new NextResponse("Invalid Request", { status: 400 })
    }
}
