"""AWS resource management commands for AgentCore Platform CLI.

This module provides commands for managing AWS resources including ECR repositories,
IAM roles, and Cognito authentication resources.
"""

import click
from tabulate import tabulate

from agentcore_cli.services.ecr import ECRService
from agentcore_cli.services.iam import IAMService
from agentcore_cli.services.cognito import CognitoService
from agentcore_cli.services.config import config_manager
from agentcore_cli.utils.validation import validate_agent_name
from agentcore_cli.utils.rich_utils import (
    print_success,
    print_error,
    print_info,
    print_warning,
    console,
    confirm_action,
    print_commands,
    print_step,
    print_summary_box,
)


@click.group()
def resources_group() -> None:
    """AWS resource management commands.

    Manage ECR repositories, IAM roles, and Cognito authentication resources
    across your environments.
    """
    pass


# ECR Repository Commands
@resources_group.group("ecr")
def ecr_group() -> None:
    """ECR repository management commands."""
    pass


@ecr_group.command("create")
@click.argument("name")
@click.option("--region", "-r", help="AWS region (defaults to current environment)")
@click.option("--image-scanning", is_flag=True, help="Enable image vulnerability scanning")
@click.option("--lifecycle-days", default=30, help="Days to retain untagged images")
@click.option("--environment", "-e", help="Environment tag (defaults to current)")
def create_ecr_repository(
    name: str, region: str | None, image_scanning: bool, lifecycle_days: int, environment: str | None
) -> None:
    """Create an ECR repository.

    Creates a new ECR repository for storing container images.
    The repository will be configured with appropriate security settings.

    Examples:
      agentcore-cli resources ecr create my-agent
      agentcore-cli resources ecr create my-agent --image-scanning --lifecycle-days 7
    """
    # Validate repository name
    is_valid, error_msg = validate_agent_name(name)
    if not is_valid:
        print_error("Invalid repository name", error_msg)
        return

    # Get region and environment
    if not region:
        try:
            region = config_manager.get_region(environment)
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-east-1"

    if not environment:
        environment = config_manager.current_environment

    print_step(1, "Creating ECR Repository", f"Setting up repository '{name}'")

    repo_data = {
        "Repository Name": name,
        "Region": region,
        "Environment": environment,
        "Image Scanning": "Enabled" if image_scanning else "Disabled",
        "Lifecycle Policy": f"{lifecycle_days} days for untagged images",
    }

    print_summary_box("Repository Configuration", repo_data)

    try:
        ecr_service = ECRService(region=region)

        # Create repository
        success, repo_info, message = ecr_service.create_repository(
            repository_name=name,
            environment=environment,
            image_scanning=image_scanning,
            lifecycle_policy_days=lifecycle_days,
        )

        if success and repo_info:
            print_success("ECR repository created successfully")
            print_info(f"URI: {repo_info.repository_uri}")

            # Add to global config
            config_manager.add_ecr_repository(name, repo_info)
            print_success("Repository added to configuration")

            console.print()
            next_steps: list[tuple[str, str | None]] = [
                (f"agentcore-cli container build {name}", "Build and push"),
                (f"AWS ECR > {name}", "View in console"),
            ]

            print_commands(next_steps, title="🎉 Next steps")
        else:
            print_error("Failed to create ECR repository", message)

    except Exception as e:
        print_error("Creation failed", str(e))


