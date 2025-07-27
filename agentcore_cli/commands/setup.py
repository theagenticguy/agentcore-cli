"""Enhanced setup command for AgentCore CLI.

This module provides a comprehensive setup experience that combines authentication,
configuration, environment creation, and initial resource setup into an interactive wizard
aligned with our environment-first architecture.
"""

import click

from agentcore_cli.services.cognito import CognitoService
from agentcore_cli.services.config import config_manager
from agentcore_cli.utils.aws_utils import get_aws_account_id, get_aws_region, validate_aws_credentials
from agentcore_cli.utils.observability import validate_and_enable_transaction_search
from agentcore_cli.utils.validation import validate_region
from agentcore_cli.utils.rich_utils import (
    print_ascii_banner,
    print_banner,
    print_step,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_copyable_values,
    print_summary_box,
    print_commands,
    confirm_action,
    prompt_input,
    console,
)


def print_welcome_banner() -> None:
    """Print an attractive welcome banner."""
    print_ascii_banner("Let's set up your AI agent development environment")

    setup_steps = [
        "Validate your AWS credentials",
        "Create your first environment (dev, staging, or prod)",
        "Configure observability (Transaction Search)",
        "Configure cloud synchronization",
        "Set up authentication resources (optional)",
        "Prepare you for agent development",
    ]

    console.print("🏗️  [bold]This wizard will:[/bold]")
    for step in setup_steps:
        console.print(f"   • {step}")
    console.print()


@click.command("init")
@click.option("--interactive/--no-interactive", default=True, help="Run interactive setup wizard")
@click.option("--region", help="AWS region to use")
@click.option("--environment", default="dev", help="Initial environment name")
@click.option("--skip-cognito", is_flag=True, help="Skip Cognito authentication setup")
@click.option("--skip-sync", is_flag=True, help="Skip cloud configuration sync setup")
@click.option("--skip-observability", is_flag=True, help="Skip Transaction Search observability setup")
def setup_cli(
    interactive: bool,
    region: str = "us-west-2",
    environment: str = "dev",
    skip_cognito: bool = False,
    skip_sync: bool = False,
    skip_observability: bool = False,
) -> None:
    """Interactive setup wizard for AgentCore Platform CLI.

    This command guides you through the complete initial setup process:
    - AWS credentials validation
    - Environment creation and configuration
    - Cloud synchronization setup
    - Optional authentication resource creation
    - Initial project structure

    Examples:
      agentcore-cli init                                                    # Full interactive setup
      agentcore-cli init --environment staging                             # Setup staging environment
      agentcore-cli init --skip-cognito --skip-sync --skip-observability  # Minimal setup
    """
    if interactive:
        print_welcome_banner()
        return run_interactive_setup(region, environment, skip_cognito, skip_sync, skip_observability)
    else:
        return run_automated_setup(region, environment, skip_cognito, skip_sync, skip_observability)


