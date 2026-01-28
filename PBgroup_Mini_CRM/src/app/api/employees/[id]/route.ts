import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { employeeSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"
import { hash } from "bcryptjs"

export async function PATCH(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { id } = await params

    try {
        const json = await req.json()
        const body = employeeSchema.partial().parse(json)
        const data: Record<string, unknown> = { ...body }

        if (body.password) {
            data.passwordHash = await hash(body.password, 10)
        }
        delete data.password
        delete data.assignedClientIds

        // Use transaction with callback for proper error handling
        const updated = await prisma.$transaction(async (tx) => {
            // Update user data
            const user = await tx.user.update({
                where: { id },
                data
            })

            // If assignments provided, replace them
            if (body.assignedClientIds !== undefined) {
                await tx.clientAssignment.deleteMany({ where: { userId: id } })

                if (body.assignedClientIds.length > 0) {
                    await tx.clientAssignment.createMany({
                        data: body.assignedClientIds.map((cid: string) => ({
                            userId: id,
                            clientId: cid
                        }))
                    })

                    // Bidirectional sync: set targetologistId or projectManagerId based on role
                    const userRole = body.role || user.role
                    if (userRole === 'TARGETOLOGIST') {
                        await tx.client.updateMany({
                            where: { id: { in: body.assignedClientIds } },
                            data: { targetologistId: id }
                        })
                    } else if (userRole === 'PROJECT') {
                        await tx.client.updateMany({
                            where: { id: { in: body.assignedClientIds } },
                            data: { projectManagerId: id }
                        })
                    }
                }
            }

            return user
        })

        // Don't log hash
        delete data.passwordHash

        await logAudit({
            userId: session.user.id,
            action: "UPDATE_USER",
            entityType: "USER",
            entityId: id,
            after: data
        })

        return NextResponse.json({ id: updated.id, fullName: updated.fullName })
    } catch (error) {
        console.error("[EMPLOYEE PATCH] Error:", error)
        return new NextResponse("Invalid Request", { status: 400 })
    }
}

export async function DELETE(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { id } = await params

    const user = await prisma.user.findUnique({ where: { id } })
    if (!user) return new NextResponse("Not Found", { status: 404 })

    // Prevent deleting self?
    if (user.id === session.user.id) {
        return new NextResponse("Cannot delete self", { status: 400 })
    }

    try {
        // Use transaction to clean up all references and hard delete
        await prisma.$transaction(async (tx) => {
            // Remove as targetologist from all clients
            await tx.client.updateMany({
                where: { targetologistId: id },
                data: { targetologistId: null }
            })

            // Remove as projectManager from all clients  
            await tx.client.updateMany({
                where: { projectManagerId: id },
                data: { projectManagerId: null }
            })

            // Delete all client assignments
            await tx.clientAssignment.deleteMany({
                where: { userId: id }
            })

            // HARD DELETE the user (not soft delete)
            await tx.user.delete({
                where: { id }
            })
        })

        await logAudit({
            userId: session.user.id,
            action: "DELETE_USER",
            entityType: "USER",
            entityId: id,
            before: user,
            after: null
        })

        return NextResponse.json({ success: true, deleted: id })
    } catch (error) {
        console.error("[EMPLOYEE DELETE] Error:", error)
        return new NextResponse("Delete failed", { status: 500 })
    }
}
