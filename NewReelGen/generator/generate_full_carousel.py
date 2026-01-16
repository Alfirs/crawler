from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Callable, List, Optional

from dotenv import load_dotenv
from openai import APIError, InternalServerError, OpenAI, RateLimitError

PRIMARY_SIZE = "1024x1024"
FALLBACK_SIZE = "1024x1792"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate minimalist Instagram carousel slides via gpt-image-1."
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="РРґРµРё РґР»СЏ РєР°СЂСѓСЃРµР»Рё",
        help="РўРµРјР° РєР°СЂСѓСЃРµР»Рё (РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РІ РїРѕРґСЃРєР°Р·РєРµ).",
    )
    parser.add_argument(
        "--slides",
        type=int,
        default=3,
        help="РљРѕР»РёС‡РµСЃС‚РІРѕ СЃР»Р°Р№РґРѕРІ (1..20).",
    )
    parser.add_argument(
        "--username",
        type=str,
        default="@brand",
        help="Р’РѕРґСЏРЅРѕР№ Р·РЅР°Рє (1..32 СЃРёРјРІРѕР»Р°).",
    )
    parser.add_argument(
        "--style_seed",
        type=int,
        default=None,
        help="РќРµРѕР±СЏР·Р°С‚РµР»СЊРЅС‹Р№ seed РґР»СЏ РµРґРёРЅРѕРѕР±СЂР°Р·РЅРѕРіРѕ СЃС‚РёР»СЏ.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=2,
        help="РљРѕР»РёС‡РµСЃС‚РІРѕ РѕРґРЅРѕРІСЂРµРјРµРЅРЅС‹С… Р·Р°РїСЂРѕСЃРѕРІ (1..5).",
    )
    return parser.parse_args()


def safe(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.replace('"', "'").strip()


def make_prompt(
    index: int,
    total: int,
    topic: str,
    username: str,
    style_seed: Optional[int] = None,
) -> str:
    topic_clean = safe(topic)
    username_clean = safe(username)
    role = "first" if index == 1 else ("last" if index == total else "middle")
    i_minus_one = max(1, index - 1)
    seed_clause = ""
    if style_seed is not None:
        seed_clause = (
            "CONSISTENCY:\n"
            f'- Keep overall style coherent across slides using this style seed hint: "{style_seed}"\n'
            "- Keep typography scale, margins, and color usage consistent across all slides.\n"
        )

    prompt = (
        f"You are a professional graphic designer.\n"
        f"Create an Instagram slide (portrait {PRIMARY_SIZE}) in clean minimalist style.\n\n"
        f"THEME (in Russian): '{topic_clean}'\n"
        f"SLIDE: {index} of {total} (role: {role})\n\n"
        "CONTENT RULES:\n"
        "- Language inside the image: Russian only.\n"
        "- Max 3–4 short lines of text. Avoid word hyphenation and broken words.\n"
        "- High readability: large bold sans-serif, high contrast, generous margins (10–12%).\n"
        f"- Add a small watermark in the top-left corner: '{username_clean}' (opacity 60-70%, padding ~24px, color #707070). Do not overlap the main title.\n\n"
        "LAYOUT & STYLE:\n"
        "- Very light background (white or light grey), soft subtle shadows.\n"
        "- Exactly one green accent element on every slide (thin line or simple geometric mark), color #2f6f4a.\n"
        "- No heavy gradients (>5%). No icons, stickers, emojis, logos, people or photos.\n"
        "- Keep typography scale and spacing consistent across slides.\n\n"
        "ROLE-SPECIFIC INSTRUCTIONS:\n"
        "- If role = \"first\":\n"
        f"  * Show the main title: \u201C{topic_clean}\u201D.\n"
        "  * Add a short subtitle/benefit line (e.g. why it matters).\n"
        "  * Do NOT repeat the title on other slides.\n"
        "- If role = \"middle\":\n"
        f"  * Start with: \u201CОшибка {i_minus_one} — …\u201D (use a short, crisp phrase).\n"
        "  * Keep text ≤ 4 lines, no long paragraphs.\n"
        "- If role = \"last\":\n"
        "  * Provide a concise conclusion or CTA (1–3 short lines), e.g. “Подведём итог / Избегайте X / Делайте Y”.\n"
        "  * Do not repeat the full title.\n\n"
        "OUTPUT:\n"
        f"- Final image {PRIMARY_SIZE} portrait.\n"
        "- All text must be rendered into the image (no external overlay).\n"
    )

    if role == "middle":
        prompt += f"\nThis slide must start with \u201CОшибка {i_minus_one} — …\u201D and stay within four short lines."
    elif role == "first":
        prompt += "\nThis slide must combine the hero title with a single supporting subtitle."
    else:
        prompt += "\nThis slide must deliver a concise conclusion or CTA without repeating the full title."

    if seed_clause:
        prompt += "\n\n" + seed_clause

    return prompt.strip()


def save_image(b64_data: str, path: str) -> None:
    Path(path).write_bytes(base64.b64decode(b64_data))


def with_retry(
    fn: Callable[[], any],
    attempts: int = 3,
    base: float = 1.6,
) -> any:
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except (RateLimitError, InternalServerError, APIError) as exc:
            if attempt == attempts:
                raise
            delay = base ** attempt
            print(f"[retry] {exc.__class__.__name__}: {exc}. Retry in {delay:.1f}s.")
            time.sleep(delay)
        except Exception:
            raise
    raise RuntimeError("with_retry exhausted attempts without returning.")


def generate_slide(
    index: int,
    total: int,
    topic: str,
    username: str,
    style_seed: Optional[int],
    client: OpenAI,
    output_dir: Path,
) -> dict:
    prompt = make_prompt(index, total, topic, username, style_seed)
    print(f"[{index}/{total}] prompt -> gpt-image-1")

    def _call(size: str):
        return client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size=size,
            n=1,
        )

    used_size = PRIMARY_SIZE

    try:
        response = with_retry(lambda: _call(PRIMARY_SIZE))
    except Exception as exc:
        error_text = str(exc).lower()
        if "param" in error_text and "size" in error_text or "internal_error" in error_text:
            print(f"WARNING: NeuroAPI rejected size {PRIMARY_SIZE}, trying {FALLBACK_SIZE}")
            response = with_retry(lambda: _call(FALLBACK_SIZE))
            used_size = FALLBACK_SIZE
        else:
            raise

    b64_image = response.data[0].b64_json
    output_path = output_dir / f"slide_{index}.jpg"
    save_image(b64_image, str(output_path))
    print(f"[{index}/{total}] saved: {output_path}")
    return {
        "index": index,
        "path": str(output_path),
        "topic": topic,
        "username": username,
        "size": used_size,
        "model": "gpt-image-1",
    }


