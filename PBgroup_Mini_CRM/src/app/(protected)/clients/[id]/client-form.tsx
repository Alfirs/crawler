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
import { Client, ClientStatus, User, SourceType, ClientPause } from "@prisma/client"
import { useState } from "react"
import { toast } from "sonner"
import { useRouter } from "next/navigation"
import { CLIENT_STATUS_LABELS } from "@/lib/dict"
import { ClientPauses } from "./client-pauses"

import { Role } from "@prisma/client"

interface ClientFormProps {
    initialData: Client & { sources: { sourceType: SourceType }[], pauses: ClientPause[] }
    employees: User[]
    canEdit: boolean
    userRole?: Role
}

export function ClientForm({ initialData, employees, canEdit, userRole }: ClientFormProps) {
    const router = useRouter()
    const [isLoading, setIsLoading] = useState(false)

    const form = useForm({
        resolver: zodResolver(clientSchema),
        defaultValues: {
            name: initialData.name,
            status: initialData.status,
            budget: initialData.budget || undefined,
            paymentDate: initialData.paymentDate || undefined,
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
            sources: initialData.sources.map(s => s.sourceType) as SourceType[],
            email: initialData.email || "",
            socialLinks: initialData.socialLinks || "",
            registrationPhone: initialData.registrationPhone || "",
            adAccountEmail: initialData.adAccountEmail || "",
            audience: initialData.audience || "",
            uniqueSellingPoints: initialData.uniqueSellingPoints || "",
            clientGoals: initialData.clientGoals || "",
            advertisingFocus: initialData.advertisingFocus || "",
            competitors: initialData.competitors || "",
            offers: initialData.offers || "",
            clientPains: initialData.clientPains || "",
            serviceDeliveryTime: initialData.serviceDeliveryTime || "",
            geoRadius: initialData.geoRadius || "",
            assetsLink: initialData.assetsLink || "",
            legalName: initialData.legalName || "",
            inn: initialData.inn || "",
            legalAddress: initialData.legalAddress || "",
        } as any,
    })

    async function onSubmit(values: z.infer<typeof clientSchema>) {
        if (!canEdit) return
        setIsLoading(true)
        try {
            // Convert "unassigned" to null for proper API handling
            const payload = {
                ...values,
                targetologistId: values.targetologistId === "unassigned" ? null : values.targetologistId,
                projectManagerId: values.projectManagerId === "unassigned" ? null : values.projectManagerId,
            }

            const res = await fetch(`/api/clients/${initialData.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })

            if (!res.ok) throw new Error("Failed to update")

            toast.success("Клиент обновлен")
            router.refresh()
        } catch (error) {
            toast.error("Ошибка обновления")
        } finally {
            setIsLoading(false)
        }
    }

    async function onDelete() {
        if (!confirm("Вы уверены, что хотите удалить этого клиента? Это действие перенесет его в архив.")) return
        setIsLoading(true)
        try {
            const res = await fetch(`/api/clients/${initialData.id}`, {
                method: "DELETE"
            })
            if (!res.ok) throw new Error("Delete failed")

            toast.success("Клиент удален")
            router.push("/clients")
            router.refresh()
        } catch (e) {
            toast.error("Ошибка удаления")
            setIsLoading(false)
        }
    }

    const canDelete = userRole === Role.ADMIN || userRole === Role.ADMIN_STAFF

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
                {/* Left and Right columns... */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Left Column: Basic Info */}
                    <div className="space-y-4">
                        <FormField
                            control={form.control}
                            name="name"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Имя</FormLabel>
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
                                    <FormLabel>Статус</FormLabel>
                                    <Select onValueChange={field.onChange} defaultValue={field.value} disabled={!canEdit}>
                                        <FormControl>
                                            <SelectTrigger>
                                                <SelectValue placeholder="Выберите статус" />
                                            </SelectTrigger>
                                        </FormControl>
                                        <SelectContent>
                                            {Object.values(ClientStatus).map((s) => (
                                                <SelectItem key={s} value={s}>{CLIENT_STATUS_LABELS[s]}</SelectItem>
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
                                    <FormLabel>Город</FormLabel>
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
                                        <FormLabel>Бюджет</FormLabel>
                                        <FormControl><Input type="number" {...field} disabled={!canEdit} /></FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                            <FormField // Simple Date Input
                                control={form.control}
                                name="paymentDate"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Дата оплаты</FormLabel>
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

                        {/* Validated Client Pause Component */}
                        <ClientPauses pauses={initialData.pauses} clientId={initialData.id} canEdit={canEdit} />

                    </div>

                    {/* Right Column: Contact & Details */}
                    <div className="space-y-4">
                        <FormField
                            control={form.control}
                            name="phone"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Телефон</FormLabel>
                                    <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="email"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Адрес электронной почты</FormLabel>
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
                                    <FormLabel>Telegram (ник)</FormLabel>
                                    <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="socialLinks"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Ссылки (Сайт, ВК, Соцсети)</FormLabel>
                                    <FormControl><Textarea className="h-20" {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="business"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Ниша / Бизнес</FormLabel>
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
                                        <FormLabel>Есть CRM?</FormLabel>
                                    </div>
                                </FormItem>
                            )}
                        />
                    </div>
                </div>

                {/* Registration Data */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t">
                    <h3 className="col-span-full font-medium text-lg">Данные для регистрации кабинета</h3>
                    <FormField
                        control={form.control}
                        name="registrationPhone"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Тел. для регистрации (СМС)</FormLabel>
                                <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="adAccountEmail"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Почта для кабинета</FormLabel>
                                <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                {/* Marketing Survey (The Check-List) */}
                <div className="space-y-4 pt-4 border-t">
                    <h3 className="font-medium text-lg">Анкета клиента (Маркетинг)</h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <FormField
                            control={form.control}
                            name="audience"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Целевая аудитория (Кто покупает?)</FormLabel>
                                    <FormControl><Textarea className="h-24" {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="uniqueSellingPoints"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Преимущества (УТП) / Отличия</FormLabel>
                                    <FormControl><Textarea className="h-24" {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="clientGoals"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Желаемые результаты клиента</FormLabel>
                                    <FormControl><Textarea className="h-24" {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="clientPains"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Боли / Страхи клиентов</FormLabel>
                                    <FormControl><Textarea className="h-24" {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="advertisingFocus"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Акцент в рекламе</FormLabel>
                                    <FormControl><Textarea className="h-24" {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="competitors"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Конкуренты</FormLabel>
                                    <FormControl><Textarea className="h-24" {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="offers"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Акции / Офферы / Предложения</FormLabel>
                                    <FormControl><Textarea className="h-24" {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="serviceDeliveryTime"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel>Сроки исполнения (товар/услуга)</FormLabel>
                                    <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                    </div>
                </div>

                {/* Geo and Assets */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t">
                    <FormField
                        control={form.control}
                        name="geoRadius"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Гео / Радиус / Адрес работы</FormLabel>
                                <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="assetsLink"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Ссылка на материалы (Фото/Видео)</FormLabel>
                                <FormControl><Input placeholder="Яндекс.Диск, Облако..." {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                {/* Legal Info */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t">
                    <FormField
                        control={form.control}
                        name="legalName"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Юр. лицо / ФИО</FormLabel>
                                <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="inn"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>ИНН</FormLabel>
                                <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="legalAddress"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Юр. адрес / Прописка</FormLabel>
                                <FormControl><Input {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                {/* Full width: Funnel & Sources */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <FormField
                        control={form.control}
                        name="funnel"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Описание воронки</FormLabel>
                                <FormControl><Textarea className="h-32" {...field} disabled={!canEdit} /></FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <div className="space-y-4">
                        <FormLabel>Источники трафика</FormLabel>
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
                                <FormLabel>Таргетолог</FormLabel>
                                <Select onValueChange={field.onChange} defaultValue={field.value} disabled={!canEdit}>
                                    <FormControl>
                                        <SelectTrigger>
                                            <SelectValue placeholder="Не назначен" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                        <SelectItem value="unassigned">Не назначен</SelectItem>
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
                                <FormLabel>Проджект-менеджер</FormLabel>
                                <Select onValueChange={field.onChange} defaultValue={field.value} disabled={!canEdit}>
                                    <FormControl>
                                        <SelectTrigger>
                                            <SelectValue placeholder="Не назначен" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                        <SelectItem value="unassigned">Не назначен</SelectItem>
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

                <div className="flex justify-between items-center">
                    <Button type="submit" disabled={!canEdit || isLoading}>
                        {isLoading ? "Сохранение..." : "Сохранить изменения"}
                    </Button>

                    {canDelete && (
                        <Button
                            type="button"
                            variant="destructive"
                            disabled={isLoading}
                            onClick={onDelete}
                        >
                            Удалить клиента
                        </Button>
                    )}
                </div>
            </form>
        </Form>
    )
}