@ecr_group.command("list")
@click.option("--region", "-r", help="AWS region (defaults to current environment)")
@click.option("--environment", "-e", help="Filter by environment tag")
def list_ecr_repositories(region: str | None, environment: str | None) -> None:
    """List ECR repositories.

    Shows all ECR repositories in the specified region,
    optionally filtered by environment tag.
    """
    # Get region
    if not region:
        try:
            region = config_manager.get_region(environment)
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-east-1"

    console.print(f"📦 [bold]ECR repositories in region {region}[/bold]")
    if environment:
        print_info(f"Filtered by environment: {environment}")
    console.print()

    try:
        ecr_service = ECRService(region=region)

        # Get repositories from global config
        repositories = []
        if config_manager.config.global_resources and config_manager.config.global_resources.ecr_repositories:
            repositories = list(config_manager.config.global_resources.ecr_repositories.keys())

        if not repositories:
            print_info("No ECR repositories found in configuration")
            print_commands([("agentcore-cli resources ecr create <name>", "Create one")])
            return

        table_data = []
        for repo_name in repositories:
            try:
                success, repo_info, _ = ecr_service.get_repository(repo_name)
                if success and repo_info:
                    # Get image count and last push
                    image_count = len(repo_info.available_tags) if repo_info.available_tags else 0
                    last_push = repo_info.last_push.strftime("%Y-%m-%d") if repo_info.last_push else "Never"

                    table_data.append(
                        [
                            repo_name,
                            repo_info.registry_id,
                            image_count,
                            "Yes" if repo_info.image_scanning_config else "No",
                            last_push,
                        ]
                    )
                else:
                    table_data.append([repo_name, "Unknown", "?", "?", "Not found"])
            except Exception:
                table_data.append([repo_name, "Error", "?", "?", "Error"])

        if table_data:
            headers = ["Repository", "Registry ID", "Images", "Scanning", "Last Push"]
            console.print(tabulate(table_data, headers=headers, tablefmt="simple"))
        else:
            print_info("No repositories found")

    except Exception as e:
        print_error("Failed to list repositories", str(e))


