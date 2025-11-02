"""Formatting utilities for sync command output."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from culture_cli.utils.sync_engine import SyncPlan, SyncResult


console = Console()


def display_sync_plan(plan: SyncPlan, dry_run: bool = True) -> None:
    """Display the sync plan with rich formatting.

    Args:
        plan: SyncPlan to display
        dry_run: Whether this is a dry run (affects header message)
    """
    # Header panel
    mode_text = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]APPLYING CHANGES[/green]"
    header = (
        f"[bold cyan]Sync Plan: Culture Extractor → Stashapp ({mode_text})[/bold cyan]\n\n"
        f"[green]CE Release:[/green]   {plan.ce_uuid}\n"
        f"[green]CE Name:[/green]      {plan.ce_release_name}\n"
        f"[green]Stashapp Scene:[/green] #{plan.stashapp_id}\n"
        f"[green]Stash Title:[/green]   {plan.stashapp_title}"
    )
    console.print(Panel(header, border_style="cyan"))
    console.print()

    # Field changes table
    field_table = _format_field_diff_table(plan.field_diffs)
    console.print(field_table)
    console.print()

    # Performer changes table
    if plan.performer_diffs:
        performer_table = _format_performer_diff_table(plan.performer_diffs)
        console.print(performer_table)
        console.print()

    # Summary
    _format_summary(plan, dry_run)


def _format_field_diff_table(field_diffs: list) -> Table:
    """Format field differences as a table.

    Args:
        field_diffs: List of FieldDiff objects

    Returns:
        Rich Table object
    """
    table = Table(title="Field Changes", show_header=True, header_style="bold magenta", expand=False)
    table.add_column("Field", style="cyan", width=15)
    table.add_column("Action", style="yellow", width=12)
    table.add_column("Details", style="white")

    for diff in field_diffs:
        if diff.action == "no_change":
            action_display = "[green]✓ NO CHANGE[/green]"
            style = "dim"
        elif diff.action == "update":
            action_display = "[blue]→ UPDATE[/blue]"
            style = "white"
        elif diff.action == "add":
            action_display = "[cyan]+ ADD[/cyan]"
            style = "white"
        elif diff.action == "warning":
            action_display = "[yellow]⚠ WARNING[/yellow]"
            style = "yellow"
        else:
            action_display = diff.action
            style = "white"

        # Format the message based on action
        if diff.action == "no_change":
            message = diff.message if diff.field_name == "url" else f"[dim]{diff.current_value or 'N/A'}[/dim]"
        else:
            message = diff.message

        table.add_row(diff.field_name.title(), action_display, message, style=style)

    return table


def _format_performer_diff_table(performer_diffs: list) -> Table:
    """Format performer differences as a table.

    Args:
        performer_diffs: List of PerformerDiff objects

    Returns:
        Rich Table object
    """
    table = Table(title="Performer Matching", show_header=True, header_style="bold magenta", expand=False)
    table.add_column("CE Performer", style="cyan", width=25)
    table.add_column("Status", style="yellow", width=15)
    table.add_column("Stashapp Match", style="white")

    for diff in performer_diffs:
        ce_performer_display = f"{diff.ce_name}\n[dim]{diff.ce_uuid[:8]}...[/dim]"

        if diff.status == "matched":
            status_display = "[green]✓ MATCHED[/green]"
            stashapp_match = f"#{diff.stashapp_id} - {diff.stashapp_name}"
            style = "white"
        elif diff.status == "not_found":
            status_display = "[yellow]⚠ NOT FOUND[/yellow]"
            stashapp_match = "[dim]No matching performer in Stashapp[/dim]"
            style = "yellow"
        else:
            status_display = diff.status
            stashapp_match = "N/A"
            style = "white"

        table.add_row(ce_performer_display, status_display, stashapp_match, style=style)

    return table


def _format_summary(plan: SyncPlan, dry_run: bool) -> None:
    """Format and display the summary.

    Args:
        plan: SyncPlan to summarize
        dry_run: Whether this is a dry run
    """
    # Count changes
    field_changes = sum(1 for diff in plan.field_diffs if diff.action in ["update", "add"])
    performers_matched = sum(1 for diff in plan.performer_diffs if diff.status == "matched")
    performers_not_found = sum(1 for diff in plan.performer_diffs if diff.status == "not_found")

    # Display warnings if any
    if plan.has_warnings:
        console.print(
            f"[yellow]⚠  {performers_not_found} performer(s) not matched - will be skipped[/yellow]"
        )

    # Display summary based on whether there are changes
    if plan.has_changes:
        if dry_run:
            console.print(
                f"[green]✓ Ready to sync {field_changes} field(s) and {performers_matched} performer(s)[/green]"
            )
            console.print()
            console.print("[cyan]Run with --apply to execute this sync.[/cyan]")
        else:
            console.print(f"[green]Syncing {field_changes} field(s) and {performers_matched} performer(s)...[/green]")
    else:
        console.print("[green]✓ No changes needed - data is already in sync[/green]")


def display_sync_result(result: SyncResult) -> None:
    """Display the result of applying a sync.

    Args:
        result: SyncResult to display
    """
    console.print()

    if result.success:
        console.print("[bold green]✓ Sync completed successfully![/bold green]")
        console.print()

        if result.fields_updated:
            console.print("[green]Updated fields:[/green]")
            for field in result.fields_updated:
                console.print(f"  [green]✓[/green] {field}")

        if result.performers_linked:
            console.print(f"[green]✓ Linked {result.performers_linked} performer(s)[/green]")

        console.print("[green]✓ Created bidirectional external ID link[/green]")

    else:
        console.print(f"[bold red]✗ Sync failed: {result.message}[/bold red]")
        if result.errors:
            console.print("\n[red]Errors:[/red]")
            for error in result.errors:
                console.print(f"  [red]✗[/red] {error}")


def print_error(message: str) -> None:
    """Print an error message.

    Args:
        message: Error message to display
    """
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Info message to display
    """
    console.print(f"[blue]ℹ[/blue] {message}")  # noqa: RUF001 - Intentional info icon


def print_success(message: str) -> None:
    """Print a success message.

    Args:
        message: Success message to display
    """
    console.print(f"[green]✓[/green] {message}")
