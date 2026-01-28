import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { clientSchema } from "@/lib/validations"
import { logAudit } from "@/lib/audit"
import { Role } from "@prisma/client"

export async function GET(req: Request) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    const { searchParams } = new URL(req.url)
    const status = searchParams.get("status")

    const whereClause: any = {}
    if (status) whereClause.status = status

    // Row-level security for EDITOR/VIEWER
    if (session.user.role === Role.TARGETOLOGIST || session.user.role === Role.SALES) {
        whereClause.assignments = {
            some: {
                userId: session.user.id,
            },
        }
    }

    try {
        const clients = await prisma.client.findMany({
            where: whereClause,
            include: {
                targetologist: { select: { fullName: true, id: true } },
                projectManager: { select: { fullName: true, id: true } },
                assignments: true, // simplified logic, may need more if showing assigned users
                sources: true,
            },
            orderBy: { createdAt: "desc" },
        })

        return NextResponse.json(clients)
    } catch (error) {
        console.error(error)
        return new NextResponse("Internal Error", { status: 500 })
    }
}

export async function POST(req: Request) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    try {
        const json = await req.json()
        const body = clientSchema.parse(json)

        const client = await prisma.client.create({
            data: {
                name: body.name,
                status: body.status,
                budget: body.budget,
                paymentDate: body.paymentDate,
                tg: body.tg,
                contactName: body.contactName,
                phone: body.phone,
                business: body.business,
                city: body.city,
                hasCrm: body.hasCrm,
                funnel: body.funnel,
                interestScore: body.interestScore,
                utmSource: body.utmSource,
                utmMedium: body.utmMedium,
                utmContent: body.utmContent,
                utmTerm: body.utmTerm,
                targetologistId: body.targetologistId,
                projectManagerId: body.projectManagerId, // Fixed typo from body.prodjectManagerId
            },
        })

        // Also add explicit assignment if targetologist/pm set?
        // Requirement says: "Assign" is distinct action? 
        // Or if we set targetologistId, should we add to Assignment table?
        // Section 4.3: "Таргетолог (пользователь)" - implies Single Field.
        // Section 5: "ClientAssignment (many-to-many user <-> client)".
        // "Row-level access ... проверять, что client_id назначен этому пользователю" (via Assignment).
        // So if Targeolog is just display, we ALSO need to assign access.
        // I will auto-assign access if targetologistId/projectManagerId are provided.

        const assignmentsToCheck = []
        if (body.targetologistId) assignmentsToCheck.push(body.targetologistId)
        if (body.projectManagerId) assignmentsToCheck.push(body.projectManagerId)

        for (const userId of assignmentsToCheck) {
            // IDK if user exists, but prisma will throw if FK fails.
            // Check if assignment exists?
            await prisma.clientAssignment.upsert({
                where: { clientId_userId: { clientId: client.id, userId } },
                create: { clientId: client.id, userId },
                update: {},
            })
        }

        if (body.sources) {
            await prisma.clientSource.createMany({
                data: body.sources.map(s => ({ clientId: client.id, sourceType: s }))
            })
        }

        await logAudit({
            userId: session.user.id,
            action: "CREATE_CLIENT",
            entityType: "CLIENT",
            entityId: client.id,
            after: body,
        })

        return NextResponse.json(client)
    } catch (error) {
        if (error instanceof Error) {
            console.error("POST client error:", error.message)
        }
        return new NextResponse("Invalid Request", { status: 400 })
    }
}