@ecr_group.command("delete")
@click.argument("name")
@click.option("--region", "-r", help="AWS region (defaults to current environment)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.option("--environment", "-e", help="Environment (defaults to current)")
def delete_ecr_repository(name: str, region: str | None, force: bool, environment: str | None) -> None:
    """Delete an ECR repository.

    ⚠️  WARNING: This will permanently delete the repository and all its images.

    Examples:
      agentcore-cli resources ecr delete old-repo --force
    """
    # Get region and environment
    if not region:
        try:
            region = config_manager.get_region(environment)
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-east-1"

    if not environment:
        environment = config_manager.current_environment

    # Confirmation
    if not force:
        console.print(f"⚠️  [red bold]Repository '{name}' Deletion[/red bold]")

        deletion_data = {
            "Repository": name,
            "Region": region,
            "Action": "Permanently delete repository and ALL container images",
        }

        print_summary_box("Deletion Plan", deletion_data, style="red")
        console.print()

        if not confirm_action(f"DELETE repository '{name}' and all images?"):
            print_info("Deletion cancelled")
            return

    print_step(1, "Deleting ECR Repository", f"Removing repository '{name}'...")

    try:
        ecr_service = ECRService(region=region)

        # Delete repository
        success, message = ecr_service.delete_repository(name, environment, force=True)

        if success:
            print_success("ECR repository deleted successfully", name)

            # Remove from config
            if (
                config_manager.config.global_resources
                and name in config_manager.config.global_resources.ecr_repositories
            ):
                del config_manager.config.global_resources.ecr_repositories[name]
                config_manager.save_config()
                print_success("Repository removed from configuration")
        else:
            print_error("Failed to delete repository", message)

    except Exception as e:
        print_error("Deletion failed", str(e))


# IAM Role Commands
@resources_group.group("iam")
def iam_group() -> None:
    """IAM role management commands."""
    pass


@iam_group.command("create")
@click.argument("agent_name")
@click.option("--region", "-r", help="AWS region (defaults to current environment)")
@click.option("--role-prefix", default="agentcore", help="Role name prefix")
@click.option("--environment", "-e", help="Environment (defaults to current)")
def create_iam_role(agent_name: str, region: str | None, role_prefix: str, environment: str | None) -> None:
    """Create an IAM role for an agent.

    Creates an IAM role with appropriate permissions for AgentCore runtime execution.

    Examples:
      agentcore-cli resources iam create my-agent
      agentcore-cli resources iam create my-agent --role-prefix mycompany
    """
    # Validate agent name
    is_valid, error_msg = validate_agent_name(agent_name)
    if not is_valid:
        print_error("Invalid agent name", error_msg)
        return

    # Get region and environment
    if not region:
        try:
            region = config_manager.get_region(environment)
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-west-2"

    if not environment:
        environment = config_manager.current_environment

    role_name = f"{role_prefix}-{agent_name}-{environment}-role"

    print_step(1, "Creating IAM Role", f"Setting up role for agent '{agent_name}'")

    role_data = {"Agent Name": agent_name, "Role Name": role_name, "Environment": environment, "Region": region}

    print_summary_box("Role Configuration", role_data)

    try:
        iam_service = IAMService(region=region)

        # Create role
        role_config = iam_service.create_agent_role(
            agent_name=agent_name, environment=environment, role_name_prefix=role_prefix
        )

        if role_config:
            print_success("IAM role created successfully")
            print_info(f"ARN: {role_config.arn}")
            print_info(f"Role Name: {role_config.name}")

            # Add to global config
            config_manager.add_iam_role(role_config.name, role_config)
            print_success("Role added to configuration")

            console.print()
            console.print("🎉 [bold]Role includes permissions for:[/bold]")
            permissions = [
                "• Bedrock AgentCore execution",
                "• S3 read-only access",
                "• CloudWatch Logs full access",
                "• Bedrock invoke model permissions",
            ]

            for perm in permissions:
                console.print(f"   {perm}")
        else:
            print_error("Failed to create IAM role")

    except Exception as e:
        print_error("Creation failed", str(e))


@iam_group.command("list")
@click.option("--environment", "-e", help="Filter by environment")
def list_iam_roles(environment: str | None) -> None:
    """List IAM roles for agents.

    Shows all AgentCore IAM roles, optionally filtered by environment.
    """
    console.print("🔐 [bold]AgentCore IAM roles[/bold]")
    if environment:
        print_info(f"Filtered by environment: {environment}")
    console.print()

    try:
        # Get roles from global config
        roles = []
        if config_manager.config.global_resources and config_manager.config.global_resources.iam_roles:
            for role_name, role_config in config_manager.config.global_resources.iam_roles.items():
                if not environment or environment in role_name:
                    roles.append((role_name, role_config))

        if not roles:
            print_info("No IAM roles found in configuration")
            print_commands([("agentcore-cli resources iam create <agent-name>", "Create one")])
            return

        table_data = []
        for role_name, role_config in roles:
            # Extract environment from role name
            parts = role_name.split("-")
            env = parts[-2] if len(parts) >= 3 else "unknown"
            agent = parts[-3] if len(parts) >= 4 else "unknown"

            table_data.append([agent, env, role_name, role_config.arn.split("/")[-1] if role_config.arn else "Unknown"])

        headers = ["Agent", "Environment", "Role Name", "Role ARN"]
        console.print(tabulate(table_data, headers=headers, tablefmt="simple"))

    except Exception as e:
        print_error("Failed to list roles", str(e))


@iam_group.command("delete")
@click.argument("agent_name")
@click.option("--environment", "-e", help="Environment (defaults to current)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def delete_iam_role(agent_name: str, environment: str | None, force: bool) -> None:
    """Delete an IAM role for an agent.

    ⚠️  WARNING: This will permanently delete the IAM role.
    Ensure no agents are using this role before deletion.

    Examples:
      agentcore-cli resources iam delete my-agent --force
      agentcore-cli resources iam delete my-agent --environment staging
    """
    if not environment:
        environment = config_manager.current_environment

    # Confirmation
    if not force:
        console.print(f"⚠️  [red bold]IAM Role Deletion[/red bold]")

        deletion_data = {"Agent": agent_name, "Environment": environment, "Action": "Permanently delete the IAM role"}

        print_summary_box("Deletion Plan", deletion_data, style="red")
        console.print()

        if not confirm_action(f"DELETE IAM role for '{agent_name}' in '{environment}'?"):
            print_info("Deletion cancelled")
            return

    print_step(1, "Deleting IAM Role", f"Removing role for agent '{agent_name}'...")

    try:
        # Get region for IAM service
        try:
            region = config_manager.get_region(environment)
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-east-1"

        iam_service = IAMService(region=region)

        # Delete role
        success, message = iam_service.delete_agent_role(agent_name, environment)

        if success:
            print_success("IAM role deleted successfully")

            # Remove from config
            role_name = f"agentcore-{agent_name}-{environment}-role"
            if config_manager.config.global_resources and role_name in config_manager.config.global_resources.iam_roles:
                del config_manager.config.global_resources.iam_roles[role_name]
                config_manager.save_config()
                print_success("Role removed from configuration")
        else:
            print_error("Failed to delete role", message)

    except Exception as e:
        print_error("Deletion failed", str(e))


# Cognito Commands
@resources_group.group("cognito")
def cognito_group() -> None:
    """Cognito authentication resource management."""
    pass


@cognito_group.command("create")
@click.argument("agent_name")
@click.option("--region", "-r", help="AWS region (defaults to current environment)")
@click.option("--environment", "-e", help="Environment (defaults to current)")
@click.option("--allow-signup", is_flag=True, help="Allow self-registration")
@click.option("--email-verification", is_flag=True, default=True, help="Require email verification")
@click.option("--resource-prefix", default="agentcore", help="Resource name prefix")
def create_cognito_resources(
    agent_name: str,
    region: str | None,
    environment: str | None,
    allow_signup: bool,
    email_verification: bool,
    resource_prefix: str,
) -> None:
    """Create Cognito authentication resources.

    Creates a Cognito User Pool, User Pool Client, Identity Pool, and associated IAM roles
    for agent authentication.

    Examples:
      agentcore-cli resources cognito create my-agent
      agentcore-cli resources cognito create my-agent --allow-signup --email-verification
    """
    # Validate agent name
    is_valid, error_msg = validate_agent_name(agent_name)
    if not is_valid:
        print_error("Invalid agent name", error_msg)
        return

    # Get region and environment
    if not region:
        try:
            region = config_manager.get_region(environment)
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-east-1"

    if not environment:
        environment = config_manager.current_environment

    print_step(1, "Creating Cognito Resources", f"Setting up authentication for '{agent_name}'")

    cognito_data = {
        "Agent": agent_name,
        "Environment": environment,
        "Region": region,
        "Self-registration": "Enabled" if allow_signup else "Disabled",
        "Email verification": "Required" if email_verification else "Optional",
    }

    print_summary_box("Authentication Configuration", cognito_data)
    console.print()
    print_info("⏳ This may take a few minutes...")

    try:
        cognito_service = CognitoService(region=region)

        # Create Cognito resources
        cognito_config = cognito_service.create_cognito_resources(
            agent_name=agent_name,
            environment=environment,
            resource_name_prefix=resource_prefix,
            allow_self_registration=allow_signup,
            email_verification_required=email_verification,
        )

        if cognito_config:
            print_success("Cognito resources created successfully")
            console.print()
            console.print("📋 [bold]Created Resources:[/bold]")

            if cognito_config.user_pool:
                console.print(f"   User Pool ID: {cognito_config.user_pool.user_pool_id}")
                if cognito_config.user_pool.client_id:
                    console.print(f"   Client ID: {cognito_config.user_pool.client_id}")

            if cognito_config.identity_pool:
                console.print(f"   Identity Pool ID: {cognito_config.identity_pool.identity_pool_id}")

            # Add to environment config
            config_manager.add_cognito_config(environment, cognito_config)
            print_success("Cognito configuration saved")

            console.print()
            next_steps: list[tuple[str, str | None]] = [
                ("Integrate with your application using the User Pool Client ID", None),
                ("Configure authentication flows in your agent code", None),
                ("Test authentication in the AWS Cognito console", None),
            ]

            print_commands(next_steps, title="🎉 Next steps")
        else:
            print_error("Failed to create Cognito resources")

    except Exception as e:
        print_error("Creation failed", str(e))


@cognito_group.command("list")
@click.option("--environment", "-e", help="Filter by environment")
def list_cognito_resources(environment: str | None) -> None:
    """List Cognito authentication resources.

    Shows all Cognito resources configured for AgentCore agents.
    """
    console.print("🔑 [bold]Cognito authentication resources[/bold]")
    if environment:
        print_info(f"Filtered by environment: {environment}")
    console.print()

    try:
        # Get cognito configs from environments
        configs_found = False

        for env_name, env_config in config_manager.config.environments.items():
            if environment and env_name != environment:
                continue

            if hasattr(env_config, "cognito") and env_config.cognito:
                configs_found = True
                cognito = env_config.cognito

                console.print(f"🌍 [bright_blue bold]Environment: {env_name}[/bright_blue bold]")

                if cognito.user_pool:
                    console.print(f"   User Pool ID: {cognito.user_pool.user_pool_id}")
                    if cognito.user_pool.client_id:
                        console.print(f"   Client ID: {cognito.user_pool.client_id}")

                if cognito.identity_pool:
                    console.print(f"   Identity Pool ID: {cognito.identity_pool.identity_pool_id}")

                console.print()

        if not configs_found:
            print_info("No Cognito resources found")
            print_commands([("agentcore-cli resources cognito create <agent-name>", "Create them")])

    except Exception as e:
        print_error("Failed to list Cognito resources", str(e))


if __name__ == "__main__":
    resources_group()
