#!/usr/bin/env python3
"""Simple GUI tool for generating Reels with GPT titles/descriptions.

This script provides two modes:
1. Read titles from a .txt file and generate only descriptions.
2. Generate both titles and descriptions from topics provided in the UI.

It overlays text onto videos using ffmpeg and allows basic preview of the
mask area on the first frame of the selected video. Music can be selected
randomly from a folder (a placeholder is left for a smarter algorithm).
"""

import os
import random
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, simpledialog

import tempfile
import json

from PIL import Image, ImageTk, ImageFont, ImageDraw, ImageColor
from openai import OpenAI
from itertools import islice, cycle
import csv
import textwrap

# Ensure ffmpeg is installed in the environment.
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

ARROW_PNG = os.path.join(os.path.dirname(__file__), "assets", "down_arrow.png")
DOTS_PNG = os.path.join(os.path.dirname(__file__), 'dots', 'dots.png')

# Possible captions displayed above the description with a pointing emoji
CAPTION_CHOICES = [
    "РЎРјРѕС‚СЂРё РѕРїРёСЃР°РЅРёРµ",
    "Р§РёС‚Р°Р№ РЅРёР¶Рµ",
    "РџСЂРѕРґРѕР»Р¶РµРЅРёРµ РЅРёР¶Рµ",
]

TEMPLATE_FILE = "mask_templates.json"

# Override captions with correct UTF-8 strings to avoid mojibake in overlays
CAPTION_CHOICES = [
    "Смотри описание",
    "Смотри ниже",
]


def load_templates() -> dict:
    try:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_templates(data: dict) -> None:
    with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# OpenAI client
# РЈРєР°Р¶РёС‚Рµ РІР°С€ РєР»СЋС‡ API РїСЂСЏРјРѕ РІ РєРѕРґРµ.
API_KEY = "sk-aitunnel-9ujMXk54yNKuaHl6QPTr5vFS731gNL0e"

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.aitunnel.ru/v1/",
)

GPT_MODEL = "gpt-4.1"