def run_interactive_setup(
    region: str = "us-west-2",
    environment: str = "dev",
    skip_cognito: bool = False,
    skip_sync: bool = False,
    skip_observability: bool = False,
) -> None:
    """Run the comprehensive interactive setup wizard."""

    # Step 1: Validate AWS credentials
    print_step(1, "AWS Credentials", "Checking your AWS configuration...")

    if not validate_aws_credentials():
        print_error("AWS credentials not found or invalid")

        credential_commands: list[tuple[str, str | None]] = [
            ("aws configure", "Configure using AWS CLI"),
            ("export AWS_ACCESS_KEY_ID=... && export AWS_SECRET_ACCESS_KEY=...", "Use environment variables"),
            ("aws sso login", "Use AWS SSO"),
        ]

        print_commands(credential_commands, title="📋 Configure AWS credentials using one of")
        print_info("After configuring credentials, run 'agentcore-cli init' again")
        return

    account_id = get_aws_account_id()
    print_success("AWS credentials validated")
    print_copyable_values({"Account": account_id or "Unknown"})

    # Step 2: Region selection
    print_step(2, "AWS Region")

    if not region:
        detected_region = get_aws_region()
        suggested_region = detected_region or "us-east-1"

        print_info(f"Detected region: {detected_region or 'None'}")
        region = prompt_input("Select AWS region", default=suggested_region) or suggested_region

    # Validate region
    is_valid, error_msg = validate_region(region)
    if not is_valid:
        print_error(error_msg)
        return

    print_success("Using AWS region", region)
    console.print()

    # Step 3: Environment setup
    print_step(3, "Environment Setup", "Environments provide isolation for dev, staging, and production deployments.")

    # Validate environment name
    while True:
        if not environment:
            environment = prompt_input("Environment name", default="dev") or "dev"

        # Validate environment name
        if not environment.replace("-", "").replace("_", "").isalnum():
            print_error("Environment name must contain only letters, numbers, hyphens, and underscores")
            environment = ""
            continue

        if len(environment) > 20:
            print_error("Environment name must be 20 characters or less")
            environment = ""
            continue

        break

    print_info(f"Creating environment '{environment}' in region {region}...")

    try:
        # Initialize config manager and create environment
        success = config_manager.add_environment(environment, region)

        if not success:
            # Environment might already exist
            if environment in config_manager.config.environments:
                print_warning(f"Environment '{environment}' already exists, using existing configuration")
                config_manager.set_current_environment(environment)
            else:
                print_error(f"Failed to create environment '{environment}'")
                return
        else:
            # Set as current environment
            config_manager.set_current_environment(environment)
            print_success(f"Environment '{environment}' created and set as current")

    except Exception as e:
        print_error("Failed to create environment", str(e))
        return

    console.print()

    # Step 4: Observability setup (Transaction Search)
    if not skip_observability:
        print_step(4, "Observability Setup", "Configure CloudWatch Transaction Search for cost-effective tracing.")

        try:
            validate_and_enable_transaction_search(region, interactive=True)
        except Exception as e:
            print_warning("Transaction Search setup failed", str(e))
            print_info("You can enable it later by running the setup again")

        console.print()

    # Step 5: Cloud sync setup
    if not skip_sync:
        print_step(
            5, "Cloud Configuration Sync", "Sync your configuration with AWS Parameter Store for team collaboration."
        )

        setup_cloud_sync = confirm_action("Enable cloud configuration sync?")

        if setup_cloud_sync:
            try:
                config_manager.enable_cloud_sync(True)
                print_success("Cloud configuration sync enabled")

                # Enable auto-sync
                auto_sync = confirm_action("Enable automatic sync (recommended)?")
                if auto_sync:
                    config_manager.enable_auto_sync(True)
                    print_success("Automatic sync enabled")

            except Exception as e:
                print_warning("Cloud sync setup failed", str(e))
                print_info("You can enable it later with: agentcore-cli config sync enable")
        else:
            print_info("Skipped cloud sync setup")

        console.print()

    # Step 6: Authentication setup (optional)
    if not skip_cognito:
        print_step(6, "Authentication Setup", "Create Cognito resources for secure agent access.")

        setup_cognito = confirm_action("Set up Cognito authentication?")

        if setup_cognito:
            agent_name = prompt_input("Agent name for auth resources", default="default") or "default"

            try:
                print_info("Creating Cognito resources (this may take a moment)...")
                cognito_service = CognitoService(region=region)

                cognito_config = cognito_service.create_cognito_resources(
                    agent_name=agent_name,
                    environment=environment,
                    allow_self_registration=False,
                    email_verification_required=True,
                )

                if cognito_config:
                    # Add to environment config
                    config_manager.add_cognito_config(environment, cognito_config)
                    print_success("Cognito authentication configured")

                    if cognito_config.user_pool:
                        print_copyable_values({"User Pool ID": cognito_config.user_pool.user_pool_id})
                else:
                    print_error("Cognito setup failed")

            except Exception as e:
                print_warning("Cognito setup failed", str(e))
                print_info("You can set up authentication later with: agentcore-cli resources cognito create")
        else:
            print_info("Skipped authentication setup")

        console.print()

    # Save configuration
    try:
        config_manager.save_config()
        print_success("Configuration saved successfully")
    except Exception as e:
        print_error("Failed to save configuration", str(e))
        return

    # Final summary and next steps
    print_banner("Setup Complete!", emoji="🎉")

    summary_data = {
        "Environment": environment,
        "Region": region,
        "AWS Account": account_id or "Unknown",
        "Observability": "Enabled" if not skip_observability else "Skipped",
        "Cloud Sync": "Enabled"
        if not skip_sync and config_manager.config.global_resources.sync_config.cloud_config_enabled
        else "Disabled",
    }

    print_summary_box("Setup Summary", summary_data, style="green")

    # Next steps with organized command groups
    next_step_groups: list[tuple[str, list[tuple[str, str | None]]]] = [
        (
            "📦 Create your first agent",
            [("agentcore-cli agent create my-agent --dockerfile ./Dockerfile", "Create and deploy an agent")],
        ),
        (
            "🌍 Manage environments",
            [
                ("agentcore-cli env list", "List environments"),
                ("agentcore-cli env create staging", "Create staging environment"),
                ("agentcore-cli env use staging", "Switch environments"),
            ],
        ),
        (
            "🔧 Manage resources",
            [
                ("agentcore-cli resources ecr create my-agent", "Create ECR repository"),
                ("agentcore-cli resources iam create my-agent", "Create IAM role"),
            ],
        ),
        (
            "📊 Check status",
            [
                ("agentcore-cli env current", "Show current environment"),
                ("agentcore-cli config show", "Show configuration"),
            ],
        ),
        (
            "📚 Get help",
            [("agentcore-cli --help", "Main help"), ("agentcore-cli <command> --help", "Command-specific help")],
        ),
    ]

    for title, commands in next_step_groups:
        print_commands(commands, title=title)

    # Quick start guide
    quick_start_steps = [
        "Create a Dockerfile for your agent",
        "Run: agentcore agent create my-agent",
        "Test: agentcore agent invoke my-agent --prompt 'Hello!'",
    ]

    console.print("💡 [yellow bold]Quick Start Guide:[/yellow bold]")
    for i, step in enumerate(quick_start_steps, 1):
        console.print(f"   {i}. {step}")
    console.print()

    console.print("🎯 [bright_green bold]Happy agent building![/bright_green bold]")
    return


