import { Role } from "@prisma/client"
import { Session } from "next-auth"
import { db } from "@/lib/db"

export function requireRole(session: Session | null, allowedRoles: Role[]) {
    if (!session || !session.user) {
        throw new Error("Unauthorized")
    }
    if (!allowedRoles.includes(session.user.role as Role)) {
        throw new Error("Forbidden: Insufficient Role")
    }
}

/**
 * Checks if the user has access to a specific client.
 * ADMIN/MANAGER: Always access.
 * EDITOR/VIEWER: Must be assigned.
 * Returns true if access allowed, false otherwise.
 */
export async function checkClientAccess(session: Session | null, clientId: string): Promise<boolean> {
    if (!session || !session.user) return false

    const role = session.user.role as Role

    if (role === 'ADMIN' || role === 'ADMIN_STAFF') return true

    // For EDITOR / VIEWER, check assignment
    const assignment = await db.clientAssignment.findUnique({
        where: {
            clientId_userId: {
                clientId,
                userId: session.user.id
            }
        }
    })

    return !!assignment
}

/**
 * Returns a Prisma `where` clause for filtering clients based on user role.
 */
export function getAccessibleClientsWhere(session: Session | null) {
    if (!session || !session.user) return { id: "impossible" } // Fail safe

    const role = session.user.role as Role

    if (role === 'ADMIN' || role === 'ADMIN_STAFF') {
        return {} // No filter, return all
    }

    return {
        assignments: {
            some: {
                userId: session.user.id
            }
        }
    }
}