# ---- GPT PROMPTS -----------------------------------------------------------
# These templates are formatted at runtime with the actual titles/topics so
# they must remain regular strings (not f-strings) to avoid NameError on import.
DESCRIPTION_PROMPT = (
    "РЎРјРѕС‚СЂРё РјС‹ РґРµР»Р°РµРј СЂРѕР»РёРєРё СЂРёР»СЃ РЅР° С‚СЂРёРіРіРµСЂРЅС‹Рµ С‚РµРјС‹, РЅР°С€Р° Р·Р°РґР°С‡Р° РЅР°Р±РёСЂР°С‚СЊ СЃ РІРёСЂР°Р»СЊРЅС‹С… СЂРѕР»РёРєРѕРІ РјРёР»Р»РёРѕРЅС‹ РїСЂРѕСЃРјРѕС‚СЂРѕРІ."
    "РЎРґРµР»Р°Р№ РѕРїРёСЃР°РЅРёСЏ РґР»СЏ РєР°Р¶РґРѕРіРѕ Р·Р°РіРѕР»РѕРІРєР° Reels"
    "РЎРїРёСЃРѕРє Р·Р°РіРѕР»РѕРІРєРѕРІ:\n{titles}"
    "РџРѕСЃС‚С‹ СЃРґРµР»Р°Р№ РєР°Рє Р±СѓРґС‚Рѕ РёС… РїРёС€РµС‚ СЃР°РјС‹Р№ РєСЂСѓС‚РѕР№ РїСЂРѕС„РµСЃСЃРёРѕРЅР°Р» РІ СЌС‚РѕРј РґРµР»Рµ, РЅРѕ РЅР°С‚РёРІРЅРѕ, РёРЅС‚РµСЂРµСЃРЅРѕ, РѕС‚РІРµС‚С‹ СЂР°Р·РІРѕСЂР°С‡РёРІР°Р№! РЎРјРѕС‚СЂРё РєР°Рє РїРёС€РµРј, РІРѕС‚ СЃС‚СЂСѓРєС‚СѓСЂР°:"
    "Р“РґРµ РІ Р·Р°РіРѕР»РѕРІРєР°С… РµСЃС‚СЊ РєР°РїСЃ - РѕСЃС‚Р°РІР»СЏР№ Р±РµР· РёР·РјРµРЅРµРЅРёР№"
    "РџСѓРЅРєС‚С‹ РѕРїРёСЃР°РЅРёСЏ = Р¶РёРІС‹Рµ С†РёС‚Р°С‚С‹ + РѕР±СЉСЏСЃРЅРµРЅРёРµ Р±РѕР»Рё, РїСЂРёС‡РёРЅ, РєРѕРЅС‚РµРєСЃС‚Р°, РѕР±СЂР°Р·РѕРІ. РџРѕСЃР»Рµ РєР°Р¶РґРѕРіРѕ РїСѓРЅРєС‚Р°, РґРµР»Р°Р№ РѕС‚СЃС‚СѓРї РЅР° Р°Р±Р·Р°С†, С‡С‚РѕР±С‹ РїРѕС‚РѕРј Р±С‹Р»Рѕ Р»РµРіРєРѕ РєРѕРїРёСЂРѕРІР°С‚СЊ РІ Р·Р°РјРµС‚РєРё."
    "Р¤РёРЅР°Р» РїРѕСЃС‚Р° = РІРѕРІР»РµРєР°СЋС‰РёР№ РІРѕРїСЂРѕСЃ + С‚СЂРёРіРіРµСЂ РЅР° РєРѕРјРјРµРЅС‚ (вЂњРЅР°РїРёС€Рё X вЂ” РїСЂРёС€Р»СЋ YвЂќ) РїРѕ С‚РµРјРµ РѕС‚РЅРѕС€РµРЅРёР№ РјС‹ РїСЂРѕСЃРёРј РЅР°РїРёСЃР°С‚СЊ СЃР»РµРґСѓСЋС‰РёРµ СЃР»РѕРІР° РІ РєРѕРЅС†Рµ (РѕС‚РЅРѕС€РµРЅРёСЏ, Р»СЋР±РѕРІСЊ, РіР°Р№Рґ, С‚РµРїР»Рѕ) РїРёСЃР°С‚СЊ РїСЂРѕСЃС‚РёРј С‡РµР»РѕРІРµРєР° РѕРґРЅРѕ РєР°РєРѕРµ-С‚Рѕ СЃР»РѕРІРѕ Р° РЅРµ РЅР° РІС‹Р±РѕСЂ!"
    "РЎРЅРёР·Сѓ РІСЃРµРіРґР° РїСЂРёРїРёСЃС‹РІР°Р№ РїРѕСЃР»Рµ РїРѕСЃР»РµРґРЅРµРіРѕ РІРѕРїСЂРѕСЃР°, С‡РµСЂРµР· Р°Р±Р·Р°С† РїРѕРґРѕР±РЅСѓСЋ С„РѕСЂРјСѓР»РёСЂРѕРІРєСѓ РґРµР»Р°Р№ РЅРѕ РјРµРЅСЏР№ СЃР»РѕРІР° РѕС‚ РєР°Р¶РґРѕРіРѕ РїРѕСЃС‚Р° Рє РєР°Р¶Р»РѕРјСѓ РїРѕСЃС‚Сѓ. РџСЂРёР·С‹РІР°РµРј РїРѕСЃС‚Р°РІРёС‚СЊ Р»Р°Р№Рє РџРёС€РµРј РЅР° РїРѕРґРѕР±РёРё С‚Р°РєРёС… С„СЂР°Р·:"
    "Р‘С‹Р»Рѕ РїРѕР»РµР·РЅРѕ, Р¶РјРё Р»Р°Р№Рє рџ‘ЌрџЏј Рё РїРѕРґРїРёСЃС‹РІР°Р№СЃСЏвЂ” РїРѕРєР°Р¶Сѓ РєР°Рє Р»РµРіРєРѕ РєР°С‡Р°С‚СЊ Р±Р»РѕРі РЅР° РґРµСЃСЏС‚РєРё С‚С‹СЃСЏС‡ РїРѕРґРїРёСЃС‡РёРєРѕРІ Р±РµР· Р»РёС€РЅРµР№ С€РµР»СѓС…Рё. Р“Р»Р°РІРЅРѕРµ РІ СЌС‚РѕР№ С„СЂР°Р·Рµ, РїРёСЃР°С‚СЊ РёРјРµРЅРЅРѕ С‚Р°РєРѕР№ Р»РѕРіРёРЅ Р±Р»РѕРіР°, РІСЃРµРіРґР° РїСЂРѕСЃРёС‚СЊ Рѕ Р»Р°Р№РєРµ, Рё РїРѕРґРїРёСЃРєРµ Р° С‚Р°Рє Р¶Рµ СЂР°Р·РЅС‹РјРё СЃР»РѕРІР°РјРё РіРѕРІРѕСЂРёС‚СЊ Рѕ С‚РѕРј С‡С‚Рѕ СЏ С‚СѓС‚ РІ Р°РєРєР°СѓРЅС‚Рµ РїРѕРєР°Р·С‹РІР°СЋ РєР°Рє Р»РµРіРєРѕ СЂР°СЃРєР°С‡Р°С‚СЊ СЃРІРѕР№ Р±Р»РѕРі РїСЂРёРєР»Р°РґС‹РІР°СЏ РјРёРЅРёРјСѓРј СѓСЃРёР»РёР№."
    "РџСЂРёРјРµСЂ С‚Р°РєРѕРіРѕ РїРѕСЃС‚Р°:"
    "Р—Р°РіРѕР»РѕРІРѕРє РґР»СЏ Reels:"
    "5 РџР РР§РРќ, РїРѕС‡РµРјСѓ РЅРёРєРѕРіРґР° РќР•Р›Р¬Р—РЇ"
    "Р‘Р РћРЎРђРўР¬ С‡РµР»РѕРІРµРєР° С‚РѕР»СЊРєРѕ РёР·-Р·Р°"
    "С‚РѕРіРѕ, С‡С‚Рѕ В«РїСЂРѕРїР°Р»Рё С‡СѓРІСЃС‚РІР°В» "
    "(Р±С‹Р» РІ Р°С…*СѓРµ РѕС‚ РѕС‚РІРµС‚Р°)"
    "(РїРѕРґРїРёСЃСЊ Рє СЂРёР»СЃСѓ)"
    "1. В«РћС‰СѓС‰РµРЅРёРµ, С‡С‚Рѕ С‡СѓРІСЃС‚РІР° СѓС€Р»Рё, С‡Р°СЃС‚Рѕ СЃРІСЏР·Р°РЅРѕ РЅРµ СЃ РїР°СЂС‚РЅС‘СЂРѕРјВ»"
    "Р§Р°С‰Рµ РІСЃРµРіРѕ СЌС‚Рѕ СЂРµР·СѓР»СЊС‚Р°С‚ РїРµСЂРµРіСЂСѓР·РєРё С‚РІРѕРµР№ РЅРµСЂРІРЅРѕР№ СЃРёСЃС‚РµРјС‹, Р° РЅРµ РїРѕС‚РµСЂРё Р»СЋР±РІРё. РџРѕСЃС‚РѕСЏРЅРЅР°СЏ СЃСѓРµС‚Р°, РЅРѕРІРѕСЃС‚Рё, СЃРѕС†СЃРµС‚Рё, СЂР°Р±РѕС‡РёРµ С‡Р°С‚С‹ Рё РґРµСЃСЏС‚РєРё СЂРµС€РµРЅРёР№ РІ РґРµРЅСЊ РёСЃС‚РѕС‰Р°СЋС‚ РјРѕР·Рі С‚Р°Рє, С‡С‚Рѕ РЅР° СѓРґРѕРІРѕР»СЊСЃС‚РІРёРµ РїСЂРѕСЃС‚Рѕ РЅРµ РѕСЃС‚Р°С‘С‚СЃСЏ СЂРµСЃСѓСЂСЃР°. РўС‹ РЅРµ РїРµСЂРµРіРѕСЂРµР» Рє С‡РµР»РѕРІРµРєСѓ вЂ” С‚С‹ РІС‹РіРѕСЂРµР» РІРЅСѓС‚СЂРё СЃРµР±СЏ. РЎРЅР°С‡Р°Р»Р° РїРµСЂРµР·Р°РіСЂСѓР·Рё СЃРµР±СЏ, Р° РїРѕС‚РѕРј РїСЂРёРЅРёРјР°Р№ СЂРµС€РµРЅРёСЏ РѕР± РѕС‚РЅРѕС€РµРЅРёСЏС…."
    "2. В«РЈРіР°СЃР°РЅРёРµ СЃС‚СЂР°СЃС‚Рё вЂ” СЌС‚Рѕ РЅРµ РІСЃРµРіРґР° РєРѕРЅРµС†В»"
    "РџСЃРёС…РѕР»РѕРіРёСЏ РіРѕРІРѕСЂРёС‚: РїРµСЂРІР°СЏ РІРѕР»РЅР° РІР»СЋР±Р»С‘РЅРЅРѕСЃС‚Рё вЂ” СЌС‚Рѕ С…РёРјРёСЏ, РєРѕС‚РѕСЂР°СЏ РІСЃРµРіРґР° СЃС…РѕРґРёС‚. РќР° РµС‘ РјРµСЃС‚Рѕ РїСЂРёС…РѕРґРёС‚ РіР»СѓР±РѕРєР°СЏ Р±Р»РёР·РѕСЃС‚СЊ Рё СЃРїРѕРєРѕР№СЃС‚РІРёРµ, РЅРѕ РµСЃР»Рё С‚С‹ РїСЂРёРІС‹Рє Рє СЌРјРѕС†РёРѕРЅР°Р»СЊРЅС‹Рј РєР°С‡РµР»СЏРј, СЌС‚Рѕ РѕС‰СѓС‰Р°РµС‚СЃСЏ РєР°Рє В«РїСѓСЃС‚РѕС‚Р°В». РќР° СЃР°РјРѕРј РґРµР»Рµ СЌС‚Рѕ РїРµСЂРµС…РѕРґ РІ Р±РѕР»РµРµ Р·СЂРµР»С‹Р№ СѓСЂРѕРІРµРЅСЊ Р»СЋР±РІРё."
    "3. В«Р­РјРѕС†РёРё РјРѕР¶РЅРѕ РІРµСЂРЅСѓС‚СЊ, РµСЃР»Рё СЂР°Р±РѕС‚Р°С‚СЊ РЅР°Рґ РЅРёРјРёВ»"
    "Р§СѓРІСЃС‚РІР° вЂ” СЌС‚Рѕ РЅРµ С„РёРєСЃРёСЂРѕРІР°РЅРЅР°СЏ РґР°РЅРЅРѕСЃС‚СЊ, Р° РїСЂРѕС†РµСЃСЃ, РєРѕС‚РѕСЂС‹Р№ РјРѕР¶РЅРѕ РїРѕРґРїРёС‚С‹РІР°С‚СЊ. РќРѕРІС‹Рµ РІРїРµС‡Р°С‚Р»РµРЅРёСЏ, СЃРѕРІРјРµСЃС‚РЅС‹Рµ РїСЂРѕРµРєС‚С‹, РїСѓС‚РµС€РµСЃС‚РІРёСЏ, РґР°Р¶Рµ РЅРµРѕР¶РёРґР°РЅРЅС‹Рµ РјР°Р»РµРЅСЊРєРёРµ СЃСЋСЂРїСЂРёР·С‹ СЃРїРѕСЃРѕР±РЅС‹ РѕР¶РёРІРёС‚СЊ РѕС‚РЅРѕС€РµРЅРёСЏ. РњРЅРѕРіРёРµ РїР°СЂС‹, РєРѕС‚РѕСЂС‹Рµ РїРµСЂРµР¶РёР»Рё В«СѓРіР°СЃР°РЅРёРµВ», РїРѕС‚РѕРј РіРѕРІРѕСЂСЏС‚, С‡С‚Рѕ СЃС‚Р°Р»Рё Р±Р»РёР¶Рµ, С‡РµРј РєРѕРіРґР°-Р»РёР±Рѕ."
    "4. В«РџРѕС‚РµСЂСЏ СЌРјРѕС†РёР№ С‡Р°СЃС‚Рѕ РіРѕРІРѕСЂРёС‚ Рѕ РІРЅСѓС‚СЂРµРЅРЅРёС… Р±Р»РѕРєР°С…В»"
    "РРЅРѕРіРґР° С…РѕР»РѕРґ РІ РѕС‚РЅРѕС€РµРЅРёСЏС… вЂ” СЌС‚Рѕ РѕС‚СЂР°Р¶РµРЅРёРµ С‚РІРѕРёС… Р»РёС‡РЅС‹С… СЃС‚СЂР°С…РѕРІ, РѕР±РёРґ РёР»Рё РЅРµРІС‹СЂР°Р¶РµРЅРЅС‹С… С‡СѓРІСЃС‚РІ. РџРѕРєР° РёС… РЅРµ РїСЂРѕСЂР°Р±РѕС‚Р°РµС€СЊ, РґР°Р¶Рµ СЃ РЅРѕРІС‹Рј С‡РµР»РѕРІРµРєРѕРј РёСЃС‚РѕСЂРёСЏ РїРѕРІС‚РѕСЂРёС‚СЃСЏ."
    "5. В«РЈС…РѕРґ РІ РјРѕРјРµРЅС‚ СѓСЃС‚Р°Р»РѕСЃС‚Рё РјРѕР¶РµС‚ СЃС‚РѕРёС‚СЊ РѕС‡РµРЅСЊ РґРѕСЂРѕРіРѕВ»"
    "Р’Р·СЂРѕСЃР»С‹Рµ РѕС‚РЅРѕС€РµРЅРёСЏ СЃС‚СЂРѕСЏС‚СЃСЏ РЅРµ РЅР° РїРѕСЃС‚РѕСЏРЅРЅРѕР№ СЃС‚СЂР°СЃС‚Рё, Р° РЅР° СѓРјРµРЅРёРё Р±С‹С‚СЊ РІРјРµСЃС‚Рµ РІ СЂР°Р·РЅС‹Рµ РїРµСЂРёРѕРґС‹. Р•СЃР»Рё СѓР№С‚Рё РІ РјРѕРјРµРЅС‚, РєРѕРіРґР° С‡СѓРІСЃС‚РІР° РѕСЃР»Р°Р±Р»Рё РёР·-Р·Р° РѕР±СЃС‚РѕСЏС‚РµР»СЊСЃС‚РІ, РјРѕР¶РЅРѕ РїРѕС‚РµСЂСЏС‚СЊ С‡РµР»РѕРІРµРєР°, СЃ РєРѕС‚РѕСЂС‹Рј РјРѕРіР»Рѕ Р±С‹С‚СЊ РЅР°СЃС‚РѕСЏС‰РµРµ, РіР»СѓР±РѕРєРѕРµ В«РјС‹В»."
    "рџ’¬ РќР°РїРёС€Рё В«С‡СѓРІСЃС‚РІР°В» РІ РєРѕРјРјРµРЅС‚Р°СЂРёРё вЂ” Рё СЏ РїСЂРёС€Р»СЋ С‡РµРє-Р»РёСЃС‚, РєР°Рє РїРµСЂРµР·Р°РїСѓСЃС‚РёС‚СЊ РѕС‚РЅРѕС€РµРЅРёСЏ РµСЃР»Рё РµС‰С‘ РµСЃС‚СЊ С€Р°РЅСЃ."
    "Р‘С‹Р»Рѕ РёРЅС‚РµСЂРµСЃРЅРѕ, РїРѕСЃС‚Р°РІСЊ Р»Р°Р№Рє рџ¤— Рё РїРѕРґРїРёС€РёСЃСЊвЂ” С‚СѓС‚ С‚РѕР»СЊРєРѕ РїРѕР»СЊР·Р° Рё РЅРёС‡РµРіРѕ РєСЂРѕРјРµ"
    "РћРїРёСЃР°РЅРёСЏ Рє Reels СЃС‚СЂРѕРіРѕ РѕС‚ 1750 РґРѕ 1850 СЃРёРјРІРѕР»РѕРІ РІ С‚РµРєСЃС‚Рµ РЅРµ Р±РѕР»СЊС€Рµ РЅРµ РјРµРЅСЊС€Рµ "
    "Р—Р°С‚РµРј СЂР°Р·СЉСЏСЃРЅРµРЅРёРµ (РїСЂРёРјРµСЂ, РѕР±СЉСЏСЃРЅРµРЅРёРµ РїСЂРёС‡РёРЅС‹, СЃ СЌРјРѕС†РёРµР№, РѕР±СЂР°Р·Р°РјРё, РЅР°СѓС‡РЅРѕР№ РёР»Рё СЃРѕС†РёР°Р»СЊРЅРѕР№ Р»РѕРіРёРєРѕР№)"
    "РџРѕСЃР»Рµ РєР°Р¶РґРѕРіРѕ РїСѓРЅРєС‚Р° РѕС‚СЃС‚СѓРї РЅР° Р°Р±Р·Р°С†, С‡С‚РѕР±С‹ Р»РµРіРєРѕ С‡РёС‚Р°Р»РѕСЃСЊ. РџРѕСЃР»Рµ РІСЃРµС… РїСѓРЅРєС‚РѕРІ РїРµСЂРµРґ РїРѕСЃР»РµРґРЅРµР№ С„СЂР°Р·РѕР№ С‚Р°Рє Р¶Рµ РѕС‚СЃС‚СѓРї РґРµР»Р°Р№, РєР°Рє РЅР° РїСЂРёРјРµСЂРµ РІС‹С€Рµ."
    "Р’СЃС‘ РЅР°РїРёСЃР°РЅРѕ РѕС‚ Р»РёС†Р° РіРѕРІРѕСЂСЏС‰РµРіРѕ, РёСЃРєСЂРµРЅРЅРµ, Р±РµР· РІРѕРґС‹, РІ СЃС‚РёР»Рµ В«Р¶РёР·РЅРµРЅРЅРѕВ»,  РёРЅС‚РµСЂРµСЃРЅРѕ РїРѕРґР°РЅРѕ."
    "Р’ РєРѕРЅС†Рµ вЂ” РІРѕРїСЂРѕСЃ Рє Р°СѓРґРёС‚РѕСЂРёРё РёР»Рё РїСЂРёР·С‹РІ Рє РґРµР№СЃС‚РІРёСЋ, РІС‹Р·С‹РІР°СЋС‰РёР№ РєРѕРјРјРµРЅС‚Р°СЂРёРё (РЅР°РїСЂРёРјРµСЂ, вЂњРЅР°РїРёС€Рё Р·РґРѕСЂРѕРІСЊРµ вЂ” РІС‹С€Р»СЋ С‡РµРє-Р»РёСЃС‚вЂќ)"
    "РќРµ РІСЃС‚Р°РІР»СЏР№ РІ РѕРїРёСЃР°РЅРёРµ РёРјСЏ Р°РєРєР°СѓРЅС‚Р° РєРѕРіРґР° РїСЂРѕСЃРёС€СЊ РїРѕРґРїРёСЃР°С‚СЊСЃСЏ. РќРµ РёСЃРїРѕР»СЊР·СѓР№ Р·РЅР°Рє РїСЂРѕС†РµРЅС‚Р° (%) РІ Р·Р°РіРѕР»РѕРІРєР°С…"
    "Р¤РѕСЂРјР°С‚ РѕС‚РІРµС‚Р°"
    "Р—Р°РіРѕР»РѕРІРѕРє"
    "РІС‚РѕСЂР°СЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°"
    "С‚СЂРµС‚СЊСЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°"
    "С‡РµС‚РІРµСЂС‚Р°СЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°|||"
    "РћРїРёСЃР°РЅРёРµ"
    "---"
    "Р—Р°РіРѕР»РѕРІРѕРє 2"
    "Р’С‚РѕСЂР°СЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°"
    "С‚СЂРµС‚СЊСЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°"
    "С‡РµС‚РІРµСЂС‚Р°СЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°|||"
    "РћРїРёСЃР°РЅРёРµ 2"
    "Р—РЅР°Рє ||| Рё --- РјРЅРµ РЅСѓР¶РЅС‹ РґР»СЏ РїРѕСЃР»РµРґСѓСЋС‰РµР№ РѕР±СЂР°Р±РѕС‚РєРё. Р”Р»РёРЅРЅР°СЏ РѕРґРЅРѕР№ СЃС‚СЂРѕРєРё Р·Р°РіРѕР»РѕРІРєР° РЅРµ РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 30 СЃРёРјРІРѕР»РѕРІ, РЅРµ РЅР°С‡РёРЅР°Р№ РєР°Р¶РґСѓСЋ СЃС‚СЂРѕРєСѓ РїРѕСЃР»Рµ РїРµСЂРІРѕР№ СЃ Р±РѕР»СЊС€РѕР№ Р±СѓРєРІС‹? РќРµ РёСЃРїРѕР»СЊР·СѓР№ РєРѕРЅСЃС‚СЂСѓРєС†РёРё РІ РѕС‚РІРµС‚Рµ СЃР»РѕРІР° Р—Р°РіРѕР»РѕРІРѕРє 1, Р—Р°РіРѕР»РѕРІРѕРє 2, РћРїРёСЃР°РЅРёРµ 1, РћРїРёСЃР°РЅРёРµ 2. Р­С‚Рѕ РІСЃС‘ РЅРµ РЅСѓР¶РЅРѕ"
)

