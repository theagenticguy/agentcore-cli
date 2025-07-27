"""
AgentCore Platform CLI - Main entry point.

A production-ready CLI for deploying and managing AI agents on AWS Bedrock AgentCore Runtime.
Built with environment-first architecture, robust CloudFormation automation, and
sophisticated configuration management.
"""

import click
import sys
from loguru import logger
from pathlib import Path
from types import TracebackType
from typing import Any
from agentcore_cli.commands.setup import setup_cli
from agentcore_cli.commands.unified_agent import unified_agent_cli
from agentcore_cli.commands.config import config_cli
from agentcore_cli.commands.environment import env_group
from agentcore_cli.commands.container import container_group
from agentcore_cli.commands.resources import resources_group
from agentcore_cli.utils.rich_utils import print_ascii_banner, console

# Configure logging
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
)


def print_version(ctx: click.Context, _: Any, value: bool) -> None:
    """Print version information and exit."""
    if not value or ctx.resilient_parsing:
        return

    try:
        from agentcore_cli import __version__

        print_ascii_banner()
        console.print(f"[bright_green bold]Version {__version__}[/bright_green bold]")
        console.print("[dim]Built with ❤️ for the AI agent development community[/dim]")
        console.print()
        console.print("📚 [bold cyan]Documentation:[/bold cyan] https://docs.agentcore.dev")
        console.print("🐛 [bold cyan]Issues:[/bold cyan] https://github.com/agentcore/agentcore-platform-cli/issues")
    except ImportError:
        print_ascii_banner()
        console.print("[bright_green bold]Development Version[/bright_green bold]")

    ctx.exit()


def print_banner() -> None:
    """Print welcome banner for interactive commands."""
    print_ascii_banner("Deploy and manage AI agents on AWS Bedrock AgentCore Runtime")


@click.group(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120})
@click.option(
    "--version", is_flag=True, callback=print_version, expose_value=False, is_eager=True, help="Show version and exit"
)
@click.option("--config", help="Path to config file (default: .agentcore/config.json)", envvar="AGENTCORE_CONFIG")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging", envvar="AGENTCORE_VERBOSE")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
@click.pass_context
def cli(ctx: click.Context, config: str | None = None, verbose: bool = False, quiet: bool = False) -> None:
    """
    🚀 AgentCore Platform CLI - Deploy and manage AI agents on AWS Bedrock AgentCore Runtime

    \b
    ARCHITECTURE HIGHLIGHTS:
    • Environment-First Design: Clean dev/staging/prod separation
    • Container-Native: Docker build and ECR integration
    • Infrastructure as Code: CloudFormation with robust polling
    • Configuration Sync: Sophisticated drift detection with DeepDiff
    • Security-First: Integrated Cognito auth and IAM management

    \b
    QUICK START:
    • Initialize project:    agentcore-cli init
    • Create agent:          agentcore-cli agent create my-bot --dockerfile ./Dockerfile
    • Invoke agent:          agentcore-cli agent invoke my-bot --prompt "Hello!"
    • Switch environment:    agentcore-cli env use prod
    • Sync configuration:    agentcore-cli config sync --push

    \b
    COMMAND GROUPS:
    • init        Interactive setup wizard
    • agent       Agent lifecycle management (create, deploy, invoke, delete)
    • env         Environment management (dev, staging, prod)
    • container   Docker build and push operations
    • config      Configuration and cloud sync management
    • resources   AWS resource management (ECR, IAM, Cognito)

    Use 'agentcore-cli <command> --help' for detailed help on any command.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Configure logging based on flags
    if verbose:
        logger.remove()
        logger.add(
            sys.stderr,
            format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG",
        )
        ctx.obj["verbose"] = True
    elif quiet:
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
        ctx.obj["quiet"] = True

    # Store config path if provided
    if config:
        ctx.obj["config_path"] = Path(config)

    # Validate AWS credentials early for most commands
    if ctx.invoked_subcommand not in ["init", "--help", "--version"]:
        from agentcore_cli.utils.aws_utils import validate_aws_credentials

        if not validate_aws_credentials():
            click.echo("❌ ", nl=False, err=True)
            click.echo(click.style("AWS credentials not found or invalid", fg="red"), err=True)
            click.echo("", err=True)
            click.echo("Please configure AWS credentials using one of:", err=True)
            click.echo("  • aws configure", err=True)
            click.echo("  • export AWS_ACCESS_KEY_ID=... && export AWS_SECRET_ACCESS_KEY=...", err=True)
            click.echo("  • Use IAM roles or AWS SSO", err=True)
            click.echo("", err=True)
            click.echo("Then run: agentcore-cli init", err=True)
            sys.exit(1)


# Import and register command groups
def register_commands() -> None:
    """Register all command groups with the main CLI."""

    # Register all commands
    cli.add_command(setup_cli, name="init")
    cli.add_command(unified_agent_cli, name="agent")
    cli.add_command(env_group, name="env")
    cli.add_command(container_group, name="container")
    cli.add_command(config_cli, name="config")
    cli.add_command(resources_group, name="resources")


# Global error handler
def handle_exception(
    exc_type: type[BaseException], exc_value: BaseException, exc_traceback: TracebackType | None
) -> None:
    """Global exception handler for better error messages."""
    if issubclass(exc_type, KeyboardInterrupt):
        click.echo("\n⚠️  Operation cancelled by user", err=True)
        sys.exit(1)
    elif issubclass(exc_type, click.ClickException):
        # Let Click handle its own exceptions
        raise exc_value
    else:
        # Log unexpected errors
        logger.error(f"Unexpected error: {exc_value}")
        # Show full traceback in verbose mode (check environment variable)
        import os

        if os.getenv("AGENTCORE_VERBOSE"):
            import traceback

            traceback.print_exception(exc_type, exc_value, exc_traceback)
        else:
            click.echo("❌ An unexpected error occurred. Use --verbose for details.", err=True)
        sys.exit(1)


# Quick commands for common operations (shortcuts)
@cli.command("deploy", hidden=True)
@click.argument("name")
@click.option("--dockerfile", default="Dockerfile", help="Path to Dockerfile")
def deploy_shortcut(name: str, dockerfile: str = "Dockerfile") -> None:
    """Quick deploy shortcut (hidden - use 'agent create' instead)."""
    click.echo("💡 Use 'agentcore-cli agent create' for full functionality:")
    click.echo(f"   agentcore-cli agent create {name} --dockerfile {dockerfile}")


@cli.command("invoke", hidden=True)
@click.argument("name")
@click.option("--prompt", help="Prompt for the agent")
def invoke_shortcut(name: str, prompt: str | None = None) -> None:
    """Quick invoke shortcut (hidden - use 'agent invoke' instead)."""
    click.echo("💡 Use 'agentcore-cli agent invoke' for full functionality:")
    if prompt:
        click.echo(f'   agentcore-cli agent invoke {name} --prompt "{prompt}"')
    else:
        click.echo(f"   agentcore-cli agent invoke {name}")


def main() -> None:
    # Set up global exception handling
    sys.excepthook = handle_exception

    # Register all commands
    register_commands()

    # Run CLI
    cli()
