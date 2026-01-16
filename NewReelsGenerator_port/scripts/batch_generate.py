import argparse
from app.services.batch_generate import batch_generate


def main():
    parser = argparse.ArgumentParser(description="Batch generate carousels from a template")
    parser.add_argument("--template", required=True, help="Template name without extension")
    parser.add_argument("--topic", required=True, help="Topic or idea for carousel content")
    parser.add_argument("--count", type=int, default=5, help="Number of carousels to generate")
    args = parser.parse_args()

    batches = batch_generate(args.template, args.topic, args.count)
    for folder in batches:
        print(folder)


if __name__ == "__main__":
    main()
