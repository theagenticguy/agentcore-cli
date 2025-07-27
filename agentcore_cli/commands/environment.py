"""Environment management commands for AgentCore Platform CLI.

This module provides commands for managing environments (dev, staging, prod)
in our environment-first architecture.
"""

import click
from datetime import datetime
from tabulate import tabulate

from agentcore_cli.services.config import config_manager
from agentcore_cli.utils.validation import validate_region
from agentcore_cli.utils.rich_utils import (
    print_success,
    print_error,
    print_info,
    print_warning,
    console,
    confirm_action,
    print_commands,
    print_summary_box,
    prompt_input,
)


@click.group()
def env_group() -> None:
    """Environment management commands.

    Manage development, staging, and production environments.
    Each environment maintains isolated agent runtimes, endpoints, and configurations.
    """
    pass


@env_group.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed environment information")
def list_environments(verbose: bool) -> None:
    """List all environments.

    Shows all configured environments with their basic information.
    Use --verbose to see detailed configuration for each environment.
    """
    if not config_manager.config.environments:
        print_info("No environments configured")
        print_commands([("agentcore-cli env create dev", "Create your first environment")])
        return

    current_env = config_manager.current_environment
    console.print("📋 [bold]Configured Environments[/bold]")
    console.print()

    if verbose:
        # Detailed view
        for env_name, env_config in config_manager.config.environments.items():
            is_current = "✅ CURRENT" if env_name == current_env else ""

            console.print(f"🌍 [bright_blue bold]{env_name}[/bright_blue bold] {is_current}")

            env_data = {
                "Region": env_config.region,
                "Created": env_config.created_at.strftime("%Y-%m-%d %H:%M") if env_config.created_at else "Unknown",
                "Updated": env_config.updated_at.strftime("%Y-%m-%d %H:%M") if env_config.updated_at else "Never",
                "Agent Runtimes": str(len(env_config.agent_runtimes)),
                "Default Runtime": env_config.default_agent_runtime or "None",
                "Environment Variables": str(len(env_config.environment_variables)),
            }

            print_summary_box(f"Environment Details", env_data, style="blue")

            if env_config.agent_runtimes:
                console.print("   [bold]Runtimes:[/bold]")
                for runtime_name in env_config.agent_runtimes.keys():
                    marker = " (default)" if runtime_name == env_config.default_agent_runtime else ""
                    console.print(f"     • {runtime_name}{marker}")
            console.print()
    else:
        # Table view
        table_data = []
        for env_name, env_config in config_manager.config.environments.items():
            is_current = "✅" if env_name == current_env else ""
            table_data.append(
                [
                    is_current,
                    env_name,
                    env_config.region,
                    len(env_config.agent_runtimes),
                    env_config.default_agent_runtime or "-",
                ]
            )

        headers = ["", "Environment", "Region", "Agents", "Default Agent"]
        console.print(tabulate(table_data, headers=headers, tablefmt="simple"))
        console.print()
        print_info("Use --verbose for detailed information")


