
import { ClientStatus, Role, DetailCategory, SourceType } from "@prisma/client"

export const CLIENT_STATUS_LABELS: Record<ClientStatus, string> = {
    IN_PROGRESS: "В работе",
    STOPPED: "Остановлен",
    WAITING_RENEWAL: "Ждет продления",
    REGISTRATION: "Оформление",
    ANALYSIS: "Анализ",
}

export const ROLE_LABELS: Record<Role, string> = {
    ADMIN: "Администратор",
    PROJECT: "Проджект",
    TARGETOLOGIST: "Таргетолог",
    SALES: "Продажи",
    ADMIN_STAFF: "Админ. персонал",
}

export const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
    VK: "ВКонтакте",
    DIRECT: "Яндекс.Директ",
    AVITO: "Авито",
    META: "Meta (FB/Inst)",
    TELEGRAM: "Телеграм",
}

export const DETAIL_CATEGORY_LABELS: Record<DetailCategory, string> = {
    PAINS: "Боли",
    CREATIVES: "Креативы",
    AUDIENCES: "Аудитории",
    HYPOTHESES: "Гипотезы",
    TEXTS: "Тексты",
}
