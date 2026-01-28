import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { NextResponse } from "next/server"
import { Role } from "@prisma/client"
import { writeFile, mkdir } from "fs/promises"
import { join } from "path"
import { logAudit } from "@/lib/audit"

export async function POST(req: Request) {
    const session = await getServerSession(authOptions)
    if (!session) return new NextResponse("Unauthorized", { status: 401 })

    // Viewer cannot upload? Requirement says detail creation/editing forbidden for editor... wait?
    // 4.7: "удаление запрещено EDITOR". So Editor CAN add/edit.
    // 3) EDITOR: "может редактировать информацию и добавлять записи"
    // Uploads are part of details (Creatives). So Editor CAN upload.
    // Viewer cannot. (4.0 VIEWER: only view).

    if (session.user.role === Role.SALES) return new NextResponse("Forbidden", { status: 403 })

    try {
        const formData = await req.formData()
        const file = formData.get("file") as File | null
        const clientId = formData.get("clientId") as string | null
        const detailItemId = formData.get("detailItemId") as string | null // Optional linkage

        if (!file) return NextResponse.json({ error: "No file provided" }, { status: 400 })
        if (!clientId) return NextResponse.json({ error: "No clientId provided" }, { status: 400 })

        // If Editor, check Assignment
        if (session.user.role === Role.TARGETOLOGIST) {
            const isAssigned = await prisma.clientAssignment.findUnique({
                where: { clientId_userId: { clientId: clientId, userId: session.user.id } }
            })
            if (!isAssigned) return new NextResponse("Forbidden", { status: 403 })
        }

        const buffer = Buffer.from(await file.arrayBuffer())
        const filename = `${Date.now()}_${file.name.replace(/\s+/g, "_")}`
        const relativePath = `/uploads/${filename}`
        const uploadDir = join(process.cwd(), "public", "uploads")

        // Ensure dir exists
        await mkdir(uploadDir, { recursive: true })

        const absolutePath = join(uploadDir, filename)
        await writeFile(absolutePath, buffer)

        // Save metadata
        const fileAsset = await prisma.fileAsset.create({
            data: {
                clientId,
                detailItemId, // can be null
                originalName: file.name,
                mimeType: file.type,
                size: file.size,
                diskPath: relativePath,
                uploadedById: session.user.id
            }
        })

        await logAudit({
            userId: session.user.id,
            action: "UPLOAD_FILE",
            entityType: "FILE",
            entityId: fileAsset.id,
            after: { filename: file.name, path: relativePath }
        })

        return NextResponse.json(fileAsset)
    } catch (error) {
        console.error(error)
        return NextResponse.json({ error: "Upload failed" }, { status: 500 })
    }
}