@env_group.command("current")
def show_current() -> None:
    """Show current environment details."""
    current_env = config_manager.current_environment

    if current_env not in config_manager.config.environments:
        print_error("Current environment not found", f"'{current_env}' not in configuration")
        return

    env_config = config_manager.config.environments[current_env]

    console.print(f"🎯 [bright_green bold]Current Environment: {current_env}[/bright_green bold]")
    console.print()

    current_data = {
        "Region": env_config.region,
        "Default Runtime": env_config.default_agent_runtime or "None",
        "Agent Runtimes": str(len(env_config.agent_runtimes)),
        "Environment Variables": str(len(env_config.environment_variables)),
        "Created": env_config.created_at.strftime("%Y-%m-%d %H:%M") if env_config.created_at else "Unknown",
        "Updated": env_config.updated_at.strftime("%Y-%m-%d %H:%M") if env_config.updated_at else "Never",
    }

    print_summary_box("Environment Information", current_data, style="green")

    if env_config.agent_runtimes:
        console.print()
        console.print("[bold]Agent Runtimes:[/bold]")
        for runtime_name, runtime in env_config.agent_runtimes.items():
            marker = " ⭐" if runtime_name == env_config.default_agent_runtime else ""
            console.print(f"  • [bright_blue]{runtime_name}{marker}[/bright_blue]")
            console.print(f"    Runtime ID: {runtime.agent_runtime_id}")
            console.print(f"    Latest Version: {runtime.latest_version}")
            console.print(f"    Region: {runtime.region}")

    if env_config.environment_variables:
        console.print()
        console.print("[bold]Environment Variables:[/bold]")
        for key, value in env_config.environment_variables.items():
            # Mask sensitive values
            display_value = (
                "***"
                if any(sensitive in key.lower() for sensitive in ["key", "secret", "token", "password"])
                else value
            )
            console.print(f"  • {key}={display_value}")


@env_group.command("create")
@click.argument("name")
@click.option("--region", "-r", help="AWS region for the environment")
@click.option("--description", "-d", help="Description for the environment")
@click.option("--set-current", is_flag=True, help="Set as current environment after creation")
def create_environment(
    name: str, region: str = "us-west-2", description: str | None = None, set_current: bool = False
) -> None:
    """Create a new environment.

    Creates a new isolated environment for deploying agents.
    Each environment maintains its own agent runtimes, endpoints, and configuration.

    Examples:
      agentcore-cli env create dev --region us-east-1 --set-current
      agentcore-cli env create staging --region us-west-2
      agentcore-cli env create prod --region eu-west-1 --description "Production environment"
    """
    # Validate environment name
    if not name.replace("-", "").replace("_", "").isalnum():
        print_error("Environment name must contain only letters, numbers, hyphens, and underscores")
        return

    if len(name) > 20:
        print_error("Environment name must be 20 characters or less")
        return

    # Check if environment already exists
    if name in config_manager.config.environments:
        print_error("Environment already exists", name)
        return

    # Get region from current environment or AWS default if not provided
    if not region:
        from agentcore_cli.utils.aws_utils import get_aws_region

        region = get_aws_region() or "us-east-1"
        print_info(f"Using region: {region}")

    # Validate region
    is_valid, error_msg = validate_region(region)
    if not is_valid:
        print_error(error_msg)
        return

    console.print(f"🚀 [bold]Creating environment '{name}' in region {region}...[/bold]")

    try:
        # Create environment
        success = config_manager.add_environment(name, region)

        if not success:
            print_error("Failed to create environment", name)
            return

        # Add description if provided
        if description:
            env_config = config_manager.config.environments[name]
            # We don't have a description field in the model, but we could add it to environment_variables
            env_config.environment_variables["ENVIRONMENT_DESCRIPTION"] = description
            config_manager.save_config()

        print_success("Environment created successfully", name)

        # Set as current if requested
        if set_current:
            config_manager.set_current_environment(name)
            print_success("Environment set as current", name)

        # Show next steps
        console.print()
        next_steps: list[tuple[str, str | None]] = []
        if not set_current:
            next_steps.append((f"agentcore-cli env use {name}", "Switch to environment"))
        next_steps.extend(
            [
                (f"agentcore-cli agent create my-agent", "Create an agent"),
                (f"agentcore-cli env current", "View environment"),
            ]
        )

        print_commands(next_steps, title="🎉 Next steps")

    except Exception as e:
        print_error("Failed to create environment", str(e))


