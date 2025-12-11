"""Command-line interface for the research agent using Typer."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from research_agent.config import get_settings, load_settings, reset_settings
from research_agent.exceptions import ConfigurationError
from research_agent.logging_config import get_logger, setup_logging

app = typer.Typer(
    name="research-agent",
    help="Deep research agent powered by LangGraph and multi-LLM orchestration",
    add_completion=False,
)

console = Console()
logger = get_logger(__name__)


@app.command()
def run(
    thread_id: str = typer.Argument(
        ...,
        help="Thread ID for the research session",
    ),
    query: str = typer.Argument(
        ...,
        help="Research query to process",
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env-file",
        "-e",
        help="Path to .env file",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Enable interactive mode for plan approval",
    ),
) -> None:
    """Run a research query with the specified thread ID.

    Args:
        thread_id: Unique identifier for the research thread.
        query: The research query to process.
        env_file: Optional path to .env file.
        interactive: Enable interactive mode for plan approval.
    """
    try:
        if env_file:
            reset_settings()
            settings = load_settings(env_file)
        else:
            settings = get_settings()

        setup_logging(settings.logging)

        console.print(
            Panel(
                f"[bold cyan]Thread ID:[/bold cyan] {thread_id}\n"
                f"[bold cyan]Query:[/bold cyan] {query}\n"
                f"[bold cyan]LLM Provider:[/bold cyan] {settings.llm.provider.value}\n"
                f"[bold cyan]Interactive:[/bold cyan] {interactive}",
                title="[bold green]Research Agent[/bold green]",
                border_style="green",
            )
        )

        logger.info(
            "Starting research query",
            thread_id=thread_id,
            query=query,
            provider=settings.llm.provider.value,
        )

        console.print("\n[yellow]⚠ Agent execution not yet implemented[/yellow]")
        console.print("[dim]This will be implemented in future iterations[/dim]\n")

        logger.info("Research query completed", thread_id=thread_id)

    except ConfigurationError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}", style="red")
        logger.error("Configuration error", error=str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        logger.exception("Unexpected error during research query")
        raise typer.Exit(code=1)


@app.command()
def config(
    env_file: Optional[Path] = typer.Option(
        None,
        "--env-file",
        "-e",
        help="Path to .env file",
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="Only validate configuration without displaying",
    ),
) -> None:
    """Display and validate current configuration.

    Args:
        env_file: Optional path to .env file.
        validate_only: Only validate without displaying.
    """
    try:
        if env_file:
            reset_settings()
            settings = load_settings(env_file)
        else:
            settings = get_settings()

        if validate_only:
            console.print("[bold green]✓[/bold green] Configuration is valid")
            return

        table = Table(title="Research Agent Configuration", show_header=True, header_style="bold")
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Setting", style="magenta")
        table.add_column("Value", style="green")

        table.add_row("General", "Environment", settings.environment)

        table.add_row("LLM", "Provider", settings.llm.provider.value)
        table.add_row("LLM", "Model", getattr(settings.llm, f"{settings.llm.provider.value}_model"))
        table.add_row("LLM", "Temperature", str(settings.llm.temperature))
        table.add_row("LLM", "Max Tokens", str(settings.llm.max_tokens))

        table.add_row("Tavily", "Max Results", str(settings.tavily.max_results))
        table.add_row("Tavily", "Search Depth", settings.tavily.search_depth)

        table.add_row("Storage", "Backend", settings.storage.backend.value)
        if settings.storage.backend.value == "sqlite":
            table.add_row("Storage", "SQLite Path", str(settings.storage.sqlite_path))
        else:
            table.add_row("Storage", "Redis URL", settings.storage.redis_url)

        table.add_row("Agent", "Recursion Limit", str(settings.agent.recursion_limit))
        table.add_row("Agent", "Max Iterations", str(settings.agent.max_iterations))
        table.add_row("Agent", "Cost Cap (USD)", str(settings.agent.cost_cap_usd))
        table.add_row("Agent", "Timeout (s)", str(settings.agent.timeout_seconds))

        table.add_row("API", "Host", settings.api.host)
        table.add_row("API", "Port", str(settings.api.port))

        table.add_row("Logging", "Level", settings.logging.level.value)
        table.add_row("Logging", "Format", settings.logging.format)

        console.print(table)

        validation = settings.validate_api_keys()
        console.print("\n[bold]API Key Validation:[/bold]")
        for key, valid in validation.items():
            status = "[green]✓[/green]" if valid else "[red]✗[/red]"
            console.print(f"  {status} {key}")

    except ConfigurationError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}", style="red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(code=1)


@app.command()
def serve(
    host: Optional[str] = typer.Option(
        None,
        "--host",
        help="Host to bind to",
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port",
        help="Port to bind to",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable auto-reload for development",
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env-file",
        "-e",
        help="Path to .env file",
    ),
) -> None:
    """Start the FastAPI server.

    Args:
        host: Host to bind to (overrides config).
        port: Port to bind to (overrides config).
        reload: Enable auto-reload.
        env_file: Optional path to .env file.
    """
    try:
        if env_file:
            reset_settings()
            settings = load_settings(env_file)
        else:
            settings = get_settings()

        setup_logging(settings.logging)

        import uvicorn

        from research_agent.api import app as fastapi_app

        host = host or settings.api.host
        port = port or settings.api.port
        reload = reload or settings.api.reload

        console.print(
            Panel(
                f"[bold cyan]Host:[/bold cyan] {host}\n"
                f"[bold cyan]Port:[/bold cyan] {port}\n"
                f"[bold cyan]Reload:[/bold cyan] {reload}\n"
                f"[bold cyan]Docs:[/bold cyan] http://{host}:{port}/docs",
                title="[bold green]Starting API Server[/bold green]",
                border_style="green",
            )
        )

        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            reload=reload,
            log_config=None,
        )

    except ConfigurationError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}", style="red")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Display version information."""
    from importlib.metadata import version as get_version

    try:
        version_str = get_version("research-agent")
    except Exception:
        version_str = "unknown"

    console.print(
        Panel(
            f"[bold cyan]Research Agent[/bold cyan]\n"
            f"[bold]Version:[/bold] {version_str}\n"
            f"[bold]Python:[/bold] 3.11+",
            border_style="blue",
        )
    )


if __name__ == "__main__":
    app()