TITLE_DESCRIPTION_PROMPT = (
    "РЎРјРѕС‚СЂРё РјС‹ РґРµР»Р°РµРј СЂРѕР»РёРєРё СЂРёР»СЃ РЅР° С‚СЂРёРіРіРµСЂРЅС‹Рµ С‚РµРјС‹, РЅР°С€Р° Р·Р°РґР°С‡Р° РЅР°Р±РёСЂР°С‚СЊ СЃ РІРёСЂР°Р»СЊРЅС‹С… СЂРѕР»РёРєРѕРІ РјРёР»Р»РёРѕРЅС‹ РїСЂРѕСЃРјРѕС‚СЂРѕРІ."
    "РЎРґРµР»Р°Р№ РѕРїРёСЃР°РЅРёСЏ РґР»СЏ РєР°Р¶РґРѕРіРѕ Р·Р°РіРѕР»РѕРІРєР° Reels"
    "РЎРїРёСЃРѕРє Р·Р°РіРѕР»РѕРІРєРѕРІ:\n{topics}"
    "РџРѕСЃС‚С‹ СЃРґРµР»Р°Р№ РєР°Рє Р±СѓРґС‚Рѕ РёС… РїРёС€РµС‚ СЃР°РјС‹Р№ РєСЂСѓС‚РѕР№ РїСЂРѕС„РµСЃСЃРёРѕРЅР°Р» РІ СЌС‚РѕРј РґРµР»Рµ, РЅРѕ РЅР°С‚РёРІРЅРѕ, РёРЅС‚РµСЂРµСЃРЅРѕ, РѕС‚РІРµС‚С‹ СЂР°Р·РІРѕСЂР°С‡РёРІР°Р№! РЎРјРѕС‚СЂРё РєР°Рє РїРёС€РµРј, РІРѕС‚ СЃС‚СЂСѓРєС‚СѓСЂР°:"
    "Р“РґРµ РІ Р·Р°РіРѕР»РѕРІРєР°С… РµСЃС‚СЊ РєР°РїСЃ - РѕСЃС‚Р°РІР»СЏР№ Р±РµР· РёР·РјРµРЅРµРЅРёР№"
    "РџСѓРЅРєС‚С‹ РѕРїРёСЃР°РЅРёСЏ = Р¶РёРІС‹Рµ С†РёС‚Р°С‚С‹ + РѕР±СЉСЏСЃРЅРµРЅРёРµ Р±РѕР»Рё, РїСЂРёС‡РёРЅ, РєРѕРЅС‚РµРєСЃС‚Р°, РѕР±СЂР°Р·РѕРІ. РџРѕСЃР»Рµ РєР°Р¶РґРѕРіРѕ РїСѓРЅРєС‚Р°, РґРµР»Р°Р№ РѕС‚СЃС‚СѓРї РЅР° Р°Р±Р·Р°С†, С‡С‚РѕР±С‹ РїРѕС‚РѕРј Р±С‹Р»Рѕ Р»РµРіРєРѕ РєРѕРїРёСЂРѕРІР°С‚СЊ РІ Р·Р°РјРµС‚РєРё."
    "Р¤РёРЅР°Р» РїРѕСЃС‚Р° = РІРѕРІР»РµРєР°СЋС‰РёР№ РІРѕРїСЂРѕСЃ + С‚СЂРёРіРіРµСЂ РЅР° РєРѕРјРјРµРЅС‚ (вЂњРЅР°РїРёС€Рё X вЂ” РїСЂРёС€Р»СЋ YвЂќ) РїРѕ С‚РµРјРµ РѕС‚РЅРѕС€РµРЅРёР№ РјС‹ РїСЂРѕСЃРёРј РЅР°РїРёСЃР°С‚СЊ СЃР»РµРґСѓСЋС‰РёРµ СЃР»РѕРІР° РІ РєРѕРЅС†Рµ (РѕС‚РЅРѕС€РµРЅРёСЏ, Р»СЋР±РѕРІСЊ, РіР°Р№Рґ, С‚РµРїР»Рѕ) РїРёСЃР°С‚СЊ РїСЂРѕСЃС‚РёРј С‡РµР»РѕРІРµРєР° РѕРґРЅРѕ РєР°РєРѕРµ-С‚Рѕ СЃР»РѕРІРѕ Р° РЅРµ РЅР° РІС‹Р±РѕСЂ!"
    "РЎРЅРёР·Сѓ РІСЃРµРіРґР° РїСЂРёРїРёСЃС‹РІР°Р№ РїРѕСЃР»Рµ РїРѕСЃР»РµРґРЅРµРіРѕ РІРѕРїСЂРѕСЃР°, С‡РµСЂРµР· Р°Р±Р·Р°С† РїРѕРґРѕР±РЅСѓСЋ С„РѕСЂРјСѓР»РёСЂРѕРІРєСѓ РґРµР»Р°Р№ РЅРѕ РјРµРЅСЏР№ СЃР»РѕРІР° РѕС‚ РєР°Р¶РґРѕРіРѕ РїРѕСЃС‚Р° Рє РєР°Р¶Р»РѕРјСѓ РїРѕСЃС‚Сѓ. РџСЂРёР·С‹РІР°РµРј РїРѕСЃС‚Р°РІРёС‚СЊ Р»Р°Р№Рє РџРёС€РµРј РЅР° РїРѕРґРѕР±РёРё С‚Р°РєРёС… С„СЂР°Р·:"
    "Р‘С‹Р»Рѕ РїРѕР»РµР·РЅРѕ, Р¶РјРё Р»Р°Р№Рє рџ‘ЌрџЏј Рё РїРѕРґРїРёСЃС‹РІР°Р№СЃСЏвЂ” РїРѕРєР°Р¶Сѓ РєР°Рє Р»РµРіРєРѕ РєР°С‡Р°С‚СЊ Р±Р»РѕРі РЅР° РґРµСЃСЏС‚РєРё С‚С‹СЃСЏС‡ РїРѕРґРїРёСЃС‡РёРєРѕРІ Р±РµР· Р»РёС€РЅРµР№ С€РµР»СѓС…Рё. Р“Р»Р°РІРЅРѕРµ РІ СЌС‚РѕР№ С„СЂР°Р·Рµ, РїРёСЃР°С‚СЊ РёРјРµРЅРЅРѕ С‚Р°РєРѕР№ Р»РѕРіРёРЅ Р±Р»РѕРіР°, РІСЃРµРіРґР° РїСЂРѕСЃРёС‚СЊ Рѕ Р»Р°Р№РєРµ, Рё РїРѕРґРїРёСЃРєРµ Р° С‚Р°Рє Р¶Рµ СЂР°Р·РЅС‹РјРё СЃР»РѕРІР°РјРё РіРѕРІРѕСЂРёС‚СЊ Рѕ С‚РѕРј С‡С‚Рѕ СЏ С‚СѓС‚ РІ Р°РєРєР°СѓРЅС‚Рµ РїРѕРєР°Р·С‹РІР°СЋ РєР°Рє Р»РµРіРєРѕ СЂР°СЃРєР°С‡Р°С‚СЊ СЃРІРѕР№ Р±Р»РѕРі РїСЂРёРєР»Р°РґС‹РІР°СЏ РјРёРЅРёРјСѓРј СѓСЃРёР»РёР№."
    "РџСЂРёРјРµСЂ С‚Р°РєРѕРіРѕ РїРѕСЃС‚Р°:"
    "Р—Р°РіРѕР»РѕРІРѕРє РґР»СЏ Reels:"
    "5 РџР РР§РРќ, РїРѕС‡РµРјСѓ РЅРёРєРѕРіРґР° РќР•Р›Р¬Р—РЇ"
    "Р‘Р РћРЎРђРўР¬ С‡РµР»РѕРІРµРєР° С‚РѕР»СЊРєРѕ РёР·-Р·Р°"
    "С‚РѕРіРѕ, С‡С‚Рѕ В«РїСЂРѕРїР°Р»Рё С‡СѓРІСЃС‚РІР°В» "
    "(Р±С‹Р» РІ Р°С…*СѓРµ РѕС‚ РѕС‚РІРµС‚Р°)"
    "(РїРѕРґРїРёСЃСЊ Рє СЂРёР»СЃСѓ)"
    "1. В«РћС‰СѓС‰РµРЅРёРµ, С‡С‚Рѕ С‡СѓРІСЃС‚РІР° СѓС€Р»Рё, С‡Р°СЃС‚Рѕ СЃРІСЏР·Р°РЅРѕ РЅРµ СЃ РїР°СЂС‚РЅС‘СЂРѕРјВ»"
    "Р§Р°С‰Рµ РІСЃРµРіРѕ СЌС‚Рѕ СЂРµР·СѓР»СЊС‚Р°С‚ РїРµСЂРµРіСЂСѓР·РєРё С‚РІРѕРµР№ РЅРµСЂРІРЅРѕР№ СЃРёСЃС‚РµРјС‹, Р° РЅРµ РїРѕС‚РµСЂРё Р»СЋР±РІРё. РџРѕСЃС‚РѕСЏРЅРЅР°СЏ СЃСѓРµС‚Р°, РЅРѕРІРѕСЃС‚Рё, СЃРѕС†СЃРµС‚Рё, СЂР°Р±РѕС‡РёРµ С‡Р°С‚С‹ Рё РґРµСЃСЏС‚РєРё СЂРµС€РµРЅРёР№ РІ РґРµРЅСЊ РёСЃС‚РѕС‰Р°СЋС‚ РјРѕР·Рі С‚Р°Рє, С‡С‚Рѕ РЅР° СѓРґРѕРІРѕР»СЊСЃС‚РІРёРµ РїСЂРѕСЃС‚Рѕ РЅРµ РѕСЃС‚Р°С‘С‚СЃСЏ СЂРµСЃСѓСЂСЃР°. РўС‹ РЅРµ РїРµСЂРµРіРѕСЂРµР» Рє С‡РµР»РѕРІРµРєСѓ вЂ” С‚С‹ РІС‹РіРѕСЂРµР» РІРЅСѓС‚СЂРё СЃРµР±СЏ. РЎРЅР°С‡Р°Р»Р° РїРµСЂРµР·Р°РіСЂСѓР·Рё СЃРµР±СЏ, Р° РїРѕС‚РѕРј РїСЂРёРЅРёРјР°Р№ СЂРµС€РµРЅРёСЏ РѕР± РѕС‚РЅРѕС€РµРЅРёСЏС…."
    "2. В«РЈРіР°СЃР°РЅРёРµ СЃС‚СЂР°СЃС‚Рё вЂ” СЌС‚Рѕ РЅРµ РІСЃРµРіРґР° РєРѕРЅРµС†В»"
    "РџСЃРёС…РѕР»РѕРіРёСЏ РіРѕРІРѕСЂРёС‚: РїРµСЂРІР°СЏ РІРѕР»РЅР° РІР»СЋР±Р»С‘РЅРЅРѕСЃС‚Рё вЂ” СЌС‚Рѕ С…РёРјРёСЏ, РєРѕС‚РѕСЂР°СЏ РІСЃРµРіРґР° СЃС…РѕРґРёС‚. РќР° РµС‘ РјРµСЃС‚Рѕ РїСЂРёС…РѕРґРёС‚ РіР»СѓР±РѕРєР°СЏ Р±Р»РёР·РѕСЃС‚СЊ Рё СЃРїРѕРєРѕР№СЃС‚РІРёРµ, РЅРѕ РµСЃР»Рё С‚С‹ РїСЂРёРІС‹Рє Рє СЌРјРѕС†РёРѕРЅР°Р»СЊРЅС‹Рј РєР°С‡РµР»СЏРј, СЌС‚Рѕ РѕС‰СѓС‰Р°РµС‚СЃСЏ РєР°Рє В«РїСѓСЃС‚РѕС‚Р°В». РќР° СЃР°РјРѕРј РґРµР»Рµ СЌС‚Рѕ РїРµСЂРµС…РѕРґ РІ Р±РѕР»РµРµ Р·СЂРµР»С‹Р№ СѓСЂРѕРІРµРЅСЊ Р»СЋР±РІРё."
    "3. В«Р­РјРѕС†РёРё РјРѕР¶РЅРѕ РІРµСЂРЅСѓС‚СЊ, РµСЃР»Рё СЂР°Р±РѕС‚Р°С‚СЊ РЅР°Рґ РЅРёРјРёВ»"
    "Р§СѓРІСЃС‚РІР° вЂ” СЌС‚Рѕ РЅРµ С„РёРєСЃРёСЂРѕРІР°РЅРЅР°СЏ РґР°РЅРЅРѕСЃС‚СЊ, Р° РїСЂРѕС†РµСЃСЃ, РєРѕС‚РѕСЂС‹Р№ РјРѕР¶РЅРѕ РїРѕРґРїРёС‚С‹РІР°С‚СЊ. РќРѕРІС‹Рµ РІРїРµС‡Р°С‚Р»РµРЅРёСЏ, СЃРѕРІРјРµСЃС‚РЅС‹Рµ РїСЂРѕРµРєС‚С‹, РїСѓС‚РµС€РµСЃС‚РІРёСЏ, РґР°Р¶Рµ РЅРµРѕР¶РёРґР°РЅРЅС‹Рµ РјР°Р»РµРЅСЊРєРёРµ СЃСЋСЂРїСЂРёР·С‹ СЃРїРѕСЃРѕР±РЅС‹ РѕР¶РёРІРёС‚СЊ РѕС‚РЅРѕС€РµРЅРёСЏ. РњРЅРѕРіРёРµ РїР°СЂС‹, РєРѕС‚РѕСЂС‹Рµ РїРµСЂРµР¶РёР»Рё В«СѓРіР°СЃР°РЅРёРµВ», РїРѕС‚РѕРј РіРѕРІРѕСЂСЏС‚, С‡С‚Рѕ СЃС‚Р°Р»Рё Р±Р»РёР¶Рµ, С‡РµРј РєРѕРіРґР°-Р»РёР±Рѕ."
    "4. В«РџРѕС‚РµСЂСЏ СЌРјРѕС†РёР№ С‡Р°СЃС‚Рѕ РіРѕРІРѕСЂРёС‚ Рѕ РІРЅСѓС‚СЂРµРЅРЅРёС… Р±Р»РѕРєР°С…В»"
    "РРЅРѕРіРґР° С…РѕР»РѕРґ РІ РѕС‚РЅРѕС€РµРЅРёСЏС… вЂ” СЌС‚Рѕ РѕС‚СЂР°Р¶РµРЅРёРµ С‚РІРѕРёС… Р»РёС‡РЅС‹С… СЃС‚СЂР°С…РѕРІ, РѕР±РёРґ РёР»Рё РЅРµРІС‹СЂР°Р¶РµРЅРЅС‹С… С‡СѓРІСЃС‚РІ. РџРѕРєР° РёС… РЅРµ РїСЂРѕСЂР°Р±РѕС‚Р°РµС€СЊ, РґР°Р¶Рµ СЃ РЅРѕРІС‹Рј С‡РµР»РѕРІРµРєРѕРј РёСЃС‚РѕСЂРёСЏ РїРѕРІС‚РѕСЂРёС‚СЃСЏ."
    "5. В«РЈС…РѕРґ РІ РјРѕРјРµРЅС‚ СѓСЃС‚Р°Р»РѕСЃС‚Рё РјРѕР¶РµС‚ СЃС‚РѕРёС‚СЊ РѕС‡РµРЅСЊ РґРѕСЂРѕРіРѕВ»"
    "Р’Р·СЂРѕСЃР»С‹Рµ РѕС‚РЅРѕС€РµРЅРёСЏ СЃС‚СЂРѕСЏС‚СЃСЏ РЅРµ РЅР° РїРѕСЃС‚РѕСЏРЅРЅРѕР№ СЃС‚СЂР°СЃС‚Рё, Р° РЅР° СѓРјРµРЅРёРё Р±С‹С‚СЊ РІРјРµСЃС‚Рµ РІ СЂР°Р·РЅС‹Рµ РїРµСЂРёРѕРґС‹. Р•СЃР»Рё СѓР№С‚Рё РІ РјРѕРјРµРЅС‚, РєРѕРіРґР° С‡СѓРІСЃС‚РІР° РѕСЃР»Р°Р±Р»Рё РёР·-Р·Р° РѕР±СЃС‚РѕСЏС‚РµР»СЊСЃС‚РІ, РјРѕР¶РЅРѕ РїРѕС‚РµСЂСЏС‚СЊ С‡РµР»РѕРІРµРєР°, СЃ РєРѕС‚РѕСЂС‹Рј РјРѕРіР»Рѕ Р±С‹С‚СЊ РЅР°СЃС‚РѕСЏС‰РµРµ, РіР»СѓР±РѕРєРѕРµ В«РјС‹В»."
    "рџ’¬ РќР°РїРёС€Рё В«С‡СѓРІСЃС‚РІР°В» РІ РєРѕРјРјРµРЅС‚Р°СЂРёРё вЂ” Рё СЏ РїСЂРёС€Р»СЋ С‡РµРє-Р»РёСЃС‚, РєР°Рє РїРµСЂРµР·Р°РїСѓСЃС‚РёС‚СЊ РѕС‚РЅРѕС€РµРЅРёСЏ РµСЃР»Рё РµС‰С‘ РµСЃС‚СЊ С€Р°РЅСЃ."
    "Р‘С‹Р»Рѕ РёРЅС‚РµСЂРµСЃРЅРѕ, РїРѕСЃС‚Р°РІСЊ Р»Р°Р№Рє рџ¤— Рё РїРѕРґРїРёС€РёСЃСЊвЂ” С‚СѓС‚ С‚РѕР»СЊРєРѕ РїРѕР»СЊР·Р° Рё РЅРёС‡РµРіРѕ РєСЂРѕРјРµ"
    "РћРїРёСЃР°РЅРёСЏ Рє Reels СЃС‚СЂРѕРіРѕ РѕС‚ 1750 РґРѕ 1850 СЃРёРјРІРѕР»РѕРІ РІ С‚РµРєСЃС‚Рµ РЅРµ Р±РѕР»СЊС€Рµ РЅРµ РјРµРЅСЊС€Рµ "
    "Р—Р°С‚РµРј СЂР°Р·СЉСЏСЃРЅРµРЅРёРµ (РїСЂРёРјРµСЂ, РѕР±СЉСЏСЃРЅРµРЅРёРµ РїСЂРёС‡РёРЅС‹, СЃ СЌРјРѕС†РёРµР№, РѕР±СЂР°Р·Р°РјРё, РЅР°СѓС‡РЅРѕР№ РёР»Рё СЃРѕС†РёР°Р»СЊРЅРѕР№ Р»РѕРіРёРєРѕР№)"
    "РџРѕСЃР»Рµ РєР°Р¶РґРѕРіРѕ РїСѓРЅРєС‚Р° РѕС‚СЃС‚СѓРї РЅР° Р°Р±Р·Р°С†, С‡С‚РѕР±С‹ Р»РµРіРєРѕ С‡РёС‚Р°Р»РѕСЃСЊ. РџРѕСЃР»Рµ РІСЃРµС… РїСѓРЅРєС‚РѕРІ РїРµСЂРµРґ РїРѕСЃР»РµРґРЅРµР№ С„СЂР°Р·РѕР№ С‚Р°Рє Р¶Рµ РѕС‚СЃС‚СѓРї РґРµР»Р°Р№, РєР°Рє РЅР° РїСЂРёРјРµСЂРµ РІС‹С€Рµ."
    "Р’СЃС‘ РЅР°РїРёСЃР°РЅРѕ РѕС‚ Р»РёС†Р° РіРѕРІРѕСЂСЏС‰РµРіРѕ, РёСЃРєСЂРµРЅРЅРµ, Р±РµР· РІРѕРґС‹, РІ СЃС‚РёР»Рµ В«Р¶РёР·РЅРµРЅРЅРѕВ»,  РёРЅС‚РµСЂРµСЃРЅРѕ РїРѕРґР°РЅРѕ."
    "Р’ РєРѕРЅС†Рµ вЂ” РІРѕРїСЂРѕСЃ Рє Р°СѓРґРёС‚РѕСЂРёРё РёР»Рё РїСЂРёР·С‹РІ Рє РґРµР№СЃС‚РІРёСЋ, РІС‹Р·С‹РІР°СЋС‰РёР№ РєРѕРјРјРµРЅС‚Р°СЂРёРё (РЅР°РїСЂРёРјРµСЂ, вЂњРЅР°РїРёС€Рё Р·РґРѕСЂРѕРІСЊРµ вЂ” РІС‹С€Р»СЋ С‡РµРє-Р»РёСЃС‚вЂќ)"
    "РќРµ РІСЃС‚Р°РІР»СЏР№ РІ РѕРїРёСЃР°РЅРёРµ РёРјСЏ Р°РєРєР°СѓРЅС‚Р° РєРѕРіРґР° РїСЂРѕСЃРёС€СЊ РїРѕРґРїРёСЃР°С‚СЊСЃСЏ. РќРµ РёСЃРїРѕР»СЊР·СѓР№ Р·РЅР°Рє РїСЂРѕС†РµРЅС‚Р° (%) РІ Р·Р°РіРѕР»РѕРІРєР°С…"
    "Р¤РѕСЂРјР°С‚ РѕС‚РІРµС‚Р°"
    "Р—Р°РіРѕР»РѕРІРѕРє"
    "РІС‚РѕСЂР°СЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°"
    "С‚СЂРµС‚СЊСЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°"
    "С‡РµС‚РІРµСЂС‚Р°СЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°|||"
    "РћРїРёСЃР°РЅРёРµ"
    "---"
    "Р—Р°РіРѕР»РѕРІРѕРє 2"
    "Р’С‚РѕСЂР°СЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°"
    "С‚СЂРµС‚СЊСЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°"
    "С‡РµС‚РІРµСЂС‚Р°СЏ СЃС‚СЂРѕРєР° Р·Р°РіРѕР»РѕРІРєР°|||"
    "РћРїРёСЃР°РЅРёРµ 2"
    "Р—РЅР°Рє ||| Рё --- РјРЅРµ РЅСѓР¶РЅС‹ РґР»СЏ РїРѕСЃР»РµРґСѓСЋС‰РµР№ РѕР±СЂР°Р±РѕС‚РєРё. Р”Р»РёРЅРЅР°СЏ РѕРґРЅРѕР№ СЃС‚СЂРѕРєРё Р·Р°РіРѕР»РѕРІРєР° РЅРµ РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 30 СЃРёРјРІРѕР»РѕРІ, РЅРµ РЅР°С‡РёРЅР°Р№ РєР°Р¶РґСѓСЋ СЃС‚СЂРѕРєСѓ РїРѕСЃР»Рµ РїРµСЂРІРѕР№ СЃ Р±РѕР»СЊС€РѕР№ Р±СѓРєРІС‹? РќРµ РёСЃРїРѕР»СЊР·СѓР№ РєРѕРЅСЃС‚СЂСѓРєС†РёРё РІ РѕС‚РІРµС‚Рµ СЃР»РѕРІР° Р—Р°РіРѕР»РѕРІРѕРє 1, Р—Р°РіРѕР»РѕРІРѕРє 2, РћРїРёСЃР°РЅРёРµ 1, РћРїРёСЃР°РЅРёРµ 2. Р­С‚Рѕ РІСЃС‘ РЅРµ РЅСѓР¶РЅРѕ"
)

