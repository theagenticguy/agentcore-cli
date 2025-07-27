"""Configuration management commands for AgentCore Platform CLI.

This module provides CLI commands for managing configuration, environments,
and synchronization settings.
"""

import click
from pathlib import Path
from tabulate import tabulate

from agentcore_cli.services.config import config_manager
from agentcore_cli.utils.rich_utils import (
    print_success,
    print_error,
    print_info,
    print_warning,
    console,
    confirm_action,
    print_commands,
    print_summary_box,
)


@click.group()
def config_cli() -> None:
    """Configuration management commands."""
    pass


# Environment Management Commands
@config_cli.group()
def env() -> None:
    """Environment management commands."""
    pass


@env.command("list")
def list_environments() -> None:
    """List all environments."""
    if not config_manager.config.environments:
        print_info("No environments configured")
        print_commands([("agentcore-cli env create dev", "Create your first environment")])
        return

    console.print("📋 [bold]Available Environments[/bold]")
    console.print()

    table_data = []
    for env_name, env_config in config_manager.config.environments.items():
        current_marker = "✅" if env_name == config_manager.current_environment else ""
        table_data.append(
            [
                current_marker,
                env_name,
                env_config.region,
                len(env_config.agent_runtimes),
                env_config.default_agent_runtime or "-",
            ]
        )

    headers = ["", "Environment", "Region", "Agents", "Default Agent"]
    console.print(tabulate(table_data, headers=headers, tablefmt="simple"))


@env.command("use")
@click.argument("name")
def use_environment(name: str) -> None:
    """Switch to a different environment."""
    if config_manager.set_current_environment(name):
        print_success("Switched to environment", name)
    else:
        print_error("Failed to switch to environment", name)
        return


@env.command("add")
@click.argument("name")
@click.option("--region", default="us-west-2", help="AWS region for the environment")
def add_environment(name: str, region: str = "us-west-2") -> None:
    """Add a new environment."""
    if config_manager.add_environment(name, region):
        print_success("Environment added", f"'{name}' with region '{region}'")
    else:
        print_error("Failed to add environment", name)
        return


@env.command("update")
@click.argument("name")
@click.option("--region", help="AWS region for the environment")
def update_environment(name: str, region: str | None = None) -> None:
    """Update an environment."""
    updates = {}
    if region:
        updates["region"] = region

    if not updates:
        print_error("No updates specified")
        return

    if config_manager.update_environment(name, **updates):
        print_success("Environment updated", name)
    else:
        print_error("Failed to update environment", name)
        return


@env.command("delete")
@click.argument("name")
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
def delete_environment(name: str, force: bool = False) -> None:
    """Delete an environment."""
    if not force:
        if not confirm_action(f"Are you sure you want to delete environment '{name}'?"):
            print_info("Deletion cancelled")
            return

    if config_manager.delete_environment(name):
        print_success("Environment deleted", name)
    else:
        print_error("Failed to delete environment", name)
        return


# Configuration Management Commands
@config_cli.command("export")
@click.option("--file", "-f", default="agentcore-config.json", help="Output file path")
def export_config(file: str) -> None:
    """Export configuration to a file."""
    if config_manager.export_config(file):
        print_success("Configuration exported", file)
    else:
        print_error("Failed to export configuration", file)
        return


@config_cli.command("import")
@click.argument("file")
@click.option("--force", is_flag=True, help="Force import without confirmation")
def import_config(file: str, force: bool = False) -> None:
    """Import configuration from a file."""
    if not Path(file).exists():
        print_error("Configuration file not found", file)
        return

    if not force:
        if not confirm_action(
            f"Are you sure you want to import configuration from '{file}'? This will overwrite current configuration."
        ):
            print_info("Import cancelled")
            return

    if config_manager.import_config(file):
        print_success("Configuration imported", file)
    else:
        print_error("Failed to import configuration", file)
        return


