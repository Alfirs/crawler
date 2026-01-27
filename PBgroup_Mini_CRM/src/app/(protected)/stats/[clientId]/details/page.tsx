import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { Role, DetailCategory } from "@prisma/client"
import { notFound, redirect } from "next/navigation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DetailList } from "./detail-list"

export default async function ClientDetailsPage({ params }: { params: Promise<{ clientId: string }> }) {
    const session = await getServerSession(authOptions)
    if (!session) redirect("/login")

    const { clientId } = await params

    // Access Security Check
    if (session.user.role === Role.EDITOR || session.user.role === Role.VIEWER) {
        const isAssigned = await prisma.clientAssignment.findUnique({
            where: { clientId_userId: { clientId, userId: session.user.id } }
        })
        if (!isAssigned) return <div>Forbidden</div>
    }

    const client = await prisma.client.findUnique({ where: { id: clientId } })
    if (!client) notFound()

    // Fetch all items
    const allItems = await prisma.detailItem.findMany({
        where: { clientId },
        include: { files: true },
        orderBy: { createdAt: "desc" }
    })

    // Group by category? Or just filter in render
    // Passing filtered arrays to components

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">Details: {client.name}</h1>

            <Tabs defaultValue={DetailCategory.PAINS} className="w-full">
                <TabsList className="grid w-full grid-cols-5 h-auto">
                    {Object.values(DetailCategory).map(cat => (
                        <TabsTrigger key={cat} value={cat} className="text-xs sm:text-sm">{cat}</TabsTrigger>
                    ))}
                </TabsList>

                {Object.values(DetailCategory).map(cat => (
                    <TabsContent key={cat} value={cat} className="mt-4">
                        <DetailList
                            items={allItems.filter(i => i.category === cat)}
                            category={cat}
                            clientId={clientId}
                            isViewer={session.user.role === Role.VIEWER}
                        />
                    </TabsContent>
                ))}
            </Tabs>
        </div>
    )
}
