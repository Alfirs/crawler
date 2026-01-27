import { z } from "zod"
import { ClientStatus, Role, SourceType, DetailCategory } from "@prisma/client"

export const loginSchema = z.object({
    login: z.string().min(1, "Login is required"),
    password: z.string().min(1, "Password is required"),
})

export const clientSchema = z.object({
    name: z.string().min(1, "Name is required"),
    status: z.nativeEnum(ClientStatus).optional(),
    budget: z.coerce.number().optional(),
    eventDate: z.coerce.date().optional(),
    tg: z.string().optional(),
    contactName: z.string().optional(),
    phone: z.string().optional(),
    business: z.string().optional(),
    city: z.string().optional(),
    hasCrm: z.boolean().optional(),
    funnel: z.string().optional(),
    interestScore: z.coerce.number().min(1).max(10).optional(),
    utmSource: z.string().optional(),
    utmMedium: z.string().optional(),
    utmContent: z.string().optional(),
    utmTerm: z.string().optional(),
    targetologistId: z.string().optional(),
    projectManagerId: z.string().optional(),
    sources: z.array(z.nativeEnum(SourceType)).optional(),
})

export const statRowSchema = z.object({
    date: z.coerce.date(),
    spend: z.coerce.number().default(0),
    reach: z.coerce.number().int().default(0),
    clicks: z.coerce.number().int().default(0),
    leads: z.coerce.number().int().default(0),
    sales: z.coerce.number().int().default(0),
    revenue: z.coerce.number().default(0),
    notes: z.string().optional(),
})

export const detailItemSchema = z.object({
    category: z.nativeEnum(DetailCategory),
    title: z.string().min(1, "Title is required"),
    description: z.string().optional(),
})

export const assignSchema = z.object({
    userId: z.string().uuid(),
})

export const employeeSchema = z.object({
    fullName: z.string().min(1),
    login: z.string().min(3),
    password: z.string().min(6).optional(), // optional on update
    role: z.nativeEnum(Role),
    specialization: z.string().optional(),
})