@config_cli.command("set-default-agent")
@click.argument("name")
@click.option("--environment", "-e", help="Environment (defaults to current)")
def set_default_agent(name: str, environment: str | None = None) -> None:
    """Set the default agent for an environment."""
    env_name = environment or config_manager.current_environment

    if config_manager.set_default_agent_runtime(env_name, name):
        print_success("Default agent set", f"'{name}' in environment '{env_name}'")
    else:
        print_error("Failed to set default agent", f"'{name}' in environment '{env_name}'")
        return


# Sync Management Commands
@config_cli.group()
def sync() -> None:
    """Configuration synchronization commands."""
    pass


@sync.command("enable")
@click.option("--auto", is_flag=True, help="Enable automatic sync")
def enable_sync(auto: bool = False) -> None:
    """Enable configuration synchronization with cloud."""
    if config_manager.enable_cloud_sync(True):
        print_success("Cloud configuration sync enabled")

        if auto:
            if config_manager.enable_auto_sync(True):
                print_success("Automatic sync enabled")
            else:
                print_error("Failed to enable automatic sync")
                return
    else:
        print_error("Failed to enable cloud configuration sync")
        return


@sync.command("disable")
def disable_sync() -> None:
    """Disable configuration synchronization with cloud."""
    if config_manager.enable_cloud_sync(False):
        print_success("Cloud configuration sync disabled")
    else:
        print_error("Failed to disable cloud configuration sync")
        return


@sync.command("status")
@click.option("--environment", "-e", help="Environment to check (defaults to current)")
def sync_status(environment: str | None = None) -> None:
    """Check synchronization status."""
    env_name = environment or config_manager.current_environment

    try:
        status = config_manager.get_cloud_sync_status(env_name)

        console.print(f"📊 [bold]Sync Status for environment '{env_name}'[/bold]:")

        status_data = {
            "Cloud Sync Enabled": str(status.cloud_config_enabled),
            "Auto Sync Enabled": str(status.auto_sync_enabled),
            "Last Sync": str(status.last_sync) if status.last_sync else "Never",
            "In Sync": str(status.in_sync),
        }

        print_summary_box("Configuration Sync Status", status_data)

        if status.drift_details:
            print_warning("Configuration drift detected!")
            for category, items in status.drift_details.items():
                if items:
                    console.print(f"  [yellow]{category}[/yellow]: {len(items)} items differ")

    except Exception as e:
        print_error("Failed to get sync status", str(e))
        return


@sync.command("pull")
def sync_pull() -> None:
    """Pull configuration from cloud."""
    if config_manager.pull_from_cloud():
        print_success("Configuration pulled from cloud")
    else:
        print_error("Failed to pull configuration from cloud")
        return


@sync.command("push")
def sync_push() -> None:
    """Push configuration to cloud."""
    result = config_manager.sync_with_cloud(auto=False)

    if result.success:
        print_success("Configuration pushed to cloud")
        if result.synced_items:
            print_info(f"Synced items: {len(result.synced_items)}")
    else:
        print_error("Failed to push configuration to cloud", result.message)
        if result.errors:
            for error in result.errors:
                console.print(f"  [red]• {error}[/red]")
        return


# Agent Runtime Management Commands
@config_cli.group()
def runtime() -> None:
    """Agent runtime management commands."""
    pass


@runtime.command("list")
@click.option("--environment", "-e", help="Environment to list (defaults to current)")
def list_runtimes(environment: str | None = None) -> None:
    """List agent runtimes in an environment."""
    env_name = environment or config_manager.current_environment

    try:
        env_config = config_manager.get_environment(env_name)

        if not env_config.agent_runtimes:
            print_info(f"No agent runtimes in environment '{env_name}'")
            print_commands([("agentcore-cli agent create <name>", "Create one")])
            return

        console.print(f"🤖 [bold]Agent Runtimes in '{env_name}'[/bold]:")
        console.print()

        for runtime_name, runtime in env_config.agent_runtimes.items():
            is_default = " ⭐" if runtime_name == env_config.default_agent_runtime else ""
            console.print(f"• [bright_blue bold]{runtime_name}{is_default}[/bright_blue bold]")
            console.print(f"  Runtime ID: {runtime.agent_runtime_id}")
            console.print(f"  Latest Version: {runtime.latest_version}")
            console.print(f"  Endpoints: {len(runtime.endpoints)}")
            console.print(f"  Versions: {len(runtime.versions)}")
            console.print()

    except KeyError:
        print_error("Environment not found", env_name)
        return


