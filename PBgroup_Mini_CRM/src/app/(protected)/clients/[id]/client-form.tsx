"use client"

import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { clientSchema } from "@/lib/validations"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import {
    Form,
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
    FormDescription
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Client, ClientStatus, User, SourceType } from "@prisma/client" // Assuming enums are exported
import { useState } from "react"
import { toast } from "sonner"
import { useRouter } from "next/navigation"

interface ClientFormProps {
    initialData: Client & { sources: { sourceType: SourceType }[] }
    employees: User[]
    canEdit: boolean
}

export function ClientForm({ initialData, employees, canEdit }: ClientFormProps) {
    const router = useRouter()
    const [isLoading, setIsLoading] = useState(false)

    const form = useForm({
        resolver: zodResolver(clientSchema),
        defaultValues: {
            name: initialData.name,
            status: initialData.status,
            budget: initialData.budget || undefined,
            eventDate: initialData.eventDate || undefined,
            tg: initialData.tg || "",
            contactName: initialData.contactName || "",
            phone: initialData.phone || "",
            business: initialData.business || "",
            city: initialData.city || "",
            hasCrm: initialData.hasCrm,
            funnel: initialData.funnel || "",
            interestScore: initialData.interestScore || undefined,
            utmSource: initialData.utmSource || "",
            utmMedium: initialData.utmMedium || "",
            utmContent: initialData.utmContent || "",
            utmTerm: initialData.utmTerm || "",
            targetologistId: initialData.targetologistId || undefined,
            projectManagerId: initialData.projectManagerId || undefined,
            sources: initialData.sources.map(s => s.sourceType) as SourceType[]
        } as any,
    })

    // Hack for Source multi-select? 
    // Standard Select doesn't support multiple.
    // Using checkboxes for sources.

    async function onSubmit(values: z.infer<typeof clientSchema>) {
        if (!canEdit) return
        setIsLoading(true)
        try {
            const res = await fetch(`/api/clients/${initialData.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(values),
            })

            if (!res.ok) throw new Error("Failed to update")

            toast.success("Client updated")
            router.refresh()
        } catch (error) {
            toast.error("Update failed")
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                    {/* Left Column: Basic Info */}
                    <div className="space-y-4">
                        <FormField
                            control={form.control}
                            name="name"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Name</FormLabel>
                                    <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="status"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Status</FormLabel>
                                    <Select onValueChange={field.onChange} defaultValue={field.value} disabled={!canEdit}>
                                        <FormControl>
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select status" />
                                            </SelectTrigger>
                                        </FormControl>
                                        <SelectContent>
                                            {Object.values(ClientStatus).map((s) => (
                                                <SelectItem key={s} value={s}>{s}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="city"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>City</FormLabel>
                                    <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <div className="grid grid-cols-2 gap-4">
                            <FormField
                                control={form.control}
                                name="budget"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Budget</FormLabel>
                                        <FormControl><Input type="number" {...field} disabled={!canEdit} /></FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                            <FormField // Simple Date Input
                                control={form.control}
                                name="eventDate"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Event Date</FormLabel>
                                        <FormControl>
                                            <Input
                                                type="date"
                                                value={field.value ? new Date(field.value).toISOString().split('T')[0] : ''}
                                                onChange={(e) => field.onChange(new Date(e.target.value))}
                                                disabled={!canEdit}
                                            />
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                        </div>
                    </div>

                    {/* Right Column: Contact & Details */}
                    <div className="space-y-4">
                        <FormField
                            control={form.control}
                            name="phone"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Phone</FormLabel>
                                    <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="tg"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Telegram</FormLabel>
                                    <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="business"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Niche / Business</FormLabel>
                                    <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="hasCrm"
                            render={({ field }) => (
                                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                                    <FormControl>
                                        <Checkbox
                                            checked={field.value}
                                            onCheckedChange={field.onChange}
                                            disabled={!canEdit}
                                        />
                                    </FormControl>
                                    <div className="space-y-1 leading-none">
                                        <FormLabel>Has CRM?</FormLabel>
                                    </div>
                                </FormItem>
                            )}
                        />
                    </div>
                </div>

                {/* Full width: Funnel & Sources */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <FormField
                        control={form.control}
                        name="funnel"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Funnel Description</FormLabel>
                                <FormControl><Textarea className="h-32" {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <div className="space-y-4">
                        <FormLabel>Sources</FormLabel>
                        <div className="grid grid-cols-2 gap-2">
                            {Object.values(SourceType).map((st) => (
                                <FormField
                                    key={st}
                                    control={form.control}
                                    name="sources"
                                    render={({ field }) => {
                                        return (
                                            <FormItem
                                                key={st}
                                                className="flex flex-row items-start space-x-3 space-y-0"
                                            >
                                                <FormControl>
                                                    <Checkbox
                                                        disabled={!canEdit}
                                                        checked={field.value?.includes(st)}
                                                        onCheckedChange={(checked) => {
                                                            return checked
                                                                ? field.onChange([...(field.value || []), st])
                                                                : field.onChange(
                                                                    field.value?.filter(
                                                                        (value: SourceType) => value !== st
                                                                    )
                                                                )
                                                        }}
                                                    />
                                                </FormControl>
                                                <FormLabel className="font-normal">
                                                    {st}
                                                </FormLabel>
                                            </FormItem>
                                        )
                                    }}
                                />
                            ))}
                        </div>
                    </div>
                </div>

                {/* Assignments */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t">
                    <FormField
                        control={form.control}
                        name="targetologistId"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Targetologist</FormLabel>
                                <Select onValueChange={field.onChange} defaultValue={field.value} disabled={!canEdit}>
                                    <FormControl>
                                        <SelectTrigger>
                                            <SelectValue placeholder="Unassigned" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                        <SelectItem value="unassigned">Unassigned</SelectItem>
                                        {employees.map((u) => (
                                            <SelectItem key={u.id} value={u.id}>{u.fullName}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="projectManagerId"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Project Manager</FormLabel>
                                <Select onValueChange={field.onChange} defaultValue={field.value} disabled={!canEdit}>
                                    <FormControl>
                                        <SelectTrigger>
                                            <SelectValue placeholder="Unassigned" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                        <SelectItem value="unassigned">Unassigned</SelectItem>
                                        {employees.map((u) => (
                                            <SelectItem key={u.id} value={u.id}>{u.fullName}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                {/* UTMs Section (Collapsible or just fields) */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
                    <FormField control={form.control} name="utmSource" render={({ field }) => (
                        <FormItem><FormLabel>UTM Source</FormLabel><FormControl><Input {...field} disabled={!canEdit} /></FormControl></FormItem>
                    )} />
                    <FormField control={form.control} name="utmMedium" render={({ field }) => (
                        <FormItem><FormLabel>UTM Medium</FormLabel><FormControl><Input {...field} disabled={!canEdit} /></FormControl></FormItem>
                    )} />
                </div>

                <Button type="submit" disabled={!canEdit || isLoading}>
                    {isLoading ? "Saving..." : "Save Changes"}
                </Button>
            </form>
        </Form>
    )
}