def run_automated_setup(
    region: str = "us-west-2",
    environment: str = "dev",
    skip_cognito: bool = False,
    skip_sync: bool = False,
    skip_observability: bool = False,
) -> None:
    """Run automated setup with minimal prompts."""

    print_info("Running automated setup...")

    # Validate AWS credentials
    if not validate_aws_credentials():
        print_error("AWS credentials required for setup")
        return

    # Get region
    if not region:
        region = get_aws_region() or "us-east-1"

    # Validate region
    is_valid, error_msg = validate_region(region)
    if not is_valid:
        print_error(error_msg)
        return

    print_info(f"Using region: {region}")
    print_info(f"Creating environment: {environment}")

    try:
        # Create environment
        success = config_manager.add_environment(environment, region)
        if success:
            config_manager.set_current_environment(environment)
            print_success(f"Environment '{environment}' created")
        else:
            if environment in config_manager.config.environments:
                config_manager.set_current_environment(environment)
                print_success(f"Using existing environment '{environment}'")
            else:
                print_error(f"Failed to create environment '{environment}'")
                return

        # Enable observability unless skipped
        if not skip_observability:
            try:
                validate_and_enable_transaction_search(region, interactive=False)
                print_success("Transaction Search enabled")
            except Exception as e:
                print_warning("Transaction Search setup skipped", str(e))

        # Enable cloud sync unless skipped
        if not skip_sync:
            config_manager.enable_cloud_sync(True)
            config_manager.enable_auto_sync(True)
            print_success("Cloud sync enabled")

        # Save configuration
        config_manager.save_config()

        account_id = get_aws_account_id()
        print_banner("Setup completed successfully!", emoji="✅")

        summary_data = {"Environment": environment, "Region": region, "Account": account_id or "Unknown"}
        print_summary_box("Automated Setup Summary", summary_data, style="green")

        console.print("🚀 [bold]Ready to create agents:[/bold]")
        console.print("   agentcore agent create my-agent --dockerfile ./Dockerfile")

        return

    except Exception as e:
        print_error("Setup failed", str(e))
        return


# Alias for backward compatibility
init_command = setup_cli

if __name__ == "__main__":
    setup_cli()