# ---- Helper functions ------------------------------------------------------

def escape(text: str) -> str:
    """Escape text for ffmpeg drawtext.

    ffmpeg's drawtext filter treats `:`, `,`, `;` and `'` as special
    characters. They must be escaped to avoid "No option name" errors when
    user supplied titles contain them.
    """
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("'", "\\'")
        # escape real newlines so ffmpeg draws multiple lines
        .replace("\n", "\\\\n")
    )


def escape_path(path: str) -> str:
    """Escape file paths for ffmpeg drawtext.

    Windows font paths contain a drive letter like ``C:`` which ffmpeg treats as
    a separator unless the colon is escaped.  We also normalize backslashes to
    forward slashes so the path works across platforms.
    """
    return path.replace("\\", "/").replace(":", "\\:")


def probe_size(path: str) -> tuple[int, int]:
    """Return (width, height) of the first video stream using ffprobe."""
    result = subprocess.run([
        FFPROBE,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0",
        path,
    ], stdout=subprocess.PIPE, text=True, check=True)
    w, h = result.stdout.strip().split(",")
    return int(w), int(h)

def probe_duration(path: str) -> float:
    """Return duration (seconds) of the media file using ffprobe."""
    result = subprocess.run(
        [
            FFPROBE,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def fit_text_to_mask(
    text: str,
    mask: tuple[int, int, int, int],
    font_path: str,
    initial_size: int,
) -> tuple[int, str]:
    """Wrap and scale *text* so it fits within the mask.

    Returns a tuple of the adjusted font size and newline-joined text.
    """
    _, _, max_w, max_h = mask
    max_w = int(max_w)
    max_h = int(max_h)
    size = initial_size
    while size > 5:
        font = ImageFont.truetype(font_path, size)

        # wrap text to mask width using current font size
        lines: list[str] = []
        for paragraph in text.splitlines():
            if not paragraph:
                lines.append("")
                continue
            words = paragraph.split()
            line = words[0]
            for word in words[1:]:
                test = f"{line} {word}"
                if font.getlength(test) <= max_w:
                    line = test
                else:
                    lines.append(line)
                    line = word
            lines.append(line)
        wrapped = "\n".join(lines)

        # measure multiline text bounding box with tighter line spacing
        line_spacing = -int(size * 0.05)
        dummy = Image.new("RGB", (max_w, max_h))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.multiline_textbbox(
            (0, 0), wrapped, font=font, spacing=line_spacing
        )
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        if text_w <= max_w and text_h <= max_h:
            return size, wrapped
        size -= 1

    font = ImageFont.truetype(font_path, size)
    lines = [p for p in text.splitlines()]
    return size, "\n".join(lines)


def chunks(iterable, size):
    """Yield lists of length *size* from *iterable*."""
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk


def _message_content(msg) -> str:
    """Return plain text from an OpenAI ChatCompletion message."""
    content = msg.content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def generate_descriptions_batch(titles: list[str], prompt_override: str | None = None) -> list[str]:
    """Generate descriptions for a list of titles using one request.

    The model is asked to return each pair in the format
    ``<Р·Р°РіРѕР»РѕРІРѕРє>|||<РѕРїРёСЃР°РЅРёРµ>`` and separate pairs with a line ``---``.
    Only the description part is used in the result.
    """

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
    tmpl = prompt_override if prompt_override else DESCRIPTION_PROMPT
    prompt = tmpl.format(titles=numbered)
    resp = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50000,
        temperature=0.25,
    )
    text = _message_content(resp.choices[0].message)
    descriptions = []
    for block in text.split("---"):
        block = block.strip()
        if not block:
            continue
        parts = block.split("|||")
        # Fallback-friendly: if delimiter is missing, treat whole block as description
        if len(parts) > 1:
            desc = parts[1]
        else:
            desc = block
        # normalize escaped newlines
        descriptions.append(desc.strip().replace("\\n", "\n"))
    # ensure same length
    while len(descriptions) < len(titles):
        descriptions.append("")
    return descriptions[: len(titles)]


def generate_descriptions_batch_structured(titles: list[str], prompt_override: str | None = None) -> list[str]:
    """Structured variant: ask model to return JSON conforming to a schema.

    Falls back to generate_descriptions_batch on failure or when no prompt_override.
    """
    if not titles:
        return []
    if not prompt_override:
        return generate_descriptions_batch(titles, prompt_override)
    try:
        import json as _json
        # Augment system with strict JSON response and ordering requirements
        system_content = (
            (prompt_override or "").rstrip()
            + "\n\n"
            + "РџСЂР°РІРёР»Р° РѕС‚РІРµС‚Р° (JSON):\n"
            + "- Р’РµСЂРЅРё СЃС‚СЂРѕРіРѕ JSON РїРѕ СЃС…РµРјРµ (Р±РµР· РїСЂРµС„РёРєСЃРѕРІ/РїРѕСЏСЃРЅРµРЅРёР№ РІРЅРµ JSON).\n"
            + "- РљРѕР»РёС‡РµСЃС‚РІРѕ СЌР»РµРјРµРЅС‚РѕРІ items РґРѕР»Р¶РЅРѕ СЂР°РІРЅСЏС‚СЊСЃСЏ РєРѕР»РёС‡РµСЃС‚РІСѓ РІС…РѕРґРЅС‹С… Р·Р°РіРѕР»РѕРІРєРѕРІ.\n"
            + "- РЎРѕС…СЂР°РЅСЏР№ РїРѕСЂСЏРґРѕРє: i-Р№ СЌР»РµРјРµРЅС‚ items РѕС‚РЅРѕСЃРёС‚СЃСЏ Рє i-РјСѓ Р·Р°РіРѕР»РѕРІРєСѓ РёР· titles.\n"
            + "- РџРѕР»Рµ input_title РґРѕР»Р¶РЅРѕ РґРѕСЃР»РѕРІРЅРѕ СЃРѕРІРїР°РґР°С‚СЊ СЃ РёСЃС…РѕРґРЅС‹Рј Р·Р°РіРѕР»РѕРІРєРѕРј.\n"
        )
        user_payload = {"titles": titles}
        taboo_regex = r"(?i)(СЃРµРєСЃ|РґРµРЅСЊРіРё|РЅР°СЂРєРѕС‚|РЅР°СЃРёР»Рё|\\*)"
        n_items = len(titles)
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": n_items,
                    "maxItems": n_items,
                    "items": {
                        "type": "object",
                        "properties": {
                            "input_title": {"type": "string", "minLength": 3, "maxLength": 300},
                            "points": {
                                "type": "array",
                                "minItems": 5,
                                "maxItems": 5,
                                "items": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 500,
                                    "not": {"pattern": taboo_regex},
                                },
                            },
                            "question": {"type": "string", "minLength": 1, "maxLength": 140, "not": {"pattern": taboo_regex}},
                            "cta_line": {"type": "string", "minLength": 1, "maxLength": 180, "not": {"pattern": taboo_regex}},
                            "share_line": {"type": "string", "minLength": 1, "maxLength": 180, "not": {"pattern": taboo_regex}},
                            "subscribe_line": {"type": "string", "minLength": 1, "maxLength": 200, "not": {"pattern": taboo_regex}},
                        },
                        "required": ["input_title","points","question","cta_line","share_line","subscribe_line"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        }

        resp = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": _json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.25,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "reels_batch", "strict": True, "schema": schema},
            },
            max_tokens=50000,
        )
        content = _message_content(resp.choices[0].message)
        data = _json.loads(content)
        # Preallocate results aligned to input titles
        out: list[str] = [""] * n_items
        by_input: dict[str, str] = {}
        for item in data.get("items", []):
            pts = item.get("points", [])
            question = (item.get("question") or "").strip()
            cta = (item.get("cta_line") or "").strip()
            share = (item.get("share_line") or "").strip()
            sub = (item.get("subscribe_line") or "").strip()
            body = "\n\n".join((p or "").strip() for p in pts if str(p).strip())
            full = "".join([
                body,
                "\n\n" if body else "",
                question,
                "\n" if question else "",
                cta,
                "\n" if cta else "",
                share,
                "\n" if share else "",
                sub,
            ]).strip()
            key = (item.get("input_title") or "").strip()
            if key:
                by_input[key] = full
        # Fill by exact title match first
        for idx, t in enumerate(titles):
            if t in by_input:
                out[idx] = by_input[t]
        # If still missing, try structured single-call for each missing
        for idx, t in enumerate(titles):
            if not out[idx]:
                try:
                    single = generate_descriptions_batch_structured([t], prompt_override)
                    if single and single[0]:
                        out[idx] = single[0]
                except Exception:
                    pass
        # If still missing, fallback per-title (legacy plain text)
        for idx, t in enumerate(titles):
            if not out[idx]:
                try:
                    single = generate_descriptions_batch([t], prompt_override)
                    out[idx] = (single[0] if single else "")
                except Exception:
                    out[idx] = ""
        return out
    except Exception:
        return generate_descriptions_batch(titles, prompt_override)


