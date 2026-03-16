import sys


def main() -> None:
    task = " ".join(sys.argv[1:]).strip() or "cleanup"
    print(f"Maintenance task queued: {task}")


if __name__ == "__main__":
    main()