def run_parallel(jobs: List[Callable[[], dict]], parallel: int) -> List[dict]:
    results: List[Optional[dict]] = [None] * len(jobs)
    effective_parallel = max(1, min(parallel, len(jobs)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=effective_parallel) as executor:
        future_to_idx = {executor.submit(jobs[idx]): idx for idx in range(len(jobs))}
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                executor.shutdown(cancel_futures=True)
                raise
    return [item for item in results if item is not None]


def _validate_inputs(slides: int, username: str, parallel: int) -> None:
    if not (1 <= slides <= 20):
        raise ValueError("--slides must be between 1 and 20.")
    if not (1 <= len(username) <= 32):
        raise ValueError("--username length must be between 1 and 32 characters.")
    if not (1 <= parallel <= 5):
        raise ValueError("--parallel must be between 1 and 5.")


def validate_args(args: argparse.Namespace) -> None:
    try:
        _validate_inputs(args.slides, args.username, args.parallel)
    except ValueError as exc:
        sys.exit(f"ERROR: {exc}")


def _prepare_client() -> OpenAI:
    load_dotenv()
    neuro_key = os.getenv("NEUROAPI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    api_key = neuro_key or openai_key
    if not api_key:
        raise RuntimeError("вќЊ No API key found (NEUROAPI_API_KEY or OPENAI_API_KEY)")

    if neuro_key:
        print("рџ”— Using NeuroAPI endpoint")
        client = OpenAI(
            base_url="https://neuroapi.host/v1",
            api_key=api_key,
        )
    else:
        print("рџ”— Using OpenAI endpoint")
        client = OpenAI(api_key=api_key)

    return client.with_options(timeout=60)


def generate_slides(
    topic: str,
    slides: int,
    username: str,
    style_seed: Optional[int] = None,
    parallel: int = 2,
) -> List[dict]:
    """
    Generate slides via gpt-image-1 and return the same metadata structure as the CLI.
    """
    _validate_inputs(slides, username, parallel)
    client = _prepare_client()
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs: List[Callable[[], dict]] = []
    for index in range(1, slides + 1):
        jobs.append(
            lambda idx=index: generate_slide(
                idx,
                slides,
                topic,
                username,
                style_seed,
                client,
                output_dir,
            )
        )

    metadata = run_parallel(jobs, parallel)
    metadata.sort(key=lambda item: item["index"])
    return metadata


def main() -> None:
    args = parse_args()
    validate_args(args)
    try:
        metadata = generate_slides(
            topic=args.topic,
            slides=args.slides,
            username=args.username,
            style_seed=args.style_seed,
            parallel=args.parallel,
        )
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as exc:
        print("[error] Generation failed:", exc)
        traceback.print_exc()
        sys.exit(1)

    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)

# РџСЂРёРјРµСЂС‹:
# python generate_full_carousel.py --topic "10 РѕС€РёР±РѕРє РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»РµР№" --slides 3 --username "@anton"
# python generate_full_carousel.py --topic "10 РѕС€РёР±РѕРє РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»РµР№" --slides 3 --username "@anton" --style_seed 42 --parallel 2

