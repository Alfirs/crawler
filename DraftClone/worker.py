def main() -> None:
    message = (
        "The background worker is no longer required.\n"
        "DraftClone now generates text-first carousels instantly and renders them inside the editor.\n"
        "You can remove any old Redis/RQ processes and use the FastAPI app directly."
    )
    print(message)


if __name__ == "__main__":
    main()