@env_group.command("use")
@click.argument("name")
def use_environment(name: str) -> None:
    """Switch to a different environment.

    Changes the current active environment for all subsequent commands.
    All agent operations will target the selected environment.

    Examples:
      agentcore-cli env use dev
      agentcore-cli env use staging
      agentcore-cli env use prod
    """
    if name not in config_manager.config.environments:
        print_error("Environment not found", name)
        console.print()
        console.print("[bold]Available environments:[/bold]")
        for env_name in config_manager.config.environments.keys():
            console.print(f"  • {env_name}")
        return

    # Switch environment
    if config_manager.set_current_environment(name):
        print_success("Switched to environment", name)

        # Show environment summary
        env_config = config_manager.config.environments[name]

        summary_data = {"Region": env_config.region, "Agent Runtimes": str(len(env_config.agent_runtimes))}

        if env_config.default_agent_runtime:
            summary_data["Default Runtime"] = env_config.default_agent_runtime

        print_summary_box("Environment Summary", summary_data, style="green")

        if not env_config.agent_runtimes:
            print_info("No agent runtimes yet")
            print_commands([("agentcore-cli agent create <name>", "Create one")])
    else:
        print_error("Failed to switch to environment", name)


@env_group.command("delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.option("--keep-resources", is_flag=True, help="Keep AWS resources (only remove from config)")
def delete_environment(name: str, force: bool = False, keep_resources: bool = False) -> None:
    """Delete an environment.

    ⚠️  WARNING: This will delete the environment and optionally its AWS resources.
    All agent runtimes and endpoints in this environment will be removed.

    Examples:
      agentcore-cli env delete old-env --force
      agentcore-cli env delete dev --keep-resources  # Remove from config only
    """
    if name not in config_manager.config.environments:
        print_error("Environment not found", name)
        return

    # Prevent deletion of current environment without explicit force
    if name == config_manager.current_environment and not force:
        print_error("Cannot delete current environment without --force", name)
        print_commands([("agentcore-cli env use <other-env>", "Switch to another environment first")])
        return

    env_config = config_manager.config.environments[name]

    # Show what will be deleted
    console.print(f"⚠️  [red bold]Environment '{name}' Deletion[/red bold]")
    console.print()

    deletion_data = {
        "Environment": name,
        "Region": env_config.region,
        "Agent Runtimes": str(len(env_config.agent_runtimes)),
        "AWS Resources": "Will be deleted" if not keep_resources else "Will be kept",
    }

    print_summary_box("Deletion Plan", deletion_data, style="red")

    if env_config.agent_runtimes:
        console.print("[bold]Runtimes to be removed:[/bold]")
        for runtime_name in env_config.agent_runtimes.keys():
            console.print(f"  • {runtime_name}")

    if not keep_resources:
        console.print()
        print_warning("AWS resources will also be deleted!")
        console.print("This includes CloudFormation stacks, ECR repositories, and IAM roles.")

    # Confirmation
    if not force:
        console.print()
        if keep_resources:
            message = f"Remove environment '{name}' from configuration only?"
        else:
            message = f"DELETE environment '{name}' and all its AWS resources?"

        if not confirm_action(message):
            print_info("Deletion cancelled")
            return

    console.print(f"🗑️  [bold]Deleting environment '{name}'...[/bold]")

    try:
        # Delete agent runtimes first if not keeping resources
        deleted_resources = []
        errors = []

        if not keep_resources and env_config.agent_runtimes:
            print_info("🤖 Deleting agent runtimes...")
            for runtime_name in list(env_config.agent_runtimes.keys()):
                try:
                    # Use the agent delete command logic
                    from agentcore_cli.services.agentcore import AgentCoreService
                    from agentcore_cli.services.ecr import ECRService
                    from agentcore_cli.services.iam import IAMService

                    agentcore_service = AgentCoreService(region=env_config.region)
                    ecr_service = ECRService(region=env_config.region)
                    iam_service = IAMService(region=env_config.region)

                    runtime = env_config.agent_runtimes[runtime_name]

                    # Delete agent runtime
                    if runtime.agent_runtime_id:
                        result = agentcore_service.delete_agent_runtime(runtime.agent_runtime_id)
                        if result.success:
                            deleted_resources.extend(result.deleted_resources)

                    # Delete ECR repository
                    ecr_success, ecr_message = ecr_service.delete_repository(runtime_name, name, force=True)
                    if ecr_success:
                        deleted_resources.append(f"ECR Repository: {runtime_name}")

                    # Delete IAM role
                    iam_success, iam_message = iam_service.delete_agent_role(runtime_name, name)
                    if iam_success:
                        deleted_resources.append(f"IAM Role: agentcore-{runtime_name}-{name}")

                except Exception as e:
                    errors.append(f"Failed to delete resources for {runtime_name}: {str(e)}")

        # Delete environment from config
        if config_manager.delete_environment(name):
            print_success("Environment deleted successfully", name)

            # Switch to another environment if this was current
            if name == config_manager.current_environment:
                remaining_envs = list(config_manager.config.environments.keys())
                if remaining_envs:
                    new_current = remaining_envs[0]
                    config_manager.set_current_environment(new_current)
                    print_success("Switched to environment", new_current)
                else:
                    print_info("No environments remaining")
                    print_commands([("agentcore-cli env create <name>", "Create one")])

            # Show summary
            if deleted_resources:
                console.print()
                console.print("[bold green]Deleted AWS resources:[/bold green]")
                for resource in deleted_resources:
                    console.print(f"  ✅ {resource}")

            if errors:
                console.print()
                console.print("[bold red]Errors encountered:[/bold red]")
                for error in errors:
                    console.print(f"  ❌ {error}")
        else:
            print_error("Failed to delete environment", name)

    except Exception as e:
        print_error("Failed to delete environment", str(e))


@env_group.command("vars")
@click.option("--set", "set_var", help="Set variable (format: KEY=VALUE)")
@click.option("--unset", help="Remove variable")
@click.option("--list", "list_vars", is_flag=True, help="List all variables")
@click.option("--env", "environment", help="Target environment (defaults to current)")
def manage_variables(
    set_var: str | None = None, unset: str | None = None, list_vars: bool = False, environment: str | None = None
) -> None:
    """Manage environment variables.

    Environment variables are available to all agent runtimes in the environment.

    Examples:
        agentcore-cli env vars --list
        agentcore-cli env vars --set API_KEY=secret123
        agentcore-cli env vars --unset OLD_CONFIG
        agentcore-cli env vars --set DEBUG=true --env staging
    """
    target_env = environment or config_manager.current_environment

    if target_env not in config_manager.config.environments:
        print_error("Environment not found", target_env)
        return

    env_config = config_manager.config.environments[target_env]

    if list_vars or (not set_var and not unset):
        # List variables
        console.print(f"🌍 [bold]Environment Variables for '{target_env}'[/bold]:")
        if not env_config.environment_variables:
            print_info("No variables set")
        else:
            for key, value in sorted(env_config.environment_variables.items()):
                # Mask sensitive values
                display_value = (
                    "***"
                    if any(sensitive in key.lower() for sensitive in ["key", "secret", "token", "password"])
                    else value
                )
                console.print(f"   {key}={display_value}")
        return

    if set_var:
        # Set variable
        if "=" not in set_var:
            print_error("Invalid format. Use: KEY=VALUE")
            return

        key, value = set_var.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            print_error("Variable name cannot be empty")
            return

        env_config.environment_variables[key] = value
        env_config.updated_at = datetime.now()
        config_manager.save_config()

        masked_value = "***" if any(s in key.lower() for s in ["key", "secret", "token", "password"]) else value
        print_success("Variable set", f"{key}={masked_value} in '{target_env}'")

    if unset:
        # Remove variable
        if unset in env_config.environment_variables:
            del env_config.environment_variables[unset]
            env_config.updated_at = datetime.now()
            config_manager.save_config()
            print_success("Variable removed", f"{unset} from '{target_env}'")
        else:
            print_error("Variable not found", f"'{unset}' in '{target_env}'")


if __name__ == "__main__":
    env_group()
