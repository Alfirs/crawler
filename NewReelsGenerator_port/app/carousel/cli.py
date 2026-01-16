import argparse
from pathlib import Path
import json
from app.carousel.core import render_carousel

def main():
    parser = argparse.ArgumentParser(description="Generate carousel slides from job.json")
    parser.add_argument("--job", required=True, help="Path to job.json")
    parser.add_argument("--out", default="output", help="Output folder")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--username", default=None, help="Override username")
    args = parser.parse_args()

    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[CLI] generating carousel...")
    result_path = render_carousel(job, out_dir, seed=args.seed, username_override=args.username)
    print("[CLI] done ->", result_path)

if __name__ == "__main__":
    main()