@runtime.command("show")
@click.argument("name")
@click.option("--environment", "-e", help="Environment (defaults to current)")
def show_runtime(name: str, environment: str | None = None) -> None:
    """Show detailed information about an agent runtime."""
    env_name = environment or config_manager.current_environment

    try:
        runtime = config_manager.get_agent_runtime(name, env_name)
        if not runtime:
            print_error("Agent runtime not found", f"'{name}' in environment '{env_name}'")
            return

        console.print(f"🤖 [bright_blue bold]Agent Runtime: {name}[/bright_blue bold]")

        runtime_data = {
            "Environment": env_name,
            "Runtime ID": runtime.agent_runtime_id,
            "Runtime ARN": runtime.agent_runtime_arn or "Not set",
            "Latest Version": runtime.latest_version,
            "Primary ECR Repository": runtime.primary_ecr_repository,
            "Region": runtime.region,
        }

        print_summary_box("Runtime Information", runtime_data)

        if runtime.versions:
            console.print()
            console.print("[bold]Versions:[/bold]")
            for version_id, version in runtime.versions.items():
                console.print(f"  • {version_id} ({version.status.value})")
                console.print(f"    Image: {version.ecr_repository_name}:{version.image_tag}")
                console.print(
                    f"    Created: {version.created_at.strftime('%Y-%m-%d %H:%M') if version.created_at else 'Unknown'}"
                )

        if runtime.endpoints:
            console.print()
            console.print("[bold]Endpoints:[/bold]")
            for endpoint_name, endpoint in runtime.endpoints.items():
                console.print(f"  • {endpoint_name} → {endpoint.target_version} ({endpoint.status.value})")

    except Exception as e:
        print_error("Failed to show runtime", str(e))
        return


# Configuration Information Commands
@config_cli.command("show")
@click.option("--environment", "-e", help="Environment to show (defaults to current)")
def show_config(environment: str | None = None) -> None:
    """Show current configuration."""
    env_name = environment or config_manager.current_environment

    console.print("📋 [bold]Configuration Summary[/bold]")

    config_data = {
        "Current Environment": config_manager.current_environment,
        "Config File": str(config_manager.config_file),
    }

    print_summary_box("General Configuration", config_data)

    try:
        env_config = config_manager.get_environment(env_name)

        env_data = {
            "Region": env_config.region,
            "Default Agent Runtime": env_config.default_agent_runtime or "None",
            "Agent Runtimes": str(len(env_config.agent_runtimes)),
            "Environment Variables": str(len(env_config.environment_variables)),
        }

        print_summary_box(f"Environment '{env_name}'", env_data)

        if env_config.agent_runtimes:
            console.print()
            console.print("[bold]Runtimes:[/bold]")
            for runtime_name in env_config.agent_runtimes.keys():
                marker = " (default)" if runtime_name == env_config.default_agent_runtime else ""
                console.print(f"    • {runtime_name}{marker}")

    except KeyError:
        print_error("Environment not found", env_name)
        return

    # Show global resources
    global_resources = config_manager.config.global_resources

    global_data = {
        "ECR Repositories": str(len(global_resources.ecr_repositories)),
        "IAM Roles": str(len(global_resources.iam_roles)),
    }

    print_summary_box("Global Resources", global_data)

    # Show sync configuration
    sync_config = global_resources.sync_config

    sync_data = {
        "Cloud Sync Enabled": str(sync_config.cloud_config_enabled),
        "Auto Sync Enabled": str(sync_config.auto_sync_enabled),
        "Parameter Store Prefix": sync_config.parameter_store_prefix,
        "Sync Interval": f"{sync_config.sync_interval_minutes} minutes",
        "Last Full Sync": str(sync_config.last_full_sync) if sync_config.last_full_sync else "Never",
    }

    print_summary_box("Sync Configuration", sync_data)


