import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { detailItemSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role, DetailCategory } from "@prisma/client"

export async function GET(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    const { id } = await params
    const { searchParams } = new URL(req.url)
    const category = searchParams.get("category") as DetailCategory | null

    // Access check
    if (session.user.role === Role.EDITOR || session.user.role === Role.VIEWER) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId: id, userId: session.user.id } }
        })
        if (!isAssigned) return new NextResponse("Forbidden", { status: 403 })
    }

    const where: any = { clientId: id }
    if (category && Object.values(DetailCategory).includes(category)) {
        where.category = category
    }

    const details = await prisma.detailItem.findMany({
        where,
        include: { files: true },
        orderBy: { createdAt: "desc" }
    })

    return NextResponse.json(details)
}

export async function POST(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    if (session.user.role === Role.VIEWER) return new NextResponse("Forbidden", { status: 403 })

    const { id } = await params

    if (session.user.role === Role.EDITOR) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId: id, userId: session.user.id } }
        })
        if (!isAssigned) return new NextResponse("Forbidden", { status: 403 })
    }

    try {
        const json = await req.json()
        const body = detailItemSchema.parse(json)

        const item = await prisma.detailItem.create({
            data: {
                clientId: id,
                category: body.category,
                title: body.title,
                description: body.description,
                createdById: session.user.id
            }
        })

        await logAudit({
            userId: session.user.id,
            action: "CREATE_DETAIL",
            entityType: "DETAIL",
            entityId: item.id,
            after: body
        })

        return NextResponse.json(item)
    } catch (error) {
        console.error(error)
        return new NextResponse("Invalid Request", { status: 400 })
    }
}
