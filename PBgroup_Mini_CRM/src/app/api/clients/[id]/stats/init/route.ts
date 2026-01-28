import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { z } from "zod"
import { getDaysInMonth, set } from "date-fns"

const initSchema = z.object({
    year: z.number().int().min(2020).max(2030),
    month: z.number().int().min(0).max(11) // 0-indexed
})

export async function POST(
    req: Request,
    { params }: { params: Promise<{ id: string }> } // id is clientId
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    const { id } = await params

    try {
        const body = await req.json()
        const { year, month } = initSchema.parse(body)

        const date = new Date(year, month, 1)
        const days = getDaysInMonth(date)

        const data = []
        for (let i = 1; i <= days; i++) {
            const d = new Date(year, month, i)
            // Ensure UTC midnight or consistent timezone usage?
            // Prisma @db.Date stores date only. JS Date is full timestamp.
            // `new Date(year, month, i)` creates local time.
            // Best to use UTC for storage to avoid shift, OR rely on Prisma handling Date objects to Date column.
            // Ideally: `new Date(Date.UTC(year, month, i))`
            const utcDate = new Date(Date.UTC(year, month, i))

            data.push({
                clientId: id,
                date: utcDate,
                spend: 0,
                reach: 0,
                clicks: 0,
                leads: 0,
                sales: 0,
                revenue: 0,
                createdById: session.user.id
            })
        }

        // Use createMany with skipDuplicates (requires unique constraint)
        const res = await prisma.statRow.createMany({
            data,
            skipDuplicates: true
        })

        return NextResponse.json({ created: res.count })
    } catch (error) {
        console.error("STATS_INIT_ERROR", error)
        return new NextResponse("Internal Error", { status: 500 })
    }
}
