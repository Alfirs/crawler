import { writeFile, mkdir } from "fs/promises"
import { join } from "path"
import { randomUUID } from "crypto"

export async function saveFile(file: File, folder: string = "uploads"): Promise<{ path: string; size: number; mime: string; originalName: string }> {
    const bytes = await file.arrayBuffer()
    const buffer = Buffer.from(bytes)

    const uploadDir = join(process.cwd(), "public", folder)
    await mkdir(uploadDir, { recursive: true })

    const ext = file.name.split('.').pop()
    const filename = `${randomUUID()}.${ext}`
    const filepath = join(uploadDir, filename)

    await writeFile(filepath, buffer)

    return {
        path: `/${folder}/${filename}`,
        size: buffer.length,
        mime: file.type,
        originalName: file.name,
    }
}
