import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { clientSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"

export async function GET(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    const { id } = await params

    const client = await prisma.client.findUnique({
        where: { id },
        include: {
            targetologist: { select: { fullName: true, id: true } },
            projectManager: { select: { fullName: true, id: true } },
            assignments: { include: { user: { select: { fullName: true, role: true } } } },
            sources: true,
        },
    })

    if (!client) return new NextResponse("Not Found", { status: 404 })

    // Access check
    if (session.user.role === Role.TARGETOLOGIST || session.user.role === Role.SALES) {
        const isAssigned = client.assignments.some(a => a.userId === session.user.id)
        if (!isAssigned) {
            await logAudit({
                userId: session.user.id,
                action: "ACCESS_DENIED",
                entityType: "CLIENT",
                entityId: id,
            })
            return new NextResponse("Forbidden", { status: 403 })
        }
    }

    return NextResponse.json(client)
}

export async function PATCH(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    const { id } = await params

    // Viewer cannot edit
    if (session.user.role === Role.SALES) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    // Access check for Editor
    if (session.user.role === Role.TARGETOLOGIST) {
        const assignment = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId: id, userId: session.user.id } }
        })
        if (!assignment) {
            await logAudit({
                userId: session.user.id,
                action: "EDIT_DENIED",
                entityType: "CLIENT",
                entityId: id,
            })
            return new NextResponse("Forbidden", { status: 403 })
        }
    }

    try {
        const json = await req.json()
        // Validation: make partial
        const body = clientSchema.partial().parse(json)

        // Helper: get current state for log
        const current = await prisma.client.findUnique({ where: { id } })

        // Detect if assignment fields were explicitly set (including to null)
        const targetologistChanged = 'targetologistId' in json
        const projectManagerChanged = 'projectManagerId' in json

        const updated = await prisma.$transaction(async (tx) => {
            // Update client with the new data
            const client = await tx.client.update({
                where: { id },
                data: {
                    ...body,
                    sources: undefined, // Handle sources separately
                }
            })

            // Handle targetologist assignment (when new value is set, not null)
            if (targetologistChanged && body.targetologistId) {
                await tx.clientAssignment.upsert({
                    where: { clientId_userId: { clientId: id, userId: body.targetologistId } },
                    create: { clientId: id, userId: body.targetologistId },
                    update: {}
                })
            }

            // Handle project manager assignment (when new value is set, not null)
            if (projectManagerChanged && body.projectManagerId) {
                await tx.clientAssignment.upsert({
                    where: { clientId_userId: { clientId: id, userId: body.projectManagerId } },
                    create: { clientId: id, userId: body.projectManagerId },
                    update: {}
                })
            }

            return client
        })

        if (body.sources) {
            await prisma.$transaction([
                prisma.clientSource.deleteMany({ where: { clientId: id } }),
                prisma.clientSource.createMany({
                    data: body.sources.map(s => ({ clientId: id, sourceType: s }))
                })
            ])
        }

        await logAudit({
            userId: session.user.id,
            action: "UPDATE_CLIENT",
            entityType: "CLIENT",
            entityId: id,
            before: current,
            after: updated
        })

        return NextResponse.json(updated)
    } catch (error) {
        console.error(error)
        return new NextResponse("Invalid Request", { status: 400 })
    }
}

export async function DELETE(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    // Only Admin or Admin Staff can delete
    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { id } = await params

    const client = await prisma.client.findUnique({ where: { id } })
    if (!client) return new NextResponse("Not Found", { status: 404 })

    const updated = await prisma.client.update({
        where: { id },
        data: { deletedAt: new Date() }
    })

    await logAudit({
        userId: session.user.id,
        action: "DELETE_CLIENT",
        entityType: "CLIENT",
        entityId: id,
        before: client,
        after: updated
    })

    return NextResponse.json(updated)
}
