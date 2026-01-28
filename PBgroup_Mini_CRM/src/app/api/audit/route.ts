import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { Role } from "@prisma/client"

export async function GET(req: Request) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    if (session.user.role !== Role.ADMIN && session.user.role !== Role.ADMIN_STAFF) {
        return new NextResponse("Forbidden", { status: 403 })
    }

    const { searchParams } = new URL(req.url)
    const limit = parseInt(searchParams.get("limit") || "100")

    const logs = await prisma.auditLog.findMany({
        orderBy: { createdAt: "desc" },
        take: limit,
        include: {
            user: {
                select: {
                    fullName: true
                }
            }
        }
    })

    return NextResponse.json(logs)
}
