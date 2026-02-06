# cn_import_clone

This project is a clone of `@cn_import_bot`, originally built with crawler artifacts.
It is now the main project in this repository.

## Features
- Recreates the observable flow of the target bot.
- Uses `DeepSeek` (NeuroAPI) for semantic understanding if enabled.
- Loads graph/screens from `output_cn_import` (or where configured).

## Quick start

1) The `.env` file should be configured with `BOT_TOKEN` and `OPENROUTER` keys.
2) Install dependencies:

```bash
pip install -e .[dev]
```

3) Run the bot:

```bash
python -m app.main
```

## Admin commands

- `/admin` shows available admin commands.
- `/rates` shows the current rate configuration.
- `/set_rate <key> <value>` updates a default rate.
- `/set_rate <category.key> <value>` updates a category override.
- `/export <user_id>` exports session logs as JSON.

## Tests

```bash
# Run tests
pytest
```
