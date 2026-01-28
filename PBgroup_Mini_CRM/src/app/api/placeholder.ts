import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { z } from "zod"
import { getDaysInMonth, set } from "date-fns"

const addMonthSchema = z.object({
    year: z.number().int().min(2020).max(2030),
    month: z.number().int().min(0).max(11) // 0-indexed month
})

export async function POST(
    req: Request,
    { params }: { params: Promise<{ id: string }> } // id is clientId (from folder [id]) ? No folder is clients/id... wait
) {
    // Route: /api/clients/[id]/stats/month - Wait, I should make it clean.
    // Previous stats API was /api/stats/[rowId] for patch.
    // And /api/clients/[id]/stats for GET.
    // I can reuse /api/clients/[id]/stats POST but body distinguishes action.
    // Or simpler: /api/clients/[id]/stats/init-month

    // Actually the params structure depends on folder.
    // I'll create `src/app/api/clients/[id]/stats/init/route.ts`.

    return new NextResponse("Use init endpoint", { status: 404 })
}
