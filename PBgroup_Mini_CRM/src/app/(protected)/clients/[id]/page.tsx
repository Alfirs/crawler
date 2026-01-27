import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { ClientForm } from "./client-form"
import { Role } from "@prisma/client"
import { notFound, redirect } from "next/navigation"

export default async function ClientPage({ params }: { params: Promise<{ id: string }> }) {
    const session = await getServerSession(authOptions)
    if (!session) redirect("/login")

    const { id } = await params

    const client = await prisma.client.findUnique({
        where: { id },
        include: {
            sources: true,
            assignments: true
        }
    })

    if (!client) notFound()

    // Access Security Check
    if (session.user.role === Role.EDITOR || session.user.role === Role.VIEWER) {
        const isAssigned = client.assignments.some(a => a.userId === session.user.id)
        if (!isAssigned) {
            return <div>Forbidden: You do not have access to this client.</div>
        }
    }

    const canEdit = session.user.role !== Role.VIEWER

    // Fetch employees for dropdowns (only need if editing allowed, but nice to show names)
    // Optimization: Only fetch needed fields
    const employees = await prisma.user.findMany({
        select: { id: true, fullName: true, role: true, specialization: true, createdAt: true, deletedAt: true, updatedAt: true, login: true, passwordHash: true }, // Need full User object to satisfy type? Or pick?
        // Type in ClientForm is User[].
        // passwordHash etc needed.
        where: { deletedAt: null }
    })

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <h1 className="text-2xl font-bold">Client: {client.name}</h1>
            <div className="bg-white dark:bg-zinc-950 p-6 rounded-lg shadow-sm border">
                <ClientForm
                    initialData={client}
                    employees={employees as any} // Casting to User[] 
                    canEdit={canEdit}
                />
            </div>
        </div>
    )
}
