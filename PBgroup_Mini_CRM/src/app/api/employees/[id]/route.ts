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

    if (session.user.role !== Role.ADMIN && session.user.role !== Role.MANAGER) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { id } = await params

    try {
        const json = await req.json()
        const body = employeeSchema.partial().parse(json)
        const data: any = { ...body }

        if (body.password) {
            data.passwordHash = await hash(body.password, 10)
            delete data.password
        }

        const updated = await prisma.user.update({
            where: { id },
            data
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
        return new NextResponse("Invalid Request", { status: 400 })
    }
}
