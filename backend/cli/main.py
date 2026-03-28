"""Insights IDE CLI — thin HTTP client wrapping the FastAPI backend."""

from __future__ import annotations

import json
import os
from typing import Annotated

import httpx
import typer
from rich import print_json
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="insights",
    help="Insights IDE command-line interface.",
    no_args_is_help=True,
)
pipeline_app = typer.Typer(help="Pipeline commands.", no_args_is_help=True)
block_app = typer.Typer(help="Block commands.", no_args_is_help=True)
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(block_app, name="block")

console = Console()
err_console = Console(stderr=True)

_DEFAULT_BASE_URL = "http://localhost:8000/api/v1"


def _base_url(ctx: typer.Context) -> str:
    """Resolve base URL from context, env var, or default."""
    obj = ctx.ensure_object(dict)
    if "api_url" in obj:
        return obj["api_url"].rstrip("/")
    return os.environ.get("INSIGHTS_API_URL", _DEFAULT_BASE_URL).rstrip("/")


def _get(url: str) -> dict | list:
    """GET request with graceful connection error handling."""
    try:
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        err_console.print(f"[red]Connection refused:[/red] could not reach {url}")
        raise typer.Exit(1) from None
    except httpx.HTTPStatusError as exc:
        err_console.print(f"[red]HTTP {exc.response.status_code}:[/red] {exc.response.text}")
        raise typer.Exit(1) from None
    except httpx.RequestError as exc:
        err_console.print(f"[red]Request error:[/red] {exc}")
        raise typer.Exit(1) from None


def _post(url: str, payload: dict | None = None) -> dict:
    """POST request with graceful connection error handling."""
    try:
        resp = httpx.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        err_console.print(f"[red]Connection refused:[/red] could not reach {url}")
        raise typer.Exit(1) from None
    except httpx.HTTPStatusError as exc:
        err_console.print(f"[red]HTTP {exc.response.status_code}:[/red] {exc.response.text}")
        raise typer.Exit(1) from None
    except httpx.RequestError as exc:
        err_console.print(f"[red]Request error:[/red] {exc}")
        raise typer.Exit(1) from None


# ---------------------------------------------------------------------------
# Global options callback
# ---------------------------------------------------------------------------


@app.callback()
def main(
    ctx: typer.Context,
    api_url: Annotated[
        str | None,
        typer.Option("--api-url", help="Override base API URL.", envvar="INSIGHTS_API_URL"),
    ] = None,
) -> None:
    """Insights IDE CLI."""
    ctx.ensure_object(dict)
    if api_url:
        ctx.obj["api_url"] = api_url


# ---------------------------------------------------------------------------
# pipeline commands
# ---------------------------------------------------------------------------


