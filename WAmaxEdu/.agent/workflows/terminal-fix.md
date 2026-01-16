---
description: Исправление зависаний терминала PowerShell в Antigravity IDE
---

# Исправление терминала Antigravity

Этот workflow автоматически применяется при работе в Antigravity IDE.

## Что исправлено

1. **PSReadLine отключен** — главная причина зависаний при захвате вывода
2. **UTF-8 принудительно** — корректное отображение кириллицы
3. **Прогресс-бары выключены** — npm/pip не спамят полосками
4. **Git без пейджера** — `git log`/`diff` не блокируют терминал
5. **ANSI-цвета отключены** — чистый вывод без escape-кодов

## Как применить глобально

// turbo
1. Добавьте в ваш PowerShell профиль (`$PROFILE`):

```powershell
if ($env:ANTIGRAVITY_IDE -eq 'true' -or $env:TERM_PROGRAM -eq 'vscode') {
    $scriptPath = "d:\VsCode\WAmaxEdu\.agent\scripts\antigravity-shell.ps1"
    if (Test-Path $scriptPath) {
        . $scriptPath
    }
}
```

## Ручной запуск

// turbo
2. Для ручной активации в текущей сессии:

```powershell
. "d:\VsCode\WAmaxEdu\.agent\scripts\antigravity-shell.ps1"
```

## Проверка работы

После применения вы увидите:
```
Antigravity Safe Shell v2.0 Active
 - UTF-8 Enforced
 - Interactive tools (git, npm) patched
 - Progress bars disabled
```