def generate_titles_descriptions_batch(topics: list[str], prompt_override: str | None = None) -> list[tuple[str, str]]:
    """Generate titles and descriptions for a list of topics in one request."""

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(topics))
    tmpl = prompt_override if prompt_override else TITLE_DESCRIPTION_PROMPT
    prompt = tmpl.format(topics=numbered)
    resp = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50000,
        temperature=0.25,
    )
    text = _message_content(resp.choices[0].message)
    results: list[tuple[str, str]] = []
    for block in text.split("---"):
        block = block.strip()
        if not block:
            continue
        parts = block.split("|||")
        title = parts[0].strip() if parts else ""
        desc = parts[1].strip() if len(parts) > 1 else ""
        results.append((title, desc))
    while len(results) < len(topics):
        results.append(("", ""))
    return results[: len(topics)]


def _generate_title_description_single(topic: str, system_prompt: str | None, separator: str) -> tuple[str, str]:
    """Call the model once and parse a single title/description pair using a separator."""
    system_parts: list[str] = []
    if system_prompt and system_prompt.strip():
        system_parts.append(system_prompt.strip())
    system_parts.append(
        f"Strict output format: <TITLE>{separator}<DESCRIPTION>. No extra prefixes, suffixes, or commentary."
    )
    system_content = "\n\n".join(system_parts).strip()

    user_content = f"Topic: {topic.strip()}\nReturn exactly one title and one description that follow the instructions."

    resp = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        temperature=0.25,
        max_tokens=50000,
    )
    raw = _message_content(resp.choices[0].message).strip()
    if separator in raw:
        title_raw, desc_raw = raw.split(separator, 1)
    else:
        lines = raw.splitlines()
        title_raw = lines[0] if lines else ""
        desc_raw = "\n".join(lines[1:]) if len(lines) > 1 else ""
    title = title_raw.strip()
    description = desc_raw.strip()
    return title, description

def generate_titles_descriptions_batch_json(
    topics: list[str],
    system_prompt: str | None = None,
    separator: str = "|||",
) -> list[tuple[str, str]]:
    """Generate (title, description) pairs sequentially using the single-output prompt."""
    if not topics:
        return []
    return [_generate_title_description_single(topic, system_prompt, separator) for topic in topics]

def generate_titles_descriptions_batch_json_points(
    topics: list[str],
    system_prompt: str | None = None,
    separator: str = "|||",
) -> list[tuple[str, str]]:
    """Compatibility shim that reuses the single-output generator."""
    return generate_titles_descriptions_batch_json(topics, system_prompt=system_prompt, separator=separator)

def refine_description(text: str, system_prompt: str | None = None, min_chars: int = 1900, max_chars: int = 2190) -> str:
    """Refine a single description to fit within [min_chars, max_chars].

    Keeps tone and structure; avoids taboo lexicon. Safe to fail: returns original text on error.
    """
    try:
        import json as _json
        taboo_regex = r"(?i)(СЃРµРєСЃ|РґРµРЅСЊРіРё|РЅР°СЂРєРѕС‚|РЅР°СЃРёР»Рё|\\*)"
        sys = (
            (system_prompt or "").rstrip()
            + "\n\n"
            + "РџСЂР°РІРёР»Р° РґРѕСЂР°Р±РѕС‚РєРё (РЎРўР РћР“Рћ):\n"
            + f"- РЎРѕС…СЂР°РЅРё СЃРјС‹СЃР» Рё СЃС‚СЂСѓРєС‚СѓСЂСѓ (5 РїСѓРЅРєС‚РѕРІ + 3 СЃС‚СЂРѕРєРё С„РёРЅР°Р»Р°). Р”РѕРІРµРґРё РѕР±СЉС‘Рј РґРѕ {min_chars}вЂ“{max_chars} СЃРёРјРІРѕР»РѕРІ.\n"
            + "- Р‘РµР· С‚Р°Р±Сѓ-Р»РµРєСЃРёРєРё Рё СЌРІС„РµРјРёР·РјРѕРІ; С‚РѕР»СЊРєРѕ РєРѕСЂРѕС‚РєРёРµ С‚РёСЂРµ вЂ-вЂ™.\n"
            + "- Р’РµСЂРЅРё РЎРўР РћР“Рћ JSON РїРѕ СЃС…РµРјРµ (РЅРёРєР°РєРѕРіРѕ С‚РµРєСЃС‚Р° РІРЅРµ JSON).\n"
        )
        schema = {
            "type": "object",
            "properties": {
                "description_final": {
                    "type": "string",
                    "minLength": int(min_chars),
                    "maxLength": int(max_chars),
                    "not": {"pattern": taboo_regex},
                }
            },
            "required": ["description_final"],
            "additionalProperties": False,
        }
        resp = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": _json.dumps({"draft": text}, ensure_ascii=False)},
            ],
            temperature=0.2,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "refine_one", "strict": True, "schema": schema},
            },
            max_tokens=2000,
        )
        data = _json.loads(_message_content(resp.choices[0].message))
        new_text = str((data or {}).get("description_final") or "").strip()
        return new_text or text
    except Exception:
        return text