@pipeline_app.command("list")
def pipeline_list(ctx: typer.Context) -> None:
    """List all saved pipelines."""
    base = _base_url(ctx)
    pipelines = _get(f"{base}/pipelines")
    assert isinstance(pipelines, list)

    if not pipelines:
        console.print("[yellow]No pipelines found.[/yellow]")
        return

    table = Table(title="Pipelines", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Nodes", justify="right")
    table.add_column("Created At")

    for p in pipelines:
        nodes = str(len(p.get("nodes", [])))
        table.add_row(
            str(p.get("pipeline_id", "")),
            p.get("name", ""),
            nodes,
            str(p.get("created_at", "")),
        )

    console.print(table)


@pipeline_app.command("show")
def pipeline_show(
    ctx: typer.Context,
    pipeline_id: Annotated[str, typer.Argument(help="Pipeline ID")],
) -> None:
    """Show a pipeline as JSON."""
    base = _base_url(ctx)
    data = _get(f"{base}/pipelines/{pipeline_id}")
    print_json(json.dumps(data))


@pipeline_app.command("run")
def pipeline_run(
    ctx: typer.Context,
    pipeline_id: Annotated[str, typer.Argument(help="Pipeline ID to execute")],
) -> None:
    """Trigger a pipeline run and display the run_id."""
    base = _base_url(ctx)
    result = _post(f"{base}/execution/{pipeline_id}/run")
    console.print(f"[green]Run started:[/green] {result['run_id']}  status={result['status']}")


@pipeline_app.command("status")
def pipeline_status(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Run ID returned by 'pipeline run'")],
) -> None:
    """Show run status with per-node breakdown."""
    base = _base_url(ctx)
    data = _get(f"{base}/execution/{run_id}/status")
    assert isinstance(data, dict)

    status_colour = {
        "pending": "yellow",
        "running": "blue",
        "completed": "green",
        "failed": "red",
        "suspended": "magenta",
    }
    run_status = data.get("status", "unknown")
    colour = status_colour.get(run_status, "white")

    console.print(f"Run ID   : [cyan]{data.get('run_id')}[/cyan]")
    console.print(f"Pipeline : {data.get('pipeline_id')}")
    console.print(f"Status   : [{colour}]{run_status}[/{colour}]")
    if data.get("current_node_id"):
        console.print(f"Current  : {data['current_node_id']}")
    if data.get("error"):
        console.print(f"[red]Error    : {data['error']}[/red]")

    node_statuses: list[dict] = data.get("node_statuses", [])
    if node_statuses:
        table = Table(title="Node Statuses", show_lines=False)
        table.add_column("Node ID", style="cyan")
        table.add_column("Status")
        table.add_column("Started At")
        table.add_column("Completed At")
        table.add_column("Error")

        for ns in node_statuses:
            ns_status = ns.get("status", "")
            ns_colour = status_colour.get(ns_status, "white")
            table.add_row(
                ns.get("node_id", ""),
                f"[{ns_colour}]{ns_status}[/{ns_colour}]",
                str(ns.get("started_at") or ""),
                str(ns.get("completed_at") or ""),
                str(ns.get("error") or ""),
            )
        console.print(table)


# ---------------------------------------------------------------------------
# block commands
# ---------------------------------------------------------------------------


@block_app.command("list")
def block_list(
    ctx: typer.Context,
    type: Annotated[
        str | None,
        typer.Option("--type", help="Filter blocks by type (e.g. transform, source)"),
    ] = None,
) -> None:
    """List all registered blocks."""
    base = _base_url(ctx)
    url = f"{base}/blocks"
    if type:
        url += f"?type={type}"

    blocks = _get(url)
    assert isinstance(blocks, list)

    if not blocks:
        console.print("[yellow]No blocks found.[/yellow]")
        return

    table = Table(title="Blocks", show_lines=False)
    table.add_column("Type", style="cyan")
    table.add_column("Implementation", style="bold")
    table.add_column("Description")

    for b in blocks:
        table.add_row(
            b.get("block_type", ""),
            b.get("implementation", ""),
            b.get("description", ""),
        )

    console.print(table)


@block_app.command("inspect")
def block_inspect(
    ctx: typer.Context,
    block_type: Annotated[str, typer.Argument(help="Block type (e.g. transform)")],
    implementation: Annotated[str, typer.Argument(help="Block implementation (e.g. csv_source)")],
) -> None:
    """Show config schema and I/O types for a block."""
    base = _base_url(ctx)
    data = _get(f"{base}/blocks/{block_type}/{implementation}")
    assert isinstance(data, dict)

    console.print(f"[bold]{data.get('block_type')} / {data.get('implementation')}[/bold]")
    if data.get("description"):
        console.print(f"Description: {data['description']}")

    console.print("\n[bold]Config Schema:[/bold]")
    print_json(json.dumps(data.get("config_schema", {})))

    console.print("\n[bold]Input Schemas:[/bold]")
    print_json(json.dumps(data.get("input_schemas", {})))

    console.print("\n[bold]Output Schemas:[/bold]")
    print_json(json.dumps(data.get("output_schemas", {})))


if __name__ == "__main__":
    app()
