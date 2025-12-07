"""Sync command for synchronizing data between systems."""

import os
import traceback
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from culture_cli.utils.formatters import display_sync_plan, display_sync_result, print_error, print_info
from culture_cli.utils.sync_engine import SyncEngine
from libraries.client_culture_extractor import ClientCultureExtractor
from libraries.client_stashapp import StashAppClient


# Repository root for .env file location
_REPO_ROOT = Path(__file__).parent.parent.parent

# Load environment variables from repository root
env_path = _REPO_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Try default locations


def sync_scene(
    from_system: Annotated[str, typer.Option("--from", help="Source system (culture-extractor)")],
    from_id: Annotated[str, typer.Option("--from-id", help="Source ID (CE UUID)")],
    to_system: Annotated[str, typer.Option("--to", help="Target system (stashapp)")],
    to_id: Annotated[int, typer.Option("--to-id", help="Target ID (Stashapp scene ID)")],
    apply: Annotated[bool, typer.Option("--apply", help="Apply changes (default is dry-run)")] = False,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Overwrite existing values instead of merging")
    ] = False,
) -> None:
    """Synchronize metadata from Culture Extractor to Stashapp.

    By default, this command runs in dry-run mode and shows what changes would be made
    without actually applying them. Use --apply to execute the sync.

    The sync will merge new data with existing data (e.g., adding new performers/tags to
    existing ones). Use --overwrite to replace existing data completely instead.

    Examples:
        # Dry run (show changes without applying)
        culture sync --from culture-extractor --from-id <UUID> --to stashapp --to-id <ID>

        # Apply changes (merge with existing data)
        culture sync --from culture-extractor --from-id <UUID> --to stashapp --to-id <ID> --apply

        # Apply changes (overwrite existing data)
        culture sync --from culture-extractor --from-id <UUID> --to stashapp --to-id <ID> --apply --overwrite
    """
    try:
        # Validate systems
        _validate_systems(from_system, to_system)

        # Initialize sync engine
        sync_engine = _initialize_sync_engine()

        # Fetch data from both systems
        print_info(f"Fetching data from Culture Extractor (UUID: {from_id})...")
        try:
            ce_data = sync_engine.fetch_ce_data(from_id)
        except ValueError as e:
            print_error(str(e))
            raise typer.Exit(code=1) from e

        print_info(f"Fetching data from Stashapp (Scene ID: {to_id})...")
        try:
            stash_data = sync_engine.fetch_stashapp_data(to_id)
        except ValueError as e:
            print_error(str(e))
            raise typer.Exit(code=1) from e

        # Compute diff
        print_info("Computing differences...")
        sync_plan = sync_engine.compute_diff(ce_data, stash_data)

        # Display the plan
        print()
        display_sync_plan(sync_plan, dry_run=not apply)
        print()

        # Apply if requested
        if apply:
            if not sync_plan.has_changes:
                print_info("No changes to apply")
                raise typer.Exit(code=0)

            result = sync_engine.apply_sync(sync_plan, overwrite=overwrite)
            display_sync_result(result)

            if not result.success:
                raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        print(traceback.format_exc())
        raise typer.Exit(code=1) from e


def _validate_systems(from_system: str, to_system: str) -> None:
    """Validate source and target systems."""
    if from_system.lower() != "culture-extractor":
        print_error(f"Unsupported source system: {from_system}")
        print_info("Currently only 'culture-extractor' is supported as source")
        raise typer.Exit(code=1)

    if to_system.lower() != "stashapp":
        print_error(f"Unsupported target system: {to_system}")
        print_info("Currently only 'stashapp' is supported as target")
        raise typer.Exit(code=1)


def _get_ce_connection_string() -> str:
    """Build CE connection string from environment variables."""
    user = os.environ.get("CE_DB_USERNAME")
    pw = os.environ.get("CE_DB_PASSWORD")
    host = os.environ.get("CE_DB_HOST")
    port = os.environ.get("CE_DB_PORT")
    db = os.environ.get("CE_DB_NAME")

    missing = []
    if not user:
        missing.append("CE_DB_USERNAME")
    if not pw:
        missing.append("CE_DB_PASSWORD")
    if not host:
        missing.append("CE_DB_HOST")
    if not port:
        missing.append("CE_DB_PORT")
    if not db:
        missing.append("CE_DB_NAME")

    if missing:
        print_error(f"Missing required environment variables: {', '.join(missing)}")
        print_info(f"Please set them in .env file at: {_REPO_ROOT / '.env'}")
        raise typer.Exit(code=1)

    return f"dbname={db} user={user} password={pw} host={host} port={port}"


def _initialize_sync_engine() -> SyncEngine:
    """Initialize and return a configured SyncEngine."""
    ce_connection_string = _get_ce_connection_string()

    print_info("Connecting to Culture Extractor...")
    ce_client = ClientCultureExtractor(ce_connection_string)

    print_info("Connecting to Stashapp...")
    stash_client = StashAppClient()

    # Get metadata base path from environment (optional)
    metadata_base_path = os.environ.get("CE_METADATA_BASE_PATH")

    return SyncEngine(ce_client, stash_client, metadata_base_path)
