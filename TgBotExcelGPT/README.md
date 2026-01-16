# Project Intake and Procurement Automation

This document captures the MVP workflow for handling construction project documentation with GPT-4o (via [NeuroAPI](https://neuroapi.host/dashboard/docs/getting-started)), Claude 3.5 Sonnet, and Unstructured.io. The goal is to automate the path from incoming files to the final procurement package with minimal manual effort.

## Stage 1. Project Intake

1. **File upload**  
   - Required bundle: project PDF (scans allowed) and drawing PDF (sharp, uninterrupted lines). Optional: ready-made estimate Excel (used later on stage 5).  
   - Upload channels: webhook form, corporate email (attachments parsed automatically), Telegram bot.
2. **Manual file tagging (MVP)**  
   - The uploader selects checkboxes such as "specification / bill of quantities" and "drawings". Automatic classification is intentionally excluded from the MVP.

## Stage 2. Data Extraction

1. **OCR and parsing**  
   - Use Unstructured.io for OCR/clean-up, then GPT-4o or Claude 3.5 Sonnet to extract materials, equipment, work volumes, dimensions, lengths, and diameters.
2. **Unified structure**  
   - Produce JSON + Excel with columns `No | Name | Quantity | Unit | Source (file + sheet)` for downstream traceability.

## Stage 3. Drawing Analysis and Volume Check

1. **Key dimensions from drawings**  
   - GPT-4o Vision or Claude 3.5 Vision processes drawing PDFs to derive total pipe lengths by diameter, wall/floor/ceiling areas, and counts of typical elements (radiators, grilles, etc.).  
   - В локальном режиме файлы парсятся через `pypdf`/`openpyxl`, формируется упрощённый список позиций.
2. **Comparison with the specification**  
   - После загрузки и разметки и спецификаций, и чертежей система автоматически строит таблицу расхождений и сохраняет в `data/<project_id>/reports/discrepancies_<project>.xlsx` и JSON. Пример строки: "PP pipe D25: spec 87 m vs drawings 102 m (+15 m)".
3. **Discrepancy report**  
   - Экспортируется Excel `Item | In specification | From drawings | Delta | Unit`, плюс JSON-версия.

## Stage 4. Estimator Finalization

The estimator reviews the Excel from stages 2-3, adjusts volumes based on discrepancies, and saves the final estimate manually.

## Stage 5. Uploading the Final Estimate

1. **Excel upload** - via the same webhook/email/Telegram inputs.  
2. **Structural checks** - LLM flags empty rows, invalid units, missing quantities or names, and replies with row numbers when issues exist.  
3. **Filtering** - automatically drop rows representing labor, coefficients, overhead, and indices, keeping only purchasable materials/equipment.  
4. **Name normalization** - GPT-4o merges synonyms (for example, "Pipe PND 32", "PND pipe 32", "Pipe 32 PND").  
5. **Procurement list** - table `Material | Characteristics | Quantity | Unit | Notes` (Excel + JSON artifacts saved per project).

## Stage 6. Supplier Requests

Supplier master data lives in Google Sheets: `Supplier | API available | API URL | Email | Contact`.

1. **Suppliers with API (up to 3 in MVP)**  
   - Send HTTP requests (authenticated via NeuroAPI services if needed), capture price, availability, lead time, and log the result both in Google Sheets and Excel. В текущем MVP поставщики считываются из Google Sheets (или локального JSON), запросы имитируются, а ответы записываются в `workspace/supplier_responses.json`.
2. **Suppliers without API**  
   - Send HTML email with embedded table plus Excel attachment; include unique project ID in the subject.  
   - Every 3 hours the agent polls IMAP, parses replies, runs attachments (PDF/Excel) through Unstructured.io and GPT-4o, performs fuzzy matching with our procurement list, and records prices/lead times. В текущем коде есть заглушка, эмулирующая email-ответы, чтобы можно было тестировать весь сценарий без реального ящика.

## Stage 7. Pricing Summary

Produce Excel + Google Sheets summary: `Material | Quantity | Supplier | Price per unit | Total | Lead time | Response status`. Highlight the minimum price per item (conditional formatting or formulas). В MVP автоматически формируется Excel/JSON `suppliers_<project_id>.*` с пометкой «Лучшая цена».

## Stage 8. Report for the Procurement Manager

Single Excel file with three sheets:
1. Specification vs drawing differences.
2. Final procurement list.
3. Supplier offers with best price highlighting and "no response" markers.  
Send an email notification linking to the file. В MVP это `final_<project_id>.xlsx`, собирающий данные из расхождений, ведомости закупки и ответа поставщиков + JSON-версия для интеграции.

## Stage 9. Final Output

- Primary artifact: Excel workbook.  
- Optional: JSON export.  
- Optional Telegram/email notification to management.

---

### GPT-4o Integration via NeuroAPI

1. Create an API key in NeuroAPI and set up a GPT-4o endpoint.  
2. For OCR/table extraction, call Unstructured.io first, then forward cleaned text or tables to GPT-4o for structured outputs.  
3. For Vision tasks, upload PDFs/images to storage, provide signed URLs to GPT-4o Vision or Claude 3.5 Vision.  
4. Use existing corporate email (Microsoft 365 or Google Workspace) with service credentials for SMTP/IMAP automation.  
5. Connect to Google Sheets through a service account to read suppliers and write replies/prices.

### Suggested Implementation Steps

1. Build the file-intake module (webhook + Telegram bot) with manual tagging UI.  
2. Implement Unstructured.io -> GPT-4o pipeline for extracting tables/text.  
3. Develop comparison logic and Excel reporting for specification vs drawings.  
4. Automate supplier outreach (API + email) and response parsing.  
5. Generate final Excel/JSON packages and dispatch notifications (email + Telegram).

---

## Local setup (no containers)

1. Python 3.11+ recommended.  
2. Create virtual environment and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in keys (NeuroAPI, Unstructured, Google service account JSON path, Drive folder ID, Sheets ID, Telegram bot token).  
4. Run API:
   ```
   uvicorn app.main:app --reload
   ```
   - Health check: `GET /health/`
   - Upload intake files: `POST /intake/files` (multipart, fields: `project_id`, `is_specification`, `is_drawing`, `notes`, `files[]`).  
   - Upload final estimate: `POST /estimate/final` (multipart, fields: `project_id`, `notes`, `file`).  
5. Run Telegram bot (optional):
   ```
   python -m app.services.telegram_bot
   ```
   - Sends documents to the bot; use caption `/spec` or `/drawing` to tag manually.

Notes:
- Google Drive/Sheets functions are stubbed; files are persisted to `data/` locally until Drive credentials are wired.  
- Если не заданы ключи NeuroAPI/Unstructured, срабатывают локальные обработчики: PDF/Excel парсятся через `pypdf` + `openpyxl`, формируется упрощённый список позиций, валидация сметы и отчёт по расхождениям.  
- Replace polling/email/IMAP with real integrations once credentials are available.

SMTP/IMAP (для уведомлений, опроса почты):  
- Добавьте в `.env`: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`.  
- При отсутствии SMTP письма логируются в `data/_email.log`; IMAP-поллер фиксирует состояние в `data/_imap.log`.

### Supplier workflow

- Обновите файл `data/_sheets/<GOOGLE_SHEETS_ID>.json`, чтобы задать поставщиков (формат: `[["Название","да/нет","api_url","email","контакт"], ...]`).  
- API:  
  - `POST /suppliers/request` — запускает рассылку запросов поставщикам на основе ведомости закупки. Тело: `{"project_id":"123","max_api_suppliers":3}`.  
  - `GET /suppliers/summary/{project_id}` — возвращает сводку цен и ссылку на Excel/JSON отчёт.  
- Результаты сохраняются в `data/<project_id>/workspace/supplier_responses.json` и отчёт `reports/suppliers_<project_id>.*`.

### Final report & notifications

- `POST /reports/final` — собирает итоговый отчёт с тремя листами (расхождения, закупка, поставщики) и сохраняет `final_<project_id>.xlsx/json`.  
- `POST /reports/notify` — отправляет email при наличии SMTP-конфигурации или пишет в лог `data/_notifications.log`; Telegram-список пока логируется.  
- Конфигурация получателей задаётся в теле запроса: `{"project_id":"123","emails":["user@corp"],"telegram_ids":["123456"]}`.  
- SMTP/IMAP параметры задаются через `.env`; при отсутствии кредов уведомления пишутся в лог.

### Email / IMAP тесты

- `POST /mail/send` — отправка тестового письма (или запись в `data/_email.log`, если SMTP не настроен). Тело: `{"subject":"...", "body":"...", "to":["user@corp"], "attachments":["path/to/file"]}`.  
- `GET /mail/poll?limit=10` — опрос IMAP (если заданы IMAP_* в `.env`), иначе пишет состояние в `data/_imap.log`.

### Project state

- `GET /projects/` — список локальных проектов в `data/`.  
- `GET /projects/{project_id}/summary` — быстрый статус проекта: что уже загружено (спеки/чертежи/смета), сколько ответов от поставщиков, список сформированных отчётов и метаданные.

### Telegram-бот

- Запуск: `python -m app.services.telegram_bot` (при активированном виртуальном окружении).  
- Команды/кнопки:
  - «Спецификация» — включает/выключает пометку следующего файла как спецификации.  
  - «Чертежи» — пометка файла как чертежей.  
  - «Сбросить теги» — снимает выбранные режимы.  
- После загрузки бот сохраняет файл в `data/<project_id>/` и запускает пайплайн извлечения.

### Отчёты

- После нормализации сметы формируется Excel и JSON `data/<project_id>/reports/procurement_<project_id>.*` с колонками `Материал | Характеристики | Кол-во | Ед. изм. | Примечание`.  
- Эти артефакты используются на этапах закупки (6–8) и могут быть отправлены снабженцу или поставщикам.
- После загрузки спецификаций и чертежей автоматически создаётся отчёт `discrepancies_<project_id>.*` c колонками `Позиция | В спецификации | По чертежам | Отклонение | Ед. изм.` — это основа листа 1 в итоговом Excel (этап 8).