@config_cli.command("validate")
def validate_config() -> None:
    """Validate current configuration."""
    console.print("🔍 [bold]Validating configuration...[/bold]")

    errors = []
    warnings = []

    # Check if current environment exists
    if config_manager.current_environment not in config_manager.config.environments:
        errors.append(f"Current environment '{config_manager.current_environment}' does not exist")

    # Check environment configurations
    for env_name, env_config in config_manager.config.environments.items():
        if not env_config.region:
            errors.append(f"Environment '{env_name}' has no region specified")

        # Check default agent runtime
        if env_config.default_agent_runtime and env_config.default_agent_runtime not in env_config.agent_runtimes:
            errors.append(
                f"Environment '{env_name}' has non-existent default agent runtime '{env_config.default_agent_runtime}'"
            )

        # Check agent runtime configurations
        for agent_name, runtime in env_config.agent_runtimes.items():
            if not runtime.agent_runtime_id:
                errors.append(f"Agent '{agent_name}' in environment '{env_name}' has no runtime ID")

            if not runtime.agent_runtime_arn:
                errors.append(f"Agent '{agent_name}' in environment '{env_name}' has no runtime ARN")

            # Check if ECR repository exists
            if runtime.primary_ecr_repository not in config_manager.config.global_resources.ecr_repositories:
                warnings.append(
                    f"Agent '{agent_name}' in environment '{env_name}' references non-existent ECR repository '{runtime.primary_ecr_repository}'"
                )

            # Check endpoint configurations
            for endpoint_name, endpoint in runtime.endpoints.items():
                if endpoint.target_version not in runtime.versions:
                    warnings.append(
                        f"Agent '{agent_name}' endpoint '{endpoint_name}' in environment '{env_name}' references non-existent version '{endpoint.target_version}'"
                    )

    # Report results
    if errors:
        print_error("Configuration validation failed")
        for error in errors:
            console.print(f"  [red]• {error}[/red]")
        return

    if warnings:
        print_warning("Configuration warnings detected")
        for warning in warnings:
            console.print(f"  [yellow]• {warning}[/yellow]")

    print_success("Configuration is valid")
    return


# Global Resources Commands
@config_cli.group()
def resources() -> None:
    """Global resource management commands."""
    pass


@resources.command("list")
def list_resources() -> None:
    """List all global resources."""
    global_resources = config_manager.config.global_resources

    console.print("🌐 [bold]Global Resources[/bold]")
    console.print()

    # ECR Repositories
    if global_resources.ecr_repositories:
        console.print("📦 [bold]ECR Repositories:[/bold]")
        for repo_name, repo in global_resources.ecr_repositories.items():
            console.print(f"  • {repo_name}")
            console.print(f"    URI: {repo.repository_uri}")
            console.print(f"    Registry: {repo.registry_id}")
            console.print(f"    Tags: {len(repo.available_tags)}")
        console.print()

    # IAM Roles
    if global_resources.iam_roles:
        console.print("🔐 [bold]IAM Roles:[/bold]")
        for role_name, role in global_resources.iam_roles.items():
            console.print(f"  • {role_name}")
            console.print(f"    ARN: {role.arn}")
        console.print()

    if not global_resources.ecr_repositories and not global_resources.iam_roles:
        print_info("No global resources configured")
        print_commands([("agentcore-cli resources ecr create <name>", "Create resources")])