def pick_music(music_dir: str, mode: str) -> str:
    """Choose a music file from the directory."""
    files = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav"))]
    if not files:
        raise FileNotFoundError("РњСѓР·С‹РєР° РЅРµ РЅР°Р№РґРµРЅР° РІ РІС‹Р±СЂР°РЅРЅРѕР№ РїР°РїРєРµ")
    if mode == "random" or mode == "smart":
        return os.path.join(music_dir, random.choice(files))
    raise ValueError("Unknown music mode")


def build_ffmpeg_filter(w: int, h: int, params: dict, emoji_input_index: int = 2) -> tuple[str, str]:
    """Build filter_complex string for ffmpeg."""
    mask = params["mask"]  # (x, y, w, h)
    caption_mask = params["caption_mask"]  # (x, y, w, h)
    title_font = escape_path(params["title_font"])
    caption_font = escape_path(params["caption_font"])
    caption_text = escape(params["caption_text"])
    title_size = params["title_size"]
    caption_size = params["caption_size"]
    text_color = params["text_color"]
    box_color = params["box_color"]
    box_alpha = params["box_alpha"]
    caption_text_width = params["caption_text_width"]
    gradient_enabled = bool(params.get("full_vertical_video"))
    gradient_height_raw = params.get("top_gradient_height")
    gradient_strength_raw = params.get("top_gradient_strength")

    tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
    tmp.write(params["title"])
    tmp.flush()
    tmp.close()
    title_file = escape_path(tmp.name)

    caption_x, caption_y, caption_w, caption_h = caption_mask
    caption_text_y = caption_y + caption_h - caption_size - 10
    total_caption_width = caption_text_width + caption_size + 10
    caption_text_x = int(caption_x + (caption_w - total_caption_width) / 2)
    arrow_x = caption_text_x + caption_text_width + 10

    start_offset = float(params.get("start_offset", 0.0) or 0.0)
    chain_steps: list[str] = []
    if start_offset > 0:
        chain_steps.append(f"trim=start={start_offset:.2f},setpts=PTS-STARTPTS")
    chain_steps.append("scale=1080:1920:force_original_aspect_ratio=decrease")
    if not gradient_enabled:
        chain_steps.append("pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black")
    if chain_steps:
        base = "[0:v]" + chain_steps[0]
        if len(chain_steps) > 1:
            base += "," + ",".join(chain_steps[1:])
    else:
        base = "[0:v]"
    unique_filter = params.get("unique_filter")
    if unique_filter:
        base += f",{unique_filter}"

    filters = [base]
    if box_alpha > 0:
        filters.append(
            f"drawbox={mask[0]}:{mask[1]}:{mask[2]}:{mask[3]}:color={box_color}@{box_alpha}:t=fill"
        )
        filters.append(
            f"drawbox={caption_mask[0]}:{caption_mask[1]}:{caption_mask[2]}:{caption_mask[3]}:color={box_color}@{box_alpha}:t=fill"
        )

    line_spacing = -int(title_size / 1.3)
    title_drawtext = (
        f"drawtext=fontfile='{title_font}':textfile='{title_file}':x={mask[0]}+({mask[2]}-text_w)/2:"
        f"y={mask[1]}+{mask[3]}-text_h-10:fontsize={title_size}:fontcolor={text_color}:"
        f"line_spacing={line_spacing}:text_align=center"
    )
    caption_drawtext = (
        f"drawtext=fontfile='{caption_font}':text='{caption_text}':x={caption_text_x}:"
        f"y={caption_text_y}:fontsize={caption_size}:fontcolor={text_color}"
    )

    filter_video = ",".join(filters)

    gradient_filter = None
    if gradient_enabled:
        try:
            gradient_height = int(gradient_height_raw) if gradient_height_raw is not None else 320
        except (TypeError, ValueError):
            gradient_height = 320
        try:
            gradient_strength = float(gradient_strength_raw) if gradient_strength_raw is not None else 0.65
        except (TypeError, ValueError):
            gradient_strength = 0.65
        gradient_filter = _build_top_gradient_filter(1080, 1920, gradient_height, gradient_strength)

    filter_parts: list[str] = []
    filter_parts.append(f"{filter_video}[base]")
    current_stream = "base"
    if gradient_filter:
        filter_parts.append(gradient_filter)
        filter_parts.append(f"[{current_stream}][grad]overlay=0:0[base_grad]")
        current_stream = "base_grad"
    filter_parts.append(f"[{current_stream}]{title_drawtext}[with_title]")
    current_stream = "with_title"
    filter_parts.append(f"[{current_stream}]{caption_drawtext}[with_caption]")
    current_stream = "with_caption"
    filter_parts.append(f"[{emoji_input_index}:v]scale={caption_size}:{caption_size}[emoji]")
    filter_parts.append(f"[{current_stream}][emoji]overlay={arrow_x}:{caption_text_y}[v]")
    filter_chain = ";".join(filter_parts)
    return filter_chain, tmp.name



def _build_video_base_chain(start_offset: float, unique_filter: str, full_vertical: bool = False) -> str:
    steps: list[str] = []
    if start_offset and start_offset > 0:
        steps.append(f"trim=start={start_offset:.2f},setpts=PTS-STARTPTS")
    steps.append("scale=1080:1920:force_original_aspect_ratio=decrease")
    if not full_vertical:
        steps.append("pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black")
    if steps:
        base = "[0:v]" + steps[0]
        if len(steps) > 1:
            base += "," + ",".join(steps[1:])
    else:
        base = "[0:v]"
    if unique_filter:
        base += f",{unique_filter}"
    return base
def _build_top_gradient_filter(
    width: int,
    height: int,
    gradient_height: int | None,
    gradient_strength: float | None,
) -> str | None:
    if not gradient_height or gradient_height <= 0:
        return None
    if not gradient_strength or gradient_strength <= 0:
        return None
    gradient_height_int = max(1, min(int(gradient_height), height))
    strength = max(0.0, min(float(gradient_strength), 1.0))
    max_alpha = int(round(255 * strength))
    if max_alpha <= 0:
        return None
    grad_height_float = f"{float(gradient_height_int):.4f}"
    alpha_expr = (
        f"if(lt(Y,{gradient_height_int}),clip({max_alpha}*(1-(Y/{grad_height_float})),0,{max_alpha}),0)"
    )
    return (
        f"color=c=black:s={width}x{height},format=rgba,"
        f"geq=r='0':g='0':b='0':a='{alpha_expr}'[grad]"
    )


def _compute_dots_geometry(caption_mask: tuple[int, int, int, int], dots_image: str, scale_ratio: float) -> tuple[int, int, int, int]:
    caption_x, caption_y, caption_w, caption_h = caption_mask
    try:
        with Image.open(dots_image) as img:
            dots_w, dots_h = img.size
    except FileNotFoundError:
        raise FileNotFoundError(f"Dots image not found: {dots_image}") from None
    if dots_w == 0 or dots_h == 0:
        return caption_w, caption_h, caption_x, caption_y

    scale_ratio = max(0.1, min(scale_ratio or 0.6, 1.0))
    target_w = max(1, int(round(caption_w * scale_ratio)))
    scale_w = target_w
    scale_h = int(round(scale_w * dots_h / dots_w))

    if scale_h > caption_h:
        scale_h = caption_h
        scale_w = max(1, int(round(scale_h * dots_w / dots_h)))

    offset_x = caption_x + (caption_w - scale_w) // 2
    offset_y = caption_y + (caption_h - scale_h) // 2
    return scale_w, scale_h, offset_x, offset_y

