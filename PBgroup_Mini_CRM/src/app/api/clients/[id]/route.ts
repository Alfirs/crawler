import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { clientSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"

export async function GET(
    req: Request,
    { params }: { params: Promise<{ id: string }> } // Params is a Promise in Next.js 15+, but I am using 16.1.4, which treats params as Promise in newer versions? Wait. Next 14 App Router params are plain objects. But Next 15+ they are Promises. I'm on Next 16. So I should AWAIT params.
    // Actually, let's play safe. If I await params, I need to check Next.js version specifics. Next 16 is Canary? Or is it 15 stable? "next": "16.1.4". That must be newest.
    // In Next.js 15, params are async. So I should await.
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
    if (session.user.role === Role.EDITOR || session.user.role === Role.VIEWER) {
        const isAssigned = client.assignments.some(a => a.userId === session.user.id)
        if (!isAssigned) {
            // Log forbidden attempt?
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
    if (session.user.role === Role.VIEWER) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    // Access check for Editor
    if (session.user.role === Role.EDITOR) {
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

        const updated = await prisma.client.update({
            where: { id },
            data: {
                ...body,
                sources: undefined, // Handle sources separately if passed? 
                // If sources passed, delete old and create new? Or just append?
                // Simple approach: if sources is in body, replace.
            }
        })

        if (body.sources) {
            // Transaction to replace sources?
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
