from dotenv import load_dotenv

from dubber.interfaces.cli.commands import app

load_dotenv()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