def process_video_with_dots(
    video_path: str,
    music_path: str | None,
    out_path: str,
    title: str,
    description: str,
    mask: tuple[int, int, int, int],
    caption_mask: tuple[int, int, int, int],
    title_font: str,
    title_size: int,
    text_color: str,
    box_color: str,
    box_alpha: float,
    dots_image: str | None = None,
    dots_scale: float = 0.6,
    highlight_color: str | None = None,
    full_vertical: bool = False,
    top_gradient_height: int | None = None,
    top_gradient_strength: float | None = None,
) -> None:
    """Create reel with title text and dots image instead of caption text."""
    dots_path = dots_image or DOTS_PNG
    probe_size(video_path)
    duration = probe_duration(video_path)
    title_size, title = fit_text_to_mask(title, mask, title_font, title_size)
    unique_filter = ""
    start_offset = 0.0
    base_chain = _build_video_base_chain(start_offset, unique_filter, full_vertical=full_vertical)

    gradient_height = top_gradient_height if top_gradient_height is not None else 320
    gradient_strength = top_gradient_strength if top_gradient_strength is not None else 0.65
    gradient_filter = None
    if full_vertical:
        gradient_filter = _build_top_gradient_filter(1080, 1920, gradient_height, gradient_strength)

    tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
    try:
        tmp.write(title)
        tmp.flush()
        title_file = escape_path(tmp.name)
        dots_w, dots_h, dots_x, dots_y = _compute_dots_geometry(caption_mask, dots_path, dots_scale)

        filters = [base_chain]
        if box_alpha > 0:
            filters.append(
                f"drawbox={mask[0]}:{mask[1]}:{mask[2]}:{mask[3]}:color={box_color}@{box_alpha}:t=fill"
            )
            filters.append(
                f"drawbox={caption_mask[0]}:{caption_mask[1]}:{caption_mask[2]}:{caption_mask[3]}:color={box_color}@{box_alpha}:t=fill"
            )
        drawtext_cmd = (
            f"drawtext=fontfile='{escape_path(title_font)}':textfile='{title_file}':x={mask[0]}+({mask[2]}-text_w)/2:"
            f"y={mask[1]}+{mask[3]}-text_h-10:fontsize={title_size}:fontcolor={text_color}:"
            f"line_spacing={-int(title_size/1.3)}:text_align=center"
        )

        filter_video = ",".join(filters)
        filter_parts: list[str] = []
        filter_parts.append(f"{filter_video}[base]")
        current_stream = "base"
        if gradient_filter:
            filter_parts.append(gradient_filter)
            filter_parts.append(f"[{current_stream}][grad]overlay=0:0[base_grad]")
            current_stream = "base_grad"
        filter_parts.append(f"[{current_stream}]{drawtext_cmd}[texted]")
        current_stream = "texted"
        dots_input_index = 2 if music_path else 1
        filter_parts.append(f"[{dots_input_index}:v]scale={dots_w}:{dots_h}[dots]")
        filter_parts.append(f"[{current_stream}][dots]overlay={dots_x}:{dots_y}[v]")
        filter_chain = ";".join(filter_parts)

        effective_duration = max(duration - start_offset, 0.1)
        cmd = [FFMPEG, "-y", "-i", video_path]
        audio_input_index: int | None = None
        if music_path:
            cmd += ["-i", music_path]
            audio_input_index = 1
        cmd += ["-i", dots_path]
        cmd += [
            "-filter_complex",
            filter_chain,
            "-map",
            "[v]",
        ]
        if music_path and audio_input_index is not None:
            cmd += ["-map", f"{audio_input_index}:a"]
        else:
            cmd += ["-map", "0:a?"]
        cmd += [
            "-shortest",
            "-t",
            f"{effective_duration:.3f}",
            out_path,
        ]
        subprocess.run(cmd, check=True)
    finally:
        tmp.close()
        try:
            os.remove(tmp.name)
        except OSError:
            pass

    with open(os.path.splitext(out_path)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write(title + "\n\n" + description)

def process_video(
        video_path: str,
        music_path: str | None,
        out_path: str,
        title: str,
        description: str,
        mask: tuple[int, int, int, int],
        caption_mask: tuple[int, int, int, int],
        title_font: str,
        caption_font: str,
        title_size: int,
        caption_size: int,
        text_color: str,
        box_color: str,
        box_alpha: float,
        full_vertical: bool = False,
        top_gradient_height: int | None = None,
        top_gradient_strength: float | None = None,
    ) -> None:
        """Create final reel video with overlays and music."""
        w, h = probe_size(video_path)
        duration = probe_duration(video_path)
        caption_text = random.choice(CAPTION_CHOICES)
        font_obj = ImageFont.truetype(caption_font, caption_size)
        caption_text_width = int(font_obj.getlength(caption_text))
        title_size, title = fit_text_to_mask(title, mask, title_font, title_size)
        unique_filter = ""
        start_offset = 0.0

        arrow_input_index = 2 if music_path else 1
        filter_str, title_file = build_ffmpeg_filter(
            w,
            h,
            {
                "mask": mask,
                "caption_mask": caption_mask,
                "title_font": title_font,
                "caption_font": caption_font,
                "title": title,
                "caption_text": caption_text,
                "caption_text_width": caption_text_width,
                "title_size": title_size,
                "caption_size": caption_size,
                "text_color": text_color,
                "box_color": box_color,
                "box_alpha": box_alpha,
                "unique_filter": unique_filter,
                "start_offset": start_offset,
                "full_vertical_video": full_vertical,
                "top_gradient_height": top_gradient_height,
                "top_gradient_strength": top_gradient_strength,
            },
            emoji_input_index=arrow_input_index,
        )

        cmd: list[str] = [FFMPEG, "-y", "-i", video_path]
        audio_input_index: int | None = None
        if music_path:
            cmd += ["-i", music_path]
            audio_input_index = 1
        cmd += ["-i", ARROW_PNG]
        cmd += [
            "-filter_complex",
            filter_str,
            "-map",
            "[v]",
        ]
        if music_path and audio_input_index is not None:
            cmd += ["-map", f"{audio_input_index}:a"]
        else:
            cmd += ["-map", "0:a?"]
        cmd += [
            "-shortest",
            "-t",
            f"{duration:.3f}",
            out_path,
        ]
        try:
            subprocess.run(cmd, check=True)
        finally:
            os.remove(title_file)
        with open(os.path.splitext(out_path)[0] + ".txt", "w", encoding="utf-8") as f:
            f.write(title + "\n\n" + description)

# ---- Mask editor -----------------------------------------------------------

class MaskEditor(tk.Toplevel):
    """Canvas window to adjust title and caption masks."""

    def __init__(
        self,
        master: tk.Tk,
        frame_img: Image.Image,
        title_mask: tuple[int, int, int, int],
        caption_mask: tuple[int, int, int, int],
        title_font: str,
        caption_font: str,
        title_size: int,
        caption_size: int,
        text_color: str,
        box_color: str,
        box_alpha: float,
        callback,
    ) -> None:
        super().__init__(master)
        self.title("Р РµРґР°РєС‚РѕСЂ РјР°СЃРєРё")
        self.callback = callback
        self.font_title_path = title_font
        self.font_caption_path = caption_font
        self.title_size = title_size
        self.caption_size = caption_size
        self.text_color = text_color
        self.box_color = box_color
        self.box_alpha = box_alpha

        self.scale = 0.5
        self.orig_img = frame_img
        self.base_img = frame_img.resize(
            (int(frame_img.width * self.scale), int(frame_img.height * self.scale))
        )
        self.arrow_full = Image.open(ARROW_PNG)

        self.rects = {
            "title": [
                title_mask[0] * self.scale,
                title_mask[1] * self.scale,
                title_mask[2] * self.scale,
                title_mask[3] * self.scale,
            ],
            "caption": [
                caption_mask[0] * self.scale,
                caption_mask[1] * self.scale,
                caption_mask[2] * self.scale,
                caption_mask[3] * self.scale,
            ],
        }

        self.canvas = tk.Canvas(self, width=self.base_img.width, height=self.base_img.height)
        self.canvas.pack()

        self.image_id = None
        self.handles: dict[str, dict[str, int]] = {"title": {}, "caption": {}}
        self.active_rect = None

        self.render_overlay()

        self.dragging = None
        self.off_x = 0
        self.off_y = 0
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        btn = tk.Frame(self)
        btn.pack(pady=5)
        tk.Button(btn, text="РџСЂРёРјРµРЅРёС‚СЊ", command=self.apply).pack(side="left", padx=5)
        tk.Button(btn, text="РћС‚РјРµРЅР°", command=self.destroy).pack(side="left", padx=5)

    # --- drawing ---------------------------------------------------------
    def render_overlay(self) -> None:
        img = self.base_img.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        box_rgba = ImageColor.getrgb(self.box_color) + (int(self.box_alpha * 255),)

        # title
        tx, ty, tw, th = self.rects["title"]
        draw.rectangle([tx, ty, tx + tw, ty + th], fill=box_rgba)
        sample = "РђР‘Р’Р“Р”Р•РЃР–Р—РР™РљР›РњРќРћРџР РЎРўРЈР¤РҐР¦Р§РЁР©РЄР«Р¬Р­Р®РЇ"
        size, wrapped = fit_text_to_mask(
            sample, (0, 0, tw, th), self.font_title_path, int(self.title_size * self.scale)
        )
        font_title = ImageFont.truetype(self.font_title_path, size)
        line_spacing = -int(size * 0.05)
        # measure multiline text for proper centering
        bbox = draw.multiline_textbbox(
            (0, 0), wrapped, font=font_title, spacing=line_spacing
        )
        t_w = bbox[2] - bbox[0]
        t_h = bbox[3] - bbox[1]
        draw.multiline_text(
            (tx + (tw - t_w) / 2, ty + th - t_h - 10),
            wrapped,
            font=font_title,
            fill=self.text_color,
            align="center",
            spacing=line_spacing,
        )

        # caption
        cx, cy, cw, ch = self.rects["caption"]
        draw.rectangle([cx, cy, cx + cw, cy + ch], fill=box_rgba)
        font_caption = ImageFont.truetype(
            self.font_caption_path, int(self.caption_size * self.scale)
        )
        arrow_size = int(self.caption_size * self.scale)
        info_w = font_caption.getlength("РЎРјРѕС‚СЂРё РѕРїРёСЃР°РЅРёРµ")
        total_w = info_w + arrow_size + 10
        text_x = cx + (cw - total_w) / 2
        text_y = cy + ch - self.caption_size * self.scale - 10
        draw.text(
            (text_x, text_y),
            "РЎРјРѕС‚СЂРё РѕРїРёСЃР°РЅРёРµ",
            font=font_caption,
            fill=self.text_color,
        )
        arrow_img = self.arrow_full.resize((arrow_size, arrow_size))
        img.paste(
            arrow_img,
            (int(text_x + info_w + 10), int(text_y)),
            arrow_img,
        )

        self.rendered_img = img
        self.tk_img = ImageTk.PhotoImage(img)
        if self.image_id is None:
            self.image_id = self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        else:
            self.canvas.itemconfig(self.image_id, image=self.tk_img)

        # draw rectangles and handles
        for key, rect in self.rects.items():
            x, y, w, h = rect
            color = "red" if key == "title" else "blue"
            self.rect_ids = getattr(self, "rect_ids", {})
            if key not in self.rect_ids:
                self.rect_ids[key] = self.canvas.create_rectangle(
                    x, y, x + w, y + h, outline=color, width=2
                )
            else:
                self.canvas.coords(self.rect_ids[key], x, y, x + w, y + h)

            handle = 6
            coords = {
                "nw": (x, y),
                "ne": (x + w, y),
                "sw": (x, y + h),
                "se": (x + w, y + h),
            }
            for name, (cx, cy) in coords.items():
                if name in self.handles[key]:
                    self.canvas.coords(
                        self.handles[key][name], cx - handle, cy - handle, cx + handle, cy + handle
                    )
                else:
                    self.handles[key][name] = self.canvas.create_rectangle(
                        cx - handle, cy - handle, cx + handle, cy + handle, fill=color
                    )

    # --- events -----------------------------------------------------------
    def find_active(self, event):
        for key, handles in self.handles.items():
            for name, hid in handles.items():
                x1, y1, x2, y2 = self.canvas.coords(hid)
                if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                    self.active_rect = key
                    return name
        for key, rect in self.rects.items():
            x, y, w, h = rect
            if x <= event.x <= x + w and y <= event.y <= y + h:
                self.active_rect = key
                self.off_x = event.x - x
                self.off_y = event.y - y
                return "move"
        return None

    def on_press(self, event):
        self.dragging = self.find_active(event)

    def on_drag(self, event):
        if not self.dragging or not self.active_rect:
            return
        rect = self.rects[self.active_rect]
        x, y, w, h = rect
        max_w, max_h = self.base_img.width, self.base_img.height
        min_size = 20
        if self.dragging == "move":
            nx = event.x - self.off_x
            ny = event.y - self.off_y
            nx = max(0, min(nx, max_w - w))
            ny = max(0, min(ny, max_h - h))
            rect[0], rect[1] = nx, ny
        elif self.dragging == "nw":
            nx = max(0, min(event.x, x + w - min_size))
            ny = max(0, min(event.y, y + h - min_size))
            rect[2] += x - nx
            rect[3] += y - ny
            rect[0], rect[1] = nx, ny
        elif self.dragging == "ne":
            nx = min(max_w, max(event.x, x + min_size))
            ny = max(0, min(event.y, y + h - min_size))
            rect[2] = nx - x
            rect[3] += y - ny
            rect[1] = ny
        elif self.dragging == "sw":
            nx = max(0, min(event.x, x + w - min_size))
            ny = min(max_h, max(event.y, y + min_size))
            rect[2] += x - nx
            rect[0] = nx
            rect[3] = ny - y
        elif self.dragging == "se":
            nx = min(max_w, max(event.x, x + min_size))
            ny = min(max_h, max(event.y, y + min_size))
            rect[2] = nx - x
            rect[3] = ny - y
        self.render_overlay()

    def on_release(self, _):
        self.dragging = None
        self.active_rect = None

    # --- finalize --------------------------------------------------------
    def apply(self) -> None:
        title_mask = (
            int(self.rects["title"][0] / self.scale),
            int(self.rects["title"][1] / self.scale),
            int(self.rects["title"][2] / self.scale),
            int(self.rects["title"][3] / self.scale),
        )
        caption_mask = (
            int(self.rects["caption"][0] / self.scale),
            int(self.rects["caption"][1] / self.scale),
            int(self.rects["caption"][2] / self.scale),
            int(self.rects["caption"][3] / self.scale),
        )

        img = self.orig_img.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        box_rgba = ImageColor.getrgb(self.box_color) + (int(self.box_alpha * 255),)
        # title
        tx, ty, tw, th = title_mask
        draw.rectangle([tx, ty, tx + tw, ty + th], fill=box_rgba)
        font_title = ImageFont.truetype(self.font_title_path, self.title_size)
        bbox = font_title.getbbox("РўР•РЎРўРћР’Р«Р™ РўР•РљРЎРў")
        t_w = bbox[2] - bbox[0]
        t_h = bbox[3] - bbox[1]
        draw.text(
            (tx + (tw - t_w) / 2, ty + th - t_h - 10),
            "РўР•РЎРўРћР’Р«Р™ РўР•РљРЎРў",
            font=font_title,
            fill=self.text_color,
        )
        # caption
        cx, cy, cw, ch = caption_mask
        draw.rectangle([cx, cy, cx + cw, cy + ch], fill=box_rgba)
        font_caption = ImageFont.truetype(self.font_caption_path, self.caption_size)
        arrow_size = self.caption_size
        info_w = font_caption.getlength("РЎРјРѕС‚СЂРё РѕРїРёСЃР°РЅРёРµ")
        total_w = info_w + arrow_size + 10
        text_x = cx + (cw - total_w) / 2
        text_y = cy + ch - self.caption_size - 10
        draw.text(
            (text_x, text_y),
            "РЎРјРѕС‚СЂРё РѕРїРёСЃР°РЅРёРµ",
            font=font_caption,
            fill=self.text_color,
        )
        arrow_img = self.arrow_full.resize((arrow_size, arrow_size))
        img.paste(
            arrow_img,
            (int(text_x + info_w + 10), int(text_y)),
            arrow_img,
        )

        self.callback(title_mask, caption_mask, img)
        self.destroy()


# ---- Tkinter GUI -----------------------------------------------------------
class ReelsGeneratorApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("Reels GPT Generator")

        # state
        self.video_dir = ""
        self.music_dir = ""
        self.titles_file = ""
        self.font_title_path = ""
        self.font_caption_path = ""
        self.count = tk.IntVar(value=1)
        self.mode = tk.StringVar(value="titles")
        self.music_mode = tk.StringVar(value="random")
        self.mask_vars = [tk.IntVar(value=50), tk.IntVar(value=50), tk.IntVar(value=500), tk.IntVar(value=200)]
        self.caption_mask_vars = [tk.IntVar(value=50), tk.IntVar(value=1700), tk.IntVar(value=400), tk.IntVar(value=100)]
        self.title_size = tk.IntVar(value=48)
        self.caption_size = tk.IntVar(value=36)
        self.text_color = tk.StringVar(value="#FFFFFF")
        self.box_color = tk.StringVar(value="#000000")
        self.box_alpha = tk.DoubleVar(value=0.5)
        self.templates = load_templates()
        self.template_var = tk.StringVar(value="(Р±РµР· С€Р°Р±Р»РѕРЅР°)")
        self.template_var.trace_add("write", self.on_template_change)

        # --- Files frame ---
        files_frame = tk.LabelFrame(master, text="Р¤Р°Р№Р»С‹")
        files_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        tk.Button(files_frame, text="РџР°РїРєР° РІРёРґРµРѕ", command=self.select_video_dir).grid(row=0, column=0, sticky="w")
        tk.Button(files_frame, text="РџР°РїРєР° РјСѓР·С‹РєРё", command=self.select_music_dir).grid(row=0, column=1, sticky="w")
        tk.Button(files_frame, text="Р¤Р°Р№Р» Р·Р°РіРѕР»РѕРІРєРѕРІ", command=self.select_titles_file).grid(row=1, column=0, sticky="w")
        tk.Button(files_frame, text="РЁСЂРёС„С‚", command=self.select_title_font).grid(row=1, column=1, sticky="w")

        # --- Mode frame ---
        mode_frame = tk.LabelFrame(master, text="Р РµР¶РёРј")
        mode_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        tk.Radiobutton(mode_frame, text="Р“РѕС‚РѕРІС‹Рµ Р·Р°РіРѕР»РѕРІРєРё", variable=self.mode, value="titles").grid(row=0, column=0, sticky="w")
        tk.Radiobutton(mode_frame, text="РўРµРјС‹ РґР»СЏ РіРµРЅРµСЂР°С†РёРё", variable=self.mode, value="topics").grid(row=0, column=1, sticky="w")
        self.topics_text = tk.Text(mode_frame, height=5, width=40)
        self.topics_text.grid(row=1, column=0, columnspan=2, padx=5, pady=5)
        tk.Label(mode_frame, text="РљРѕР»РёС‡РµСЃС‚РІРѕ СЂРѕР»РёРєРѕРІ").grid(row=2, column=0, sticky="w")
        tk.Entry(mode_frame, textvariable=self.count, width=5).grid(row=2, column=1, sticky="w")

        # --- Position frame ---
        pos_frame = tk.LabelFrame(master, text="РџРѕР·РёС†РёРё")
        pos_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nw")
        tk.Label(pos_frame, text="РњР°СЃРєР° Р·Р°РіРѕР»РѕРІРєР° x,y,w,h").grid(row=0, column=0, columnspan=4, sticky="w")
        for i in range(4):
            tk.Entry(pos_frame, textvariable=self.mask_vars[i], width=5).grid(row=1, column=i)
        tk.Label(pos_frame, text="РњР°СЃРєР° РїРѕРґРїРёСЃРё x,y,w,h").grid(row=2, column=0, columnspan=4, sticky="w")
        for i in range(4):
            tk.Entry(pos_frame, textvariable=self.caption_mask_vars[i], width=5).grid(row=3, column=i)
        self.template_menu = tk.OptionMenu(
            pos_frame, self.template_var, "(Р±РµР· С€Р°Р±Р»РѕРЅР°)", *self.templates.keys()
        )
        self.template_menu.grid(row=4, column=0, columnspan=4, sticky="ew", pady=2)
        tk.Button(pos_frame, text="РЎРѕС…СЂР°РЅРёС‚СЊ С€Р°Р±Р»РѕРЅ", command=self.save_template).grid(
            row=5, column=0, columnspan=4, sticky="ew"
        )

        # --- Format frame ---
        fmt_frame = tk.LabelFrame(master, text="Р¤РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµ")
        fmt_frame.grid(row=2, column=1, padx=5, pady=5, sticky="ne")
        tk.Label(fmt_frame, text="Р Р°Р·РјРµСЂ Р·Р°РіРѕР»РѕРІРєР°").grid(row=0, column=0, sticky="w")
        tk.Entry(fmt_frame, textvariable=self.title_size, width=5).grid(row=0, column=1)
        tk.Label(fmt_frame, text="Р Р°Р·РјРµСЂ РїРѕРґРїРёСЃРё").grid(row=1, column=0, sticky="w")
        tk.Entry(fmt_frame, textvariable=self.caption_size, width=5).grid(row=1, column=1)
        tk.Button(fmt_frame, text="Р¦РІРµС‚ С‚РµРєСЃС‚Р°", command=self.select_text_color).grid(row=2, column=0, sticky="w")
        tk.Button(fmt_frame, text="Р¦РІРµС‚ РїРѕРґР»РѕР¶РєРё", command=self.select_box_color).grid(row=2, column=1, sticky="w")
        tk.Label(fmt_frame, text="РџСЂРѕР·СЂР°С‡РЅРѕСЃС‚СЊ РїРѕРґР»РѕР¶РєРё").grid(row=3, column=0, sticky="w")
        tk.Entry(fmt_frame, textvariable=self.box_alpha, width=5).grid(row=3, column=1)

        # --- Music frame ---
        music_frame = tk.LabelFrame(master, text="РњСѓР·С‹РєР°")
        music_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        tk.Radiobutton(music_frame, text="РЎР»СѓС‡Р°Р№РЅР°СЏ", variable=self.music_mode, value="random").grid(row=0, column=0, sticky="w")
        tk.Radiobutton(music_frame, text="РЈРјРЅС‹Р№ РїРѕРґР±РѕСЂ (Р·Р°РіР»СѓС€РєР°)", variable=self.music_mode, value="smart").grid(row=0, column=1, sticky="w")

        # --- Actions ---
        action_frame = tk.Frame(master)
        action_frame.grid(row=4, column=0, columnspan=2, pady=5)
        tk.Button(action_frame, text="РќР°СЃС‚СЂРѕРёС‚СЊ РјР°СЃРєСѓ", command=self.open_mask_editor).grid(row=0, column=0, padx=5)
        tk.Button(action_frame, text="Р“РµРЅРµСЂРёСЂРѕРІР°С‚СЊ", command=self.generate).grid(row=0, column=1, padx=5)

        self.preview_label = tk.Label(master)
        self.preview_label.grid(row=5, column=0, columnspan=2, pady=10)

    # --- UI callbacks ------------------------------------------------------
    def select_video_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.video_dir = path

    def select_music_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.music_dir = path

    def select_titles_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if path:
            self.titles_file = path

    def select_title_font(self):
        path = filedialog.askopenfilename(filetypes=[("Fonts", "*.ttf;*.otf")])
        if path:
            self.font_title_path = path
            self.font_caption_path = path

    def select_text_color(self):
        color = colorchooser.askcolor(initialcolor=self.text_color.get())[1]
        if color:
            self.text_color.set(color)

    def select_box_color(self):
        color = colorchooser.askcolor(initialcolor=self.box_color.get())[1]
        if color:
            self.box_color.set(color)

    def open_mask_editor(self):
        if not self.video_dir or not self.font_title_path:
            messagebox.showerror("РћС€РёР±РєР°", "Р’С‹Р±РµСЂРёС‚Рµ РїР°РїРєСѓ СЃ РІРёРґРµРѕ Рё С€СЂРёС„С‚")
            return
        videos = sorted(
            [f for f in os.listdir(self.video_dir) if f.lower().endswith((".mp4", ".mov", ".avi"))]
        )
        if not videos:
            messagebox.showerror("РћС€РёР±РєР°", "Р’ РїР°РїРєРµ РЅРµС‚ РІРёРґРµРѕ")
            return
        first_video = os.path.join(self.video_dir, videos[0])
        frame_path = "preview_frame.png"
        filter_str = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black"
        )
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                first_video,
                "-vf",
                filter_str,
                "-vframes",
                "1",
                frame_path,
            ],
            check=True,
        )
        img = Image.open(frame_path)
        mask = tuple(var.get() for var in self.mask_vars)
        caption_mask = tuple(var.get() for var in self.caption_mask_vars)
        MaskEditor(
            self.master,
            img,
            mask,
            caption_mask,
            self.font_title_path,
            self.font_caption_path,
            self.title_size.get(),
            self.caption_size.get(),
            self.text_color.get(),
            self.box_color.get(),
            float(self.box_alpha.get()),
            self.on_mask_applied,
        )

    def on_mask_applied(self, mask, caption_mask, preview_img):
        for var, val in zip(self.mask_vars, mask):
            var.set(val)
        for var, val in zip(self.caption_mask_vars, caption_mask):
            var.set(val)
        preview = preview_img.resize((270, 480))
        self.preview_img = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=self.preview_img)

    def on_template_change(self, *_):
        name = self.template_var.get()
        tpl = self.templates.get(name)
        if not tpl:
            return
        for var, val in zip(self.mask_vars, tpl.get("title", [])):
            var.set(val)
        for var, val in zip(self.caption_mask_vars, tpl.get("caption", [])):
            var.set(val)

    def save_template(self):
        name = simpledialog.askstring("РРјСЏ С€Р°Р±Р»РѕРЅР°", "Р’РІРµРґРёС‚Рµ РёРјСЏ С€Р°Р±Р»РѕРЅР°")
        if not name:
            return
        tpl = {
            "title": [var.get() for var in self.mask_vars],
            "caption": [var.get() for var in self.caption_mask_vars],
        }
        self.templates[name] = tpl
        save_templates(self.templates)
        menu = self.template_menu["menu"]
        menu.add_command(label=name, command=tk._setit(self.template_var, name))
        self.template_var.set(name)

    def generate(self):
        if not all([self.video_dir, self.music_dir, self.font_title_path]):
            messagebox.showerror("РћС€РёР±РєР°", "Р—Р°РїРѕР»РЅРёС‚Рµ РІСЃРµ РЅР°СЃС‚СЂРѕР№РєРё")
            return
        videos = sorted(
            [
                os.path.join(self.video_dir, f)
                for f in os.listdir(self.video_dir)
                if f.lower().endswith((".mp4", ".mov", ".avi"))
            ]
        )
        if not videos:
            messagebox.showerror("РћС€РёР±РєР°", "Р’ РїР°РїРєРµ РЅРµС‚ РІРёРґРµРѕ")
            return
        os.makedirs("output", exist_ok=True)
        mask = tuple(var.get() for var in self.mask_vars)
        caption_mask = tuple(var.get() for var in self.caption_mask_vars)
        tasks: list[tuple[str, str]] = []
        if self.mode.get() == "titles":
            if not self.titles_file:
                messagebox.showerror("РћС€РёР±РєР°", "Р’С‹Р±РµСЂРёС‚Рµ С„Р°Р№Р» СЃ Р·Р°РіРѕР»РѕРІРєР°РјРё")
                return
            with open(self.titles_file, "r", encoding="utf-8") as f:
                titles = [line.strip() for line in f if line.strip()]
            random.shuffle(titles)
            titles = titles[: self.count.get()]
            for chunk in chunks(titles, 5):
                descs = generate_descriptions_batch(chunk)
                tasks.extend(zip(chunk, descs))
        else:
            topics = [
                line.strip()
                for line in self.topics_text.get("1.0", tk.END).splitlines()
                if line.strip()
            ][: self.count.get()]
            for chunk in chunks(topics, 5):
                pairs = generate_titles_descriptions_batch(chunk)
                tasks.extend(pairs)

        tasks = tasks[: self.count.get()]

        rows = []
        video_cycle = cycle(videos)
        for idx, ((title, desc), video_path) in enumerate(zip(tasks, video_cycle), 1):
            music = pick_music(self.music_dir, self.music_mode.get())
            out_video = os.path.join("output", f"reel_{idx}.mp4")
            try:
                process_video(
                    video_path,
                    music,
                    out_video,
                    title,
                    desc,
                    mask,
                    caption_mask,
                    self.font_title_path,
                    self.font_caption_path,
                    self.title_size.get(),
                    self.caption_size.get(),
                    self.text_color.get(),
                    self.box_color.get(),
                    float(self.box_alpha.get()),
                )
            except Exception as e:
                messagebox.showerror("РћС€РёР±РєР°", str(e))
                return
            rows.append({"filename": os.path.basename(out_video), "description": desc})

        with open(
            os.path.join("output", "results.csv"),
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["filename", "description"])
            for row in rows:
                writer.writerow([row["filename"], row["description"]])

        messagebox.showinfo("Р“РѕС‚РѕРІРѕ", "Р“РµРЅРµСЂР°С†РёСЏ Р·Р°РІРµСЂС€РµРЅР°")

# ---- main -----------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = ReelsGeneratorApp(root)
    root.mainloop()


