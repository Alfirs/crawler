import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { prisma } from "@/lib/prisma"
import { Role } from "@prisma/client"
import { redirect } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export default async function StatsPage() {
    const session = await getServerSession(authOptions)
    if (!session) redirect("/login")

    const whereClause: any = {}

    if (session.user.role === Role.EDITOR || session.user.role === Role.VIEWER) {
        whereClause.assignments = {
            some: {
                userId: session.user.id,
            },
        }
    }

    const clients = await prisma.client.findMany({
        where: whereClause,
        orderBy: { createdAt: "desc" },
    })

    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">Statistics</h1>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {clients.map(client => (
                    <Card key={client.id} className="hover:bg-slate-50 dark:hover:bg-zinc-900 transition-colors">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">
                                {client.name}
                            </CardTitle>
                            <div className={`h-2 w-2 rounded-full ${client.status === 'IN_PROGRESS' ? 'bg-green-500' : 'bg-gray-300'}`} />
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-col gap-2 mt-2">
                                <Link href={`/stats/${client.id}`} >
                                    <Button variant="outline" className="w-full justify-start">
                                        Statistics Table
                                    </Button>
                                </Link>
                                <Link href={`/stats/${client.id}/details`}>
                                    <Button variant="outline" className="w-full justify-start">
                                        Project Details
                                    </Button>
                                </Link>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    )
}
