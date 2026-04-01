"""Insights IDE CLI — thin HTTP client wrapping the FastAPI backend."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import httpx
import typer
from pydantic import ValidationError
from rich import print_json
from rich.console import Console
from rich.table import Table

from schemas.pipeline import PipelineSchema

app = typer.Typer(
    name="insights",
    help="Insights IDE command-line interface.",
    no_args_is_help=True,
)
pipeline_app = typer.Typer(help="Pipeline commands.", no_args_is_help=True)
block_app = typer.Typer(help="Block commands.", no_args_is_help=True)
run_app = typer.Typer(help="Run commands.", no_args_is_help=True)
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(block_app, name="block")
app.add_typer(run_app, name="run")

console = Console()
err_console = Console(stderr=True)

_DEFAULT_BASE_URL = "http://localhost:8000/api/v1"
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


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


@pipeline_app.command("validate")
def pipeline_validate(
    ctx: typer.Context,
    pipeline_file: Annotated[str, typer.Argument(help="Path to pipeline JSON file")],
) -> None:
    """Validate a local pipeline JSON file against the pipeline schema."""
    path = Path(pipeline_file)

    # Check file exists
    if not path.exists():
        err_console.print(f"[red]Error:[/red] File not found: {pipeline_file}")
        raise typer.Exit(1) from None

    # Try to load and parse JSON
    try:
        content = path.read_text()
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error:[/red] Invalid JSON: {exc}")
        raise typer.Exit(1) from None
    except OSError as exc:
        err_console.print(f"[red]Error:[/red] Could not read file: {exc}")
        raise typer.Exit(1) from None

    # Validate against PipelineSchema
    try:
        pipeline = PipelineSchema(**data)
        console.print(f"[green]✓[/green] Valid pipeline: {pipeline.name}")
        console.print(f"  Pipeline ID : {pipeline.pipeline_id}")
        console.print(f"  Version     : {pipeline.version}")
        console.print(f"  Nodes       : {len(pipeline.nodes)}")
        console.print(f"  Edges       : {len(pipeline.edges)}")
        if pipeline.loop_definitions:
            console.print(f"  Loops       : {len(pipeline.loop_definitions)}")
    except ValidationError as exc:
        err_console.print("[red]Validation errors:[/red]")
        for error in exc.errors():
            loc = " -> ".join(str(p) for p in error["loc"])
            err_console.print(f"  [yellow]{loc}:[/yellow] {error['msg']}")
        raise typer.Exit(1) from None


@pipeline_app.command("create")
def pipeline_create(
    ctx: typer.Context,
    from_template: Annotated[
        str | None,
        typer.Option(
            "--from-template",
            help="Template name to scaffold from (use --list-templates to see options)",
        ),
    ] = None,
    list_templates: Annotated[
        bool,
        typer.Option("--list-templates", help="List available templates"),
    ] = False,
    output_file: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output file path (default: <name>.json)"),
    ] = None,
) -> None:
    """Create a new pipeline from a built-in template."""
    # List templates mode
    if list_templates:
        if not _TEMPLATES_DIR.exists():
            err_console.print(f"[yellow]No templates directory found at {_TEMPLATES_DIR}[/yellow]")
            raise typer.Exit(1) from None

        template_files = sorted(_TEMPLATES_DIR.glob("*.json"))
        if not template_files:
            console.print("[yellow]No templates found.[/yellow]")
            return

        table = Table(title="Available Templates", show_lines=False)
        table.add_column("Template Name", style="cyan")
        table.add_column("Description")

        for tmpl_file in template_files:
            try:
                data = json.loads(tmpl_file.read_text())
                name = tmpl_file.stem
                desc = data.get("metadata", {}).get("description", "")
                table.add_row(name, desc[:60] + "..." if len(desc) > 60 else desc)
            except (json.JSONDecodeError, OSError):
                # Skip invalid templates
                continue

        console.print(table)
        console.print("\n[bold]Usage:[/bold] insights pipeline create --from-template <name>")
        return

    # Create from template mode
    if not from_template:
        err_console.print(
            "[red]Error:[/red] --from-template is required (or use --list-templates to see options)"
        )
        raise typer.Exit(1) from None

    # Resolve template path
    template_path = _TEMPLATES_DIR / f"{from_template}.json"
    if not template_path.exists():
        err_console.print(f"[red]Error:[/red] Template not found: {from_template}")
        console.print("[yellow]Hint:[/yellow] Use --list-templates to see available templates")
        raise typer.Exit(1) from None

    # Load template
    try:
        content = template_path.read_text()
        data = json.loads(content)
        pipeline = PipelineSchema(**data)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error:[/red] Invalid template JSON: {exc}")
        raise typer.Exit(1) from None
    except OSError as exc:
        err_console.print(f"[red]Error:[/red] Could not read template: {exc}")
        raise typer.Exit(1) from None
    except ValidationError as exc:
        err_console.print("[red]Error:[/red] Template failed validation:")
        for error in exc.errors():
            loc = " -> ".join(str(p) for p in error["loc"])
            err_console.print(f"  [yellow]{loc}:[/yellow] {error['msg']}")
        raise typer.Exit(1) from None

    # Determine output file
    if output_file is None:
        output_file = f"{pipeline.name.replace(' ', '_').lower()}.json"

    output_path = Path(output_file)

    # Check if output file already exists
    if output_path.exists():
        err_console.print(f"[red]Error:[/red] Output file already exists: {output_file}")
        err_console.print("[yellow]Hint:[/yellow] Use --output to specify a different path")
        raise typer.Exit(1) from None

    # Write pipeline to file
    try:
        output_path.write_text(json.dumps(data, indent=2))
        console.print(f"[green]✓[/green] Pipeline created: {output_file}")
        console.print(f"  Name    : {pipeline.name}")
        console.print(f"  Nodes   : {len(pipeline.nodes)}")
        console.print(f"  Edges   : {len(pipeline.edges)}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  1. Review: cat {output_file}")
        console.print(
            f"  2. Upload: insights pipeline create-from-api {output_file} (if implemented)"
        )
        console.print("  3. Run:    insights pipeline run <pipeline_id>")
    except OSError as exc:
        err_console.print(f"[red]Error:[/red] Could not write output file: {exc}")
        raise typer.Exit(1) from None


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


# ---------------------------------------------------------------------------
# advise command
# ---------------------------------------------------------------------------


@app.command()
def advise(
    ctx: typer.Context,
    research_question: Annotated[str, typer.Argument(help="Research question to characterize")],
    recommend: Annotated[
        bool,
        typer.Option(
            "--recommend",
            "-r",
            help="Run Stage 3 to produce full recommendation with pipeline sketch",
        ),
    ] = False,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Reasoning profile to use (overrides default)"),
    ] = None,
    data_context: Annotated[
        str | None,
        typer.Option("--data-context", "-d", help="JSON string with data context (optional)"),
    ] = None,
) -> None:
    """Research question -> method recommendation.

    Calls Stage 1 (characterize) then Stage 2 (match) to produce ranked method candidates.
    With --recommend, also calls Stage 3 (recommend) for full recommendation with pipeline sketch.
    """
    base = _base_url(ctx)

    # Parse data_context if provided
    context_dict: dict | None = None
    if data_context:
        try:
            context_dict = json.loads(data_context)
        except json.JSONDecodeError:
            err_console.print(f"[red]Invalid JSON in --data-context:[/red] {data_context}")
            raise typer.Exit(1) from None

    # Build query params
    params = {}
    if profile:
        params["profile"] = profile

    # Stage 1: characterize
    console.print("[bold]Stage 1:[/bold] Characterizing problem...")
    characterize_payload = {
        "research_question": research_question,
        "data_context": context_dict,
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
    url = (
        f"{base}/advise/characterize?{query_string}"
        if query_string
        else f"{base}/advise/characterize"
    )
    characterize_result = _post(url, characterize_payload)
    problem_profile = characterize_result.get("profile", {})
    console.print("[green]✓[/green] Problem characterized")

    # Stage 2: match
    console.print("[bold]Stage 2:[/bold] Matching candidates...")
    match_payload = {"profile": problem_profile}
    url = f"{base}/advise/match?{query_string}" if query_string else f"{base}/advise/match"
    match_result = _post(url, match_payload)
    candidates = match_result.get("candidates", [])
    console.print(f"[green]✓[/green] Found {len(candidates)} candidate methods")

    # Display candidates table
    if not candidates:
        console.print("[yellow]No matching methods found.[/yellow]")
        return

    console.print("\n[bold]Ranked Method Candidates:[/bold]")
    table = Table(title="Method Candidates", show_lines=True)
    table.add_column("Rank", style="cyan", no_wrap=True, width=6)
    table.add_column("Method", style="bold", no_wrap=True)
    table.add_column("Fit Score", justify="right", style="green")
    table.add_column("Fit Reasoning")
    table.add_column("Tradeoffs")

    for idx, candidate in enumerate(candidates, 1):
        score = candidate.get("fit_score", 0)
        score_str = f"{score:.2f}" if isinstance(score, (int, float)) else str(score)
        table.add_row(
            str(idx),
            candidate.get("block_implementation", "Unknown"),
            score_str,
            candidate.get("fit_reasoning", "")[:80] + "..."
            if len(candidate.get("fit_reasoning", "")) > 80
            else candidate.get("fit_reasoning", ""),
            candidate.get("tradeoffs", "")[:80] + "..."
            if len(candidate.get("tradeoffs", "")) > 80
            else candidate.get("tradeoffs", ""),
        )

    console.print(table)

    # Stage 3: recommend (if --recommend flag)
    if recommend:
        console.print("\n[bold]Stage 3:[/bold] Generating recommendation...")
        recommend_payload = {"candidates": candidates, "constraints": None}
        url = (
            f"{base}/advise/recommend?{query_string}"
            if query_string
            else f"{base}/advise/recommend"
        )
        recommend_result = _post(url, recommend_payload)
        recommendation = recommend_result.get("recommendation", {})
        console.print("[green]✓[/green] Recommendation generated")

        # Display recommendation
        console.print(
            "\n[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]"
        )
        console.print(
            f"[bold cyan]Selected Method:[/bold cyan] {recommendation.get('selected_method', 'Unknown')}"
        )
        console.print("\n[bold]Rationale:[/bold]")
        console.print(recommendation.get("rationale", "No rationale provided."))

        pipeline_sketch = recommendation.get("pipeline_sketch")
        if pipeline_sketch:
            console.print("\n[bold]Pipeline Sketch:[/bold]")
            print_json(json.dumps(pipeline_sketch))

        practitioner_workflow = recommendation.get("practitioner_workflow")
        if practitioner_workflow:
            console.print(f"\n[bold]Practitioner Workflow:[/bold] {practitioner_workflow}")

        console.print(
            "[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]"
        )


# ---------------------------------------------------------------------------
# run commands
# ---------------------------------------------------------------------------


@run_app.command("resume")
def run_resume(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Run ID to resume")],
    hitl_response: Annotated[
        str,
        typer.Option(
            "--hitl-response",
            "-r",
            help="Path to JSON file containing HITL response",
        ),
    ] = None,
) -> None:
    """Resume a suspended HITL run by submitting a response file."""
    if not hitl_response:
        err_console.print("[red]Error:[/red] --hitl-response is required")
        raise typer.Exit(1) from None

    # Load response file
    response_path = Path(hitl_response)
    if not response_path.exists():
        err_console.print(f"[red]Error:[/red] Response file not found: {hitl_response}")
        raise typer.Exit(1) from None

    try:
        response_content = response_path.read_text()
        response_data = json.loads(response_content)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error:[/red] Invalid JSON in response file: {exc}")
        raise typer.Exit(1) from None
    except OSError as exc:
        err_console.print(f"[red]Error:[/red] Could not read response file: {exc}")
        raise typer.Exit(1) from None

    # Build request payload
    payload = {"response": response_data, "metadata": {}}

    # POST to HITL endpoint
    base = _base_url(ctx)
    try:
        result = _post(f"{base}/hitl/{run_id}/respond", payload)
    except httpx.HTTPStatusError:
        # Already handled by _post, but provide context
        raise typer.Exit(1) from None

    console.print(f"[green]✓[/green] Run resumed: {result['run_id']}")
    console.print(f"  Status : {result['status']}")
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  Check status: insights run status {run_id}")


if __name__ == "__main__":
    app()
