
import { PrismaClient } from "@prisma/client"
const prisma = new PrismaClient()

async function main() {
    const rows = await prisma.statRow.findMany({
        orderBy: { updatedAt: 'desc' } // Keep latest
    })

    const seen = new Set<string>()
    const toDelete: string[] = []

    for (const row of rows) {
        // Date to ISO string (date part)
        const dateStr = row.date.toISOString().split('T')[0]
        const key = `${row.clientId}_${dateStr}`

        if (seen.has(key)) {
            toDelete.push(row.id)
        } else {
            seen.add(key)
        }
    }

    console.log(`Found ${toDelete.length} duplicates to delete.`)

    if (toDelete.length > 0) {
        await prisma.statRow.deleteMany({
            where: { id: { in: toDelete } }
        })
        console.log("Deleted duplicates.")
    }
}

main()
    .catch(e => console.error(e))
    .finally(async () => await prisma.$disconnect())
