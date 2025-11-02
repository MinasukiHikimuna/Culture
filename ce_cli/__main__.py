"""Allow running ce_cli as a module with python -m ce_cli."""

from ce_cli.cli import app

if __name__ == "__main__":
    app()
