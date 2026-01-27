import { db } from "@/lib/db"
import { Role } from "@prisma/client"

export type AuditAction =
    | "LOGIN"
    | "LOGOUT"
    | "CREATE"
    | "UPDATE"
    | "DELETE" // For soft deletes or attempts
    | "ASSIGN"
    | "UNASSIGN"
    | "UPLOAD"
    | "FORBIDDEN_ATTEMPT"

export type AuditEntityType =
    | "CLIENT"
    | "STAT_ROW"
    | "DETAIL_ITEM"
    | "USER"
    | "ASSIGNMENT"
    | "FILE"
    | "AUTH"

interface LogAuditParams {
    userId: string | null // Nullable for failed auth attempts
    action: AuditAction
    entityType: AuditEntityType
    entityId: string
    before?: any
    after?: any
    ip?: string
    userAgent?: string
}

export async function logAudit({
    userId,
    action,
    entityType,
    entityId,
    before,
    after,
    ip,
    userAgent,
}: LogAuditParams) {
    try {
        await db.auditLog.create({
            data: {
                userId,
                action,
                entityType,
                entityId,
                beforeJson: before ? JSON.parse(JSON.stringify(before)) : undefined,
                afterJson: after ? JSON.parse(JSON.stringify(after)) : undefined,
                ip,
                userAgent,
            },
        })
    } catch (error) {
        console.error("Failed to write audit log:", error)
        // We don't throw here to avoid breaking the main flow, but in high-security context we might want to.
    }
}
