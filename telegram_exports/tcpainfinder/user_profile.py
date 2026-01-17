from __future__ import annotations

from dataclasses import dataclass

from tcpainfinder.models import Category


@dataclass(frozen=True)
class OfferTemplate:
    offer_id: str
    title: str
    for_whom: str
    result: str
    timeline: str
    price: str
    needs: tuple[str, ...]
    quick_start: str


PRIMARY_CATEGORIES: tuple[Category, ...] = (
    "Bots_TG_WA_VK",
    "Integrations_Sheets_CRM_n8n",
    "Autoposting_ContentFactory",
    "Parsing_Analytics_Reports",
    "Landing_Sites",
)


CATEGORY_QUICK_SOLUTIONS: dict[Category, str] = {
    "Bots_TG_WA_VK": "Мини-бот: меню/кнопки, прием заявок, уведомление админу, передача менеджеру (1-2 дня).",
    "Integrations_Sheets_CRM_n8n": "Интеграция/n8n: заявки из формы/бота -> Sheets/CRM + уведомления + статусная таблица (1-2 дня).",
    "Autoposting_ContentFactory": "Контент-завод: таблица тем -> генерация -> автопостинг + очередь публикаций (MVP за 1-2 дня).",
    "Parsing_Analytics_Reports": "Парсинг/отчет: выгрузка данных -> Google Sheets + автообновление + 3-5 метрик (1-2 дня).",
    "Landing_Sites": "Лендинг: простая страница + форма/квиз + базовая аналитика + интеграция заявок в таблицу (1-2 дня).",
    "Sales_CRM_Process": "Быстрый комплект продаж: оффер + 2-3 скрипта + простая CRM/таблица + план касаний (1-2 дня).",
    "Design_Copy": "Могу подключить сбор заявок/таблицу/уведомления, но дизайн/копирайт не беру как основной продукт.",
    "Other": "Могу автоматизировать часть процесса: заявки -> таблица -> уведомления (1-2 дня).",
}


CATEGORY_PRICE_RANGES: dict[Category, str] = {
    "Bots_TG_WA_VK": "15 000-25 000 руб (+ поддержка 3 000-7 000 руб/мес)",
    "Integrations_Sheets_CRM_n8n": "12 000-30 000 руб",
    "Autoposting_ContentFactory": "12 000-30 000 руб",
    "Parsing_Analytics_Reports": "10 000-20 000 руб",
    "Landing_Sites": "15 000-30 000 руб",
    "Sales_CRM_Process": "12 000-25 000 руб",
    "Design_Copy": "0 руб (не беру как основной продукт)",
    "Other": "10 000-20 000 руб",
}


CATEGORY_TO_OFFER_ID: dict[Category, str] = {
    "Bots_TG_WA_VK": "OFFER_1_BOT_LEADS",
    "Integrations_Sheets_CRM_n8n": "OFFER_2_N8N_INTEGRATION",
    "Autoposting_ContentFactory": "OFFER_3_CONTENT_FACTORY",
    "Parsing_Analytics_Reports": "OFFER_4_PARSING_REPORTS",
    "Landing_Sites": "OFFER_5_LANDING",
    "Sales_CRM_Process": "OFFER_2_N8N_INTEGRATION",
    "Design_Copy": "OFFER_2_N8N_INTEGRATION",
    "Other": "OFFER_2_N8N_INTEGRATION",
}


OFFERS: tuple[OfferTemplate, ...] = (
    OfferTemplate(
        offer_id="OFFER_1_BOT_LEADS",
        title="Бот + заявки в таблицу за 48 часов",
        for_whom="тем, кто получает заявки в Telegram/WhatsApp/VK и хочет быстро навести порядок",
        result="Соберу мини-бота: кнопки/меню, прием заявок, уведомление админу, запись в Google Sheets/CRM.",
        timeline="1-2 дня",
        price="15 000-25 000 руб",
        needs=(
            "что бот должен делать (3-7 пунктов)",
            "тексты для кнопок/сообщений (можно черновик)",
            "куда складывать заявки (Sheets/CRM) и кто получает уведомления",
        ),
        quick_start="Сегодня: коротко уточняю требования и собираю черновой сценарий/прототип. Завтра: рабочая версия + тест.",
    ),
    OfferTemplate(
        offer_id="OFFER_2_N8N_INTEGRATION",
        title="Интеграция n8n: заявки -> Sheets/CRM + уведомления",
        for_whom="тем, у кого заявки приходят из разных мест и теряются",
        result="Настрою связку: форма/бот -> Google Sheets/CRM -> уведомления -> статусная таблица задач (через n8n/Make).",
        timeline="1-2 дня",
        price="12 000-30 000 руб",
        needs=(
            "откуда приходят заявки (форма/бот/почта/чат)",
            "какие поля нужны и куда сохранять",
            "куда слать уведомления и кто отвечает",
        ),
        quick_start="Сегодня: фиксируем поля и маршрут. Завтра: собираю интеграцию, тестируем на 5-10 заявках.",
    ),
    OfferTemplate(
        offer_id="OFFER_3_CONTENT_FACTORY",
        title="Автопостинг / контент-завод из таблицы",
        for_whom="тем, кто ведет канал и хочет регулярные посты без ручной рутины",
        result="Сделаю MVP: таблица тем -> генерация текста -> очередь -> автопостинг в канал/соцсеть (через n8n/Make).",
        timeline="1-2 дня (MVP)",
        price="12 000-30 000 руб",
        needs=(
            "куда постим и какой формат поста",
            "таблица/структура тем (можно наброском)",
            "2-3 примера постов, которые нравятся",
        ),
        quick_start="Сегодня: согласуем шаблон поста и поля таблицы. Завтра: автопостинг + очередь + тестовый прогон.",
    ),
    OfferTemplate(
        offer_id="OFFER_4_PARSING_REPORTS",
        title="Парсинг -> Google Sheets + автоотчет",
        for_whom="тем, кому нужны данные/выгрузка и понятные цифры",
        result="Соберу сбор данных/парсинг -> таблица + автообновление + 3-5 метрик/отчет.",
        timeline="1-2 дня",
        price="10 000-20 000 руб",
        needs=(
            "что и откуда нужно собрать",
            "пример нужной таблицы/отчета",
            "как часто обновлять (раз в день/час/по кнопке)",
        ),
        quick_start="Сегодня: уточняю источник и формат. Завтра: готовая выгрузка + обновление + короткая инструкция.",
    ),
    OfferTemplate(
        offer_id="OFFER_5_LANDING",
        title="Лендинг + форма + аналитика",
        for_whom="тем, кому нужен быстрый лендинг под оффер и сбор заявок",
        result="Соберу простой лендинг (Tilda) + форма/квиз + базовая аналитика + интеграция заявок в таблицу.",
        timeline="1-2 дня",
        price="15 000-30 000 руб",
        needs=(
            "оффер и аудитория (2-3 предложения)",
            "пример структуры или конкурента (можно словами)",
            "куда отправлять заявки (таблица/CRM)",
        ),
        quick_start="Сегодня: структура + блоки. Завтра: сборка + форма + интеграция + запуск.",
    ),
)

