import { prisma } from "../src/lib/prisma"

async function main() {
    console.log("Connecting to DB...");
    try {
        const count = await prisma.user.count();
        console.log(`Success! User count: ${count}`);
        const admin = await prisma.user.findFirst({ where: { role: 'ADMIN' } });
        console.log(`Admin found: ${admin?.login}`);
    } catch (e) {
        console.error("DB Error:", e);
        process.exit(1);
    }
}

main();
