import { PrismaClient } from "@prisma/client"
import "dotenv/config"

const prisma = new PrismaClient()

async function main() {
    const rowId = "524f4feb-7a48-46df-b17f-5f629788ac8e"

    const row = await prisma.statRow.findUnique({
        where: { id: rowId }
    })

    if (row) {
        console.log("Found row:")
        console.log("  spend:", row.spend)
        console.log("  reach:", row.reach)
        console.log("  clicks:", row.clicks)
        console.log("  leads:", row.leads)
        console.log("  revenue:", row.revenue)
        console.log("  notes:", row.notes)
    } else {
        console.log("Row not found with id:", rowId)
    }
}

main()
    .then(async () => {
        await prisma.$disconnect()
    })
    .catch(async (e) => {
        console.error(e)
        await prisma.$disconnect()
        process.exit(1)
    })
