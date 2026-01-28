import { PrismaClient, Role } from "@prisma/client"
import "dotenv/config"
import { hash } from "bcryptjs"

const prisma = new PrismaClient()

async function main() {
    const adminEmail = "admin"
    const adminPassword = "admin1234"
    const hashedPassword = await hash(adminPassword, 12)

    try {
        const admin = await prisma.user.upsert({
            where: { login: adminEmail },
            update: {},
            create: {
                login: adminEmail,
                fullName: "System Admin",
                role: Role.ADMIN,
                passwordHash: hashedPassword,
            },
        })
        console.log({ admin })
    } catch (e) {
        console.error("Error seeding:", e)
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
