import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"

export async function DELETE(
    req: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    // TODO: Add stricter RBAC here if needed (only Admin/Manager?)

    const { id } = await params

    try {
        await prisma.clientPause.delete({
            where: { id }
        })

        return NextResponse.json({ success: true })
    } catch (error) {
        console.error("PAUSE_DELETE_ERROR", error)
        return new NextResponse("Internal Error", { status: 500 })
    }
}
