"use client"

import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { clientSchema } from "@/lib/validations"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Textarea } from "@/components/ui/textarea"
import { ClientStatus, SourceType } from "@prisma/client"
import { toast } from "sonner"
import { useRouter } from "next/navigation"

type ClientFormValues = z.infer<typeof clientSchema>

interface ClientFormProps {
    initialData?: any
    users: { id: string; fullName: string }[]
    clientId?: string
}

export function ClientForm({ initialData, users, clientId }: ClientFormProps) {
    const router = useRouter()
    const [loading, setLoading] = useState(false)

    const form = useForm<ClientFormValues>({
        resolver: zodResolver(clientSchema) as any,
        defaultValues: initialData || {
            name: "",
            status: ClientStatus.IN_PROGRESS,
            budget: 0,
        },
    })

    const onSubmit = async (data: ClientFormValues) => {
        setLoading(true)
        try {
            const url = clientId ? `/api/clients/${clientId}` : "/api/clients"
            const method = clientId ? "PATCH" : "POST"

            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data),
            })

            if (!res.ok) {
                throw new Error(await res.text())
            }

            toast.success(clientId ? "Client updated" : "Client created")
            router.refresh()
            if (!clientId) {
                router.push("/clients")
            }
        } catch (error: any) {
            toast.error(error.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
                <div className="grid grid-cols-2 gap-4">
                    <FormField
                        control={form.control}
                        name="name"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Name</FormLabel>
                                <FormControl><Input {...field} /></FormControl>
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
                                <Select onValueChange={field.onChange} defaultValue={field.value}>
                                    <FormControl>
                                        <SelectTrigger><SelectValue placeholder="Select status" /></SelectTrigger>
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
                        name="targetologistId"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Targetologist</FormLabel>
                                <Select onValueChange={field.onChange} defaultValue={field.value || undefined}>
                                    <FormControl>
                                        <SelectTrigger><SelectValue placeholder="Select user" /></SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                        {users.map((u) => (
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
                        name="budget"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Budget</FormLabel>
                                <FormControl><Input type="number" {...field} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                {/* Additional fields */}
                <div className="grid grid-cols-3 gap-4">
                    <FormField control={form.control} name="phone" render={({ field }) => (<FormItem><FormLabel>Phone</FormLabel><FormControl><Input {...field} /></FormControl></FormItem>)} />
                    <FormField control={form.control} name="city" render={({ field }) => (<FormItem><FormLabel>City</FormLabel><FormControl><Input {...field} /></FormControl></FormItem>)} />
                    <FormField control={form.control} name="tg" render={({ field }) => (<FormItem><FormLabel>Telegram</FormLabel><FormControl><Input {...field} /></FormControl></FormItem>)} />
                </div>

                <Button type="submit" disabled={loading}>
                    {loading ? "Saving..." : "Save Client"}
                </Button>
            </form>
        </Form>
    )
}
