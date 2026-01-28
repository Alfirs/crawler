import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { z } from "zod"

const pauseSchema = z.object({
    startDate: z.coerce.date(),
    endDate: z.coerce.date().optional(),
    comment: z.string().optional(),
})

export async function POST(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    const { id: clientId } = await params

    try {
        const body = await req.json()
        const { startDate, endDate, comment } = pauseSchema.parse(body)

        const pause = await prisma.clientPause.create({
            data: {
                clientId,
                startDate,
                endDate,
                comment,
                createdById: session.user.id
            }
        })

        return NextResponse.json(pause)
    } catch (error) {
        console.error("PAUSE_CREATE_ERROR", error)
        return new NextResponse("Internal Error", { status: 500 })
    }
}
