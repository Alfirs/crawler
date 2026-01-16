# app/services/nlp_utils.py
from __future__ import annotations
from collections import Counter
import re

try:
    from razdel import tokenize as _rz_tokenize
except Exception:
    _rz_tokenize = None  # razdel отсутствует, fallback используется

def _iter_tokens(text: str):
    if _rz_tokenize:
        for t in _rz_tokenize(text):
            yield t.text
    else:
        for m in re.finditer(r"[A-Za-zА-Яа-яЁё0-9\-]+", text, re.UNICODE):
            yield m.group(0)

MD_TOKENS_RE = re.compile(r"(\*\*|__|\[\[|\]\])")

def normalize_spaces(s: str) -> str:
    s = re.sub(r"([,;:.!?])([^\s])", r"\1 \2", s)
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def strip_markup(s: str) -> str:
    s = s.replace("[[", "").replace("]]", "")
    s = s.replace("**", "").replace("__", "")
    return normalize_spaces(s)

def apply_markup(title: str, bullets: list[str], keywords: list[str]|None=None) -> tuple[str, list[str]]:
    def mark_phrase(text: str, phrase: str, left="__", right="__"):
        words = [re.escape(w) for w in phrase.split()]
        pattern = r"(?i)\b" + r"\s+".join(words) + r"\b"
        return re.sub(pattern, lambda m: f"{left}{m.group(0)}{right}", text)
    def mark_word(text: str, word: str, left="[[", right="]]"):
        pattern = r"(?i)\b" + re.escape(word) + r"\b"
        return re.sub(pattern, lambda m: f"{left}{m.group(0)}{right}", text)

    title = normalize_spaces(title)
    bullets = [normalize_spaces(b) for b in bullets]
    if keywords:
        phrases = [k for k in keywords if len(k.split()) >= 2][:3]
        singles = [k for k in keywords if len(k.split()) == 1][:5]
        for ph in phrases:
            title = mark_phrase(title, ph)
            bullets = [mark_phrase(b, ph) for b in bullets]
        for w in singles:
            title = mark_word(title, w)
            bullets = [mark_word(b, w) for b in bullets]
    title = normalize_spaces(title)
    bullets = [normalize_spaces(b) for b in bullets]
    return title, bullets

STOP = set("""и в во на по для при из у от это этот эта эти же ли бы как но да не ни или либо чем чтобы тоже которые который куда где когда всего тут там вот уже ещё лишь без более если что кто где куда""".split())

def normalize_words(text: str) -> list[str]:
    tokens = [t.lower() for t in _iter_tokens(text)]
    tokens = [re.sub(r"[^а-яa-z0-9\-]+", "", t) for t in tokens]
    return [t for t in tokens if t and t not in STOP]

def top_keywords(slides: list[dict], k: int = 3) -> list[list[str]]:
    """
    Простая tf-idf приближалка:
    - реже в корпусе, но часто на слайде → высокая значимость
    - bi-gram'ы чуть повышаем
    """
    corpus = Counter()
    per_slide = []
    for s in slides:
        words = normalize_words(s.get("title","") + " " + " ".join(s.get("bullets", [])))
        per_slide.append(words)
        corpus.update(set(words))

    result = []
    for words in per_slide:
        scores = Counter()
        for i, w in enumerate(words):
            scores[w] += 1 / (1 + corpus[w])
            if i + 1 < len(words):
                bi = f"{w} {words[i+1]}"
                scores[bi] += 1.4 / (1 + corpus.get(words[i+1], 1))
        chosen: list[str] = []
        for term, _ in scores.most_common(12):
            if all(term not in c and c not in term for c in chosen):
                chosen.append(term)
            if len(chosen) >= k:
                break
        result.append(chosen)
    return result
