"""Unified agent command for AgentCore CLI.

This module provides a streamlined agent lifecycle management that consolidates
functionality from agent, runtime, deploy, and container commands into a single
cohesive workflow optimized for the environment-first architecture.
"""

import click
import json
from datetime import datetime
from pathlib import Path
from tabulate import tabulate
from agentcore_cli.utils.rich_utils import (
    print_agent_response,
    print_agent_response_raw,
    extract_response_content,
    print_success,
    print_error,
    print_info,
)

from agentcore_cli.models.inputs import CreateAgentRuntimeInput, UpdateAgentRuntimeInput
from agentcore_cli.models.runtime import AgentRuntime, AgentRuntimeVersion, AgentRuntimeEndpoint
from agentcore_cli.models.base import AgentStatusType, AgentEndpointStatusType, NetworkModeType, ServerProtocolType
from agentcore_cli.services.agentcore import AgentCoreService
from agentcore_cli.services.containers import ContainerService
from agentcore_cli.services.ecr import ECRService
from agentcore_cli.services.iam import IAMService
from agentcore_cli.services.config import config_manager
from agentcore_cli.utils.aws_utils import get_aws_region
from agentcore_cli.utils.session_utils import generate_session_id
from agentcore_cli.utils.validation import validate_agent_name


@click.group("agent")
def unified_agent_cli() -> None:
    """Unified agent lifecycle management.

    This command provides a streamlined workflow for creating, deploying,
    and managing AgentCore agents with environment-first design.
    """
    pass


@unified_agent_cli.command("create")
@click.argument("name")
@click.option("--dockerfile", default="Dockerfile", help="Path to Dockerfile")
@click.option("--region", help="AWS region (defaults to current environment)")
@click.option("--environment", "-e", help="Environment (defaults to current)")
@click.option("--no-deploy", is_flag=True, help="Skip runtime deployment after creation")
@click.option("--image-tag", default="latest", help="Container image tag")
@click.option("--build-args", multiple=True, help="Docker build arguments (KEY=VALUE)")
def create_agent(
    name: str,
    dockerfile: str = "Dockerfile",
    region: str = "us-west-2",
    environment: str | None = None,
    no_deploy: bool = False,
    image_tag: str = "latest",
    build_args: tuple[str, ...] = (),
) -> None:
    """Create a new agent with container image and runtime.

    This is the easiest way to deploy an agent to AgentCore runtime with a single command.
    It performs the complete workflow:
    1. Validates agent name and Dockerfile
    2. Creates ECR repository if needed
    3. Builds and pushes container image
    4. Creates IAM role if needed
    5. Creates AgentCore runtime
    6. Deploys to the specified environment

    Examples:
      agentcore agent create my-chat-bot
      agentcore agent create data-processor --environment prod --image-tag v1.0.0
      agentcore agent create ml-agent --dockerfile ./docker/Dockerfile --build-args API_KEY=secret
    """
    # Validate agent name
    is_valid, error_msg = validate_agent_name(name)
    if not is_valid:
        click.echo(f"❌ Invalid agent name: {error_msg}", err=True)
        return

    # Validate Dockerfile exists
    dockerfile_path = Path(dockerfile)
    if not dockerfile_path.exists():
        click.echo(f"❌ Dockerfile not found: {dockerfile}", err=True)
        return

    # Get environment and region
    env_name = environment or config_manager.current_environment
    if not region:
        try:
            region = config_manager.get_region(env_name)
        except Exception:
            region = get_aws_region() or "us-east-1"

    click.echo(f"🚀 Creating agent '{name}' in environment '{env_name}'")
    click.echo(f"   Region: {region}")
    click.echo(f"   Dockerfile: {dockerfile}")
    click.echo(f"   Image Tag: {image_tag}")
    click.echo()

    try:
        # Check if agent already exists
        existing_runtime = config_manager.get_agent_runtime(name, env_name)
        if existing_runtime:
            click.echo(f"❌ Agent '{name}' already exists in environment '{env_name}'", err=True)
            click.echo("💡 Use 'agentcore agent update' to update an existing agent")
            return

        # Initialize services
        container_service = ContainerService(region=region)
        ecr_service = ECRService(region=region)
        iam_service = IAMService(region=region)
        agentcore_service = AgentCoreService(region=region)

        # Step 1: Create or get ECR repository
        click.echo("📦 Step 1: Setting up ECR repository...")
        ecr_success, repo_info, ecr_message = ecr_service.get_repository(name)

        if not ecr_success:
            click.echo(f"   Creating ECR repository '{name}'...")
            ecr_success, repo_info, ecr_message = ecr_service.create_repository(
                repository_name=name, environment=env_name, image_scanning=True
            )
            if not ecr_success:
                click.echo(f"❌ Failed to create ECR repository: {ecr_message}", err=True)
                return
            click.echo("   ✅ ECR repository created")
        else:
            click.echo("   ✅ ECR repository exists")

        if not repo_info:
            click.echo("❌ Failed to get ECR repository information", err=True)
            return

        ecr_uri = repo_info.repository_uri
        click.echo(f"   Repository: {ecr_uri}")

        # Step 2: Build and push container image
        click.echo()
        click.echo("🏗️  Step 2: Building and pushing container image...")

        # Build image
        build_args_dict = {}
        for arg in build_args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                build_args_dict[key] = value

        build_success = container_service.build_image(
            repo_name=name,
            tag=image_tag,
            dockerfile=str(dockerfile_path.absolute()),
            build_args=[f"{k}={v}" for k, v in build_args_dict.items()],
            use_cache=True,
        )

        if not build_success:
            click.echo("❌ Failed to build container image", err=True)
            return
        click.echo("   ✅ Container image built")

        # Push image
        push_result = container_service.push_image(name, image_tag, ecr_uri)
        if not push_result:
            click.echo("❌ Failed to push container image", err=True)
            return
        click.echo(f"   ✅ Image pushed: {ecr_uri}:{image_tag}")

        # Step 3: Create or get IAM role
        click.echo()
        click.echo("🔐 Step 3: Setting up IAM role...")

        role_config = iam_service.create_agent_role(agent_name=name, environment=env_name, role_name_prefix="agentcore")

        if not role_config:
            click.echo("❌ Failed to create IAM role", err=True)
            return

        click.echo(f"   ✅ IAM role created: {role_config.name}")
        role_arn = role_config.arn

        # Step 4: Create AgentCore runtime (unless no-deploy)
        if no_deploy:
            click.echo()
            click.echo("⏭️  Skipping runtime deployment (--no-deploy specified)")
        else:
            click.echo()
            click.echo("🤖 Step 4: Creating AgentCore runtime...")

            # Create runtime input
            runtime_input = CreateAgentRuntimeInput(
                name=name,
                container_uri=f"{ecr_uri}:{image_tag}",
                role_arn=role_arn,
                description=f"Agent runtime for {name}",
                network_mode=NetworkModeType.PUBLIC,
                protocol=ServerProtocolType.HTTP,
                environment_variables={},
            )

            # Create runtime
            creation_result = agentcore_service.create_agent_runtime(runtime_input)

            if not creation_result.success:
                click.echo(f"❌ Failed to create runtime: {creation_result.message}", err=True)
                return

            if not creation_result.runtime_id:
                click.echo("❌ Runtime ID not available from creation result", err=True)
                return

            click.echo(f"   ✅ Runtime created: {creation_result.runtime_id}")

            # Step 5: Save to configuration
            click.echo()
            click.echo("💾 Step 5: Saving configuration...")

            # Create runtime version
            runtime_version = AgentRuntimeVersion(
                version_id="V1",
                agent_runtime_id=creation_result.runtime_id,
                ecr_repository_name=name,
                image_tag=image_tag,
                status=AgentStatusType.READY,
                execution_role_arn=role_arn,
                created_at=datetime.now(),
                description=f"Initial version for {name}",
            )

            # Create default endpoint
            default_endpoint = AgentRuntimeEndpoint(
                name="DEFAULT",
                agent_runtime_id=creation_result.runtime_id,
                target_version="V1",
                status=AgentEndpointStatusType.READY,
                created_at=datetime.now(),
            )

            # Create agent runtime config
            agent_runtime = AgentRuntime(
                name=name,
                agent_runtime_id=creation_result.runtime_id,
                agent_runtime_arn=creation_result.runtime_arn,
                description=f"Agent runtime for {name}",
                latest_version="V1",
                primary_ecr_repository=name,
                versions={"V1": runtime_version},
                endpoints={"DEFAULT": default_endpoint},
                region=region,
                created_at=datetime.now(),
            )

            # Save to environment config
            success = config_manager.add_agent_runtime(name, agent_runtime, env_name)
            if not success:
                click.echo("⚠️  Failed to save agent configuration", err=True)
            else:
                click.echo("   ✅ Configuration saved")

            # Add global resources to config
            config_manager.add_ecr_repository(name, repo_info)
            config_manager.add_iam_role(role_config.name, role_config)

        # Success summary
        click.echo()
        click.echo("🎉 " + click.style(f"Agent '{name}' created successfully!", fg="green", bold=True))
        click.echo(f"   Environment: {env_name}")
        click.echo(f"   Region: {region}")
        click.echo(f"   ECR Repository: {ecr_uri}")
        if not no_deploy:
            click.echo(f"   Runtime ID: {creation_result.runtime_id}")
            click.echo(f"   Runtime ARN: {creation_result.runtime_arn}")

        click.echo()
        click.echo("🚀 " + click.style("Next steps:", bold=True))
        if no_deploy:
            click.echo(f"   • Deploy runtime: agentcore agent create {name} --environment {env_name}")
        else:
            click.echo(f"   • Test agent: agentcore agent invoke {name} --prompt 'Hello!'")
            click.echo(f"   • Check status: agentcore agent status {name}")
            click.echo(f"   • Update agent: agentcore agent update {name} --image-tag v2")

    except Exception as e:
        click.echo(f"❌ Agent creation failed: {str(e)}", err=True)
        return


@unified_agent_cli.command("update")
@click.argument("name")
@click.option("--image-tag", default="latest", help="New container image tag")
@click.option("--region", help="AWS region (defaults to current environment)")
@click.option("--environment", "-e", help="Environment (defaults to current)")
@click.option("--dockerfile", help="Path to Dockerfile (rebuilds if specified)")
@click.option("--build-args", multiple=True, help="Docker build arguments (KEY=VALUE)")
def update_agent(
    name: str,
    image_tag: str = "latest",
    region: str = "us-west-2",
    environment: str | None = None,
    dockerfile: str | None = None,
    build_args: tuple[str, ...] = (),
) -> None:
    """Update an existing agent with a new container version.

    This creates a new immutable version of the agent runtime.
    If dockerfile is specified, it rebuilds and pushes the image first.

    Examples:
      agentcore agent update my-agent --image-tag v2.0.0
      agentcore agent update my-agent --dockerfile ./Dockerfile --image-tag latest
    """
    # Get environment and region
    env_name = environment or config_manager.current_environment
    if not region:
        try:
            region = config_manager.get_region(env_name)
        except Exception:
            region = get_aws_region() or "us-east-1"

    click.echo(f"🔄 Updating agent '{name}' in environment '{env_name}'")
    click.echo(f"   New image tag: {image_tag}")
    click.echo()

    try:
        # Check if agent exists
        runtime = config_manager.get_agent_runtime(name, env_name)
        if not runtime:
            click.echo(f"❌ Agent '{name}' not found in environment '{env_name}'", err=True)
            env_config = config_manager.get_environment(env_name)
            if env_config.agent_runtimes:
                click.echo(f"Available agents: {', '.join(env_config.agent_runtimes.keys())}")
            else:
                click.echo("No agents found in this environment")
            click.echo(f"💡 Create it first: agentcore agent create {name}")
            return

        # Initialize services
        container_service = ContainerService(region=region)
        ecr_service = ECRService(region=region)
        agentcore_service = AgentCoreService(region=region)

        # Get ECR repository info
        ecr_success, repo_info, ecr_message = ecr_service.get_repository(runtime.primary_ecr_repository)
        if not ecr_success or not repo_info:
            click.echo(f"❌ ECR repository not found: {ecr_message}", err=True)
            return

        ecr_uri = repo_info.repository_uri

        # Rebuild image if dockerfile specified
        if dockerfile:
            dockerfile_path = Path(dockerfile)
            if not dockerfile_path.exists():
                click.echo(f"❌ Dockerfile not found: {dockerfile}", err=True)
                return

            click.echo("🏗️  Rebuilding container image...")

            # Parse build arguments
            build_args_dict = {}
            for arg in build_args:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    build_args_dict[key] = value

            # Build image
            build_success = container_service.build_image(
                repo_name=name,
                tag=image_tag,
                dockerfile=str(dockerfile_path.absolute()),
                build_args=[f"{k}={v}" for k, v in build_args_dict.items()],
                use_cache=True,
            )

            if not build_success:
                click.echo("❌ Failed to build container image", err=True)
                return

            # Push image
            push_result = container_service.push_image(name, image_tag, ecr_uri)
            if not push_result:
                click.echo("❌ Failed to push container image", err=True)
                return

            click.echo(f"   ✅ New image pushed: {ecr_uri}:{image_tag}")

        # Update runtime
        click.echo("🤖 Updating AgentCore runtime...")

        update_input = UpdateAgentRuntimeInput(
            agent_runtime_id=runtime.agent_runtime_id,
            container_uri=f"{ecr_uri}:{image_tag}",
            description=f"Updated agent runtime for {name} - {image_tag}",
        )

        update_result = agentcore_service.update_agent_runtime(update_input)

        if not update_result.success:
            click.echo(f"❌ Failed to update runtime: {update_result.message}", err=True)
            return

        click.echo(f"   ✅ Runtime updated to version: {update_result.version}")

        # Update configuration
        click.echo("💾 Updating configuration...")

        # Add new version to runtime config
        new_version = AgentRuntimeVersion(
            version_id=update_result.version,
            agent_runtime_id=runtime.agent_runtime_id,
            ecr_repository_name=runtime.primary_ecr_repository,
            image_tag=image_tag,
            status=AgentStatusType.READY,
            execution_role_arn=runtime.versions[runtime.latest_version].execution_role_arn,
            created_at=datetime.now(),
            description=f"Updated version for {name}",
        )

        runtime.versions[update_result.version] = new_version
        runtime.latest_version = update_result.version
        runtime.updated_at = datetime.now()

        config_manager.save_config()
        click.echo("   ✅ Configuration updated")

        # Success summary
        click.echo()
        click.echo("🎉 " + click.style(f"Agent '{name}' updated successfully!", fg="green", bold=True))
        click.echo(f"   Environment: {env_name}")
        click.echo(f"   New Version: {update_result.version}")
        click.echo(f"   Image: {ecr_uri}:{image_tag}")

        click.echo()
        click.echo("🚀 " + click.style("Next steps:", bold=True))
        click.echo(f"   • Test updated agent: agentcore agent invoke {name} --prompt 'Hello!'")
        click.echo(f"   • Update endpoint: agentcore agent endpoint update {name} --version {update_result.version}")

    except Exception as e:
        click.echo(f"❌ Agent update failed: {str(e)}", err=True)
        return


@unified_agent_cli.command("invoke")
@click.argument("name")
@click.option("--prompt", help="Prompt for the agent")
@click.option("--session-id", help="Session ID (auto-generated if not provided)")
@click.option("--region", help="AWS region (defaults to current environment)")
@click.option("--environment", "-e", help="Environment (defaults to current)")
@click.option("--endpoint", help="Endpoint name (defaults to DEFAULT)")
@click.option("--content-type", default="application/json", help="Content type for the request")
@click.option("--accept", default="application/json", help="Accept header for the response")
@click.option(
    "--raw-markdown", is_flag=True, help="Show raw markdown syntax instead of rendering (better for clipboard)"
)
@click.option("--pipe", is_flag=True, help="Output only the response content (no formatting, perfect for piping)")
def invoke_agent(
    name: str,
    prompt: str | None = None,
    session_id: str | None = None,
    region: str = "us-west-2",
    environment: str | None = None,
    endpoint: str | None = None,
    content_type: str = "application/json",
    accept: str = "application/json",
    raw_markdown: bool = False,
    pipe: bool = False,
) -> None:
    """Invoke an agent runtime with a prompt.

    This sends a prompt to the specified agent and returns the response.
    Perfect for testing your deployed agents.

    Examples:
      agentcore agent invoke my-chat-bot --prompt "Hello, how are you?"
      agentcore agent invoke data-processor --prompt "Process this data" --endpoint production
      agentcore agent invoke my-agent --prompt "Generate markdown" --raw-markdown
      agentcore agent invoke my-agent --prompt "Generate content" --pipe > output.txt
      agentcore agent invoke my-agent --prompt "Generate content" --pipe --raw-markdown | grep "##"
    """
    # Get environment and region
    env_name = environment or config_manager.current_environment
    if not region:
        try:
            region = config_manager.get_region(env_name)
        except Exception:
            region = get_aws_region() or "us-west-2"

    # Validate prompt
    if not prompt:
        # disallow the user from entering an empty string
        prompt = click.prompt("Enter prompt for the agent")
        if not prompt:
            if not pipe:
                click.echo("❌ Prompt cannot be empty", err=True)
            return

    # Generate session ID if not provided
    if not session_id:
        session_id = generate_session_id()

    # Use DEFAULT endpoint if not specified
    if not endpoint:
        endpoint = "DEFAULT"

    # Only show status messages if not in pipe mode
    if not pipe:
        click.echo(f"🤖 Invoking agent '{name}' in environment '{env_name}'")
        click.echo(f"   Endpoint: {endpoint}")
        click.echo(f"   Session ID: {session_id}")
        click.echo(f"   Prompt: {prompt}")
        click.echo()

    try:
        # Get agent runtime
        runtime = config_manager.get_agent_runtime(name, env_name)
        if not runtime:
            if not pipe:
                print_error(f"Agent '{name}' not found in environment '{env_name}'")
                env_config = config_manager.get_environment(env_name)
                if env_config.agent_runtimes:
                    print_info(f"Available agents: {', '.join(env_config.agent_runtimes.keys())}")
                else:
                    print_info("No agents found in this environment")
            return

        # Check if endpoint exists
        if endpoint not in runtime.endpoints:
            if not pipe:
                print_error(f"Endpoint '{endpoint}' not found for agent '{name}'")
                print_info(f"Available endpoints: {', '.join(runtime.endpoints.keys())}")
            return

        # Check if runtime ARN is available
        if not runtime.agent_runtime_arn:
            if not pipe:
                print_error("Agent runtime ARN not available. Runtime may not be deployed yet.")
                print_info(f"Deploy the runtime first with: agentcore agent update {name}")
            return

        # Create AgentCore service
        agentcore_service = AgentCoreService(region=region)

        # Invoke agent
        if not pipe:
            print_info("Sending request...")

        status_code, response = agentcore_service.invoke_agent_runtime(
            agent_runtime_arn=runtime.agent_runtime_arn,
            qualifier=endpoint,
            runtime_session_id=session_id,
            payload=prompt,
            content_type=content_type,
            accept=accept,
        )

        # Handle response based on mode
        if pipe:
            # Pipe mode: only output the content
            prefer_markdown = (
                not raw_markdown
            )  # If --raw-markdown is used with --pipe, don't prefer markdown extraction
            content = extract_response_content(response, prefer_markdown=prefer_markdown)
            click.echo(content)
        else:
            # Normal mode: full Rich formatting
            if status_code == 200:
                print_success("Response received")
                if raw_markdown:
                    print_agent_response_raw(response)
                else:
                    print_agent_response(response)
            else:
                print_error(f"Request failed with status: {status_code}")
                if raw_markdown:
                    print_agent_response_raw(response, title="Error Response")
                else:
                    print_agent_response(response, title="Error Response")
                return

    except Exception as e:
        if not pipe:
            print_error("Agent invocation failed", str(e))
        return


@unified_agent_cli.command("status")
@click.argument("name", required=False)
@click.option("--region", help="AWS region (defaults to current environment)")
@click.option("--environment", "-e", help="Environment (defaults to current)")
def agent_status(name: str | None = None, region: str = "us-west-2", environment: str | None = None) -> None:
    """Show the status of an agent or all agents.

    Displays current status, versions, endpoints, and other details.

    Examples:
      agentcore agent status                    # Show all agents
      agentcore agent status my-chat-bot       # Show specific agent
    """
    # Get environment and region
    env_name = environment or config_manager.current_environment
    if not region:
        try:
            region = config_manager.get_region(env_name)
        except Exception:
            region = get_aws_region() or "us-west-2"

    try:
        env_config = config_manager.get_environment(env_name)

        if name:
            # Show specific agent status
            runtime = env_config.agent_runtimes.get(name)
            if not runtime:
                click.echo(f"❌ Agent '{name}' not found in environment '{env_name}'", err=True)
                return

            click.echo(f"🤖 " + click.style(f"Agent Status: {name}", fg="bright_blue", bold=True))
            click.echo(f"   Environment: {env_name}")
            click.echo(f"   Region: {region}")
            click.echo(f"   Runtime ID: {runtime.agent_runtime_id}")
            click.echo(f"   Runtime ARN: {runtime.agent_runtime_arn or 'Not set'}")
            click.echo(f"   Latest Version: {runtime.latest_version}")
            click.echo(f"   ECR Repository: {runtime.primary_ecr_repository}")

            if runtime.versions:
                click.echo()
                click.echo(click.style("Versions:", bold=True))
                for version_id, version in runtime.versions.items():
                    status_icon = "✅" if version.status == AgentStatusType.READY else "⚠️"
                    click.echo(f"  {status_icon} {version_id} ({version.status.value})")
                    click.echo(f"     Image: {version.ecr_repository_name}:{version.image_tag}")
                    click.echo(
                        f"     Created: {version.created_at.strftime('%Y-%m-%d %H:%M') if version.created_at else 'Unknown'}"
                    )

            if runtime.endpoints:
                click.echo()
                click.echo(click.style("Endpoints:", bold=True))
                for endpoint_name, endpoint in runtime.endpoints.items():
                    status_icon = "✅" if endpoint.status == AgentEndpointStatusType.READY else "⚠️"
                    click.echo(f"  {status_icon} {endpoint_name} → {endpoint.target_version} ({endpoint.status.value})")

        else:
            # Show all agents in environment
            if not env_config.agent_runtimes:
                click.echo(f"📋 No agents in environment '{env_name}'")
                click.echo("💡 Create your first agent: agentcore agent create <name>")
                return

            click.echo(f"🤖 " + click.style(f"Agents in '{env_name}'", bold=True))
            click.echo()

            table_data = []
            for runtime_name, runtime in env_config.agent_runtimes.items():
                latest_version = runtime.versions.get(runtime.latest_version)
                status_icon = "✅" if latest_version and latest_version.status == AgentStatusType.READY else "⚠️"
                is_default = "⭐" if runtime_name == env_config.default_agent_runtime else ""

                table_data.append(
                    [
                        f"{status_icon} {runtime_name}{is_default}",
                        runtime.latest_version,
                        len(runtime.endpoints),
                        runtime.agent_runtime_id[:12] + "..." if runtime.agent_runtime_id else "N/A",
                    ]
                )

            headers = ["Agent", "Latest Version", "Endpoints", "Runtime ID"]
            click.echo(tabulate(table_data, headers=headers, tablefmt="simple"))

    except Exception as e:
        click.echo(f"❌ Failed to get agent status: {str(e)}", err=True)
        return


@unified_agent_cli.command("list")
@click.option("--region", help="AWS region (defaults to current environment)")
@click.option("--environment", "-e", help="Environment (defaults to current)")
def list_agents(region: str | None, environment: str | None) -> None:
    """List all agents in the current environment.

    Shows a summary of all deployed agents with their status and versions.
    """
    # Get environment and region
    env_name = environment or config_manager.current_environment
    if not region:
        try:
            region = config_manager.get_region(env_name)
        except Exception:
            region = get_aws_region() or "us-west-2"

    try:
        env_config = config_manager.get_environment(env_name)

        if not env_config.agent_runtimes:
            click.echo(f"📋 No agents found in environment '{env_name}'")
            click.echo("💡 Create your first agent: agentcore agent create <name>")
            return

        click.echo(f"📋 " + click.style(f"Agents in '{env_name}' ({len(env_config.agent_runtimes)})", bold=True))
        click.echo()

        for runtime_name, runtime in env_config.agent_runtimes.items():
            is_default = " ⭐" if runtime_name == env_config.default_agent_runtime else ""
            latest_version = runtime.versions.get(runtime.latest_version)
            status_icon = "✅" if latest_version and latest_version.status == AgentStatusType.READY else "⚠️"

            click.echo(f"{status_icon} " + click.style(f"{runtime_name}{is_default}", fg="bright_blue", bold=True))
            click.echo(f"   Latest Version: {runtime.latest_version}")
            click.echo(f"   Endpoints: {len(runtime.endpoints)}")
            click.echo(f"   ECR Repository: {runtime.primary_ecr_repository}")
            if latest_version:
                click.echo(f"   Image: {latest_version.ecr_repository_name}:{latest_version.image_tag}")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Failed to list agents: {str(e)}", err=True)
        return


@unified_agent_cli.command("delete")
@click.argument("name")
@click.option("--region", help="AWS region (defaults to current environment)")
@click.option("--environment", "-e", help="Environment (defaults to current)")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.option("--keep-ecr", is_flag=True, help="Keep ECR repository")
@click.option("--keep-iam", is_flag=True, help="Keep IAM role")
def delete_agent(
    name: str,
    region: str = "us-west-2",
    environment: str | None = None,
    force: bool = False,
    keep_ecr: bool = False,
    keep_iam: bool = False,
) -> None:
    """Delete an agent and optionally its AWS resources.

    ⚠️  WARNING: This will delete the agent runtime and optionally its ECR repository and IAM role.

    Examples:
      agentcore agent delete my-agent --force
      agentcore agent delete my-agent --keep-ecr --keep-iam
    """
    # Get environment and region
    env_name = environment or config_manager.current_environment
    if not region:
        try:
            region = config_manager.get_region(env_name)
        except Exception:
            region = get_aws_region() or "us-east-1"

    try:
        # Check if agent exists
        runtime = config_manager.get_agent_runtime(name, env_name)
        if not runtime:
            click.echo(f"❌ Agent '{name}' not found in environment '{env_name}'", err=True)
            return

        # Show what will be deleted
        click.echo(f"⚠️  " + click.style(f"Agent '{name}' Deletion", fg="red", bold=True))
        click.echo(f"   Environment: {env_name}")
        click.echo(f"   Runtime ID: {runtime.agent_runtime_id}")
        click.echo(f"   Versions: {len(runtime.versions)}")
        click.echo(f"   Endpoints: {len(runtime.endpoints)}")

        if not keep_ecr:
            click.echo(f"   ECR Repository: {runtime.primary_ecr_repository} (will be deleted)")
        if not keep_iam:
            click.echo(f"   IAM Role: agentcore-{name}-{env_name}-role (will be deleted)")

        click.echo()

        # Confirmation
        if not force:
            if not click.confirm(click.style(f"DELETE agent '{name}' and its resources?", fg="red")):
                click.echo("❌ Deletion cancelled")
                return

        click.echo(f"🗑️  Deleting agent '{name}'...")

        # Initialize services
        agentcore_service = AgentCoreService(region=region)
        ecr_service = ECRService(region=region)
        iam_service = IAMService(region=region)

        deleted_resources = []
        errors = []

        # Delete runtime
        if runtime.agent_runtime_id:
            click.echo("🤖 Deleting AgentCore runtime...")
            delete_result = agentcore_service.delete_agent_runtime(runtime.agent_runtime_id)
            if delete_result.success:
                deleted_resources.extend(delete_result.deleted_resources)
                click.echo("   ✅ Runtime deleted")
            else:
                errors.append(f"Failed to delete runtime: {delete_result.message}")

        # Delete ECR repository
        if not keep_ecr:
            click.echo("📦 Deleting ECR repository...")
            try:
                ecr_success, ecr_message = ecr_service.delete_repository(
                    runtime.primary_ecr_repository, env_name, force=True
                )
                if ecr_success:
                    deleted_resources.append(f"ECR Repository: {runtime.primary_ecr_repository}")
                    click.echo("   ✅ ECR repository deleted")
                else:
                    errors.append(f"Failed to delete ECR repository: {ecr_message}")
            except Exception as e:
                errors.append(f"ECR deletion error: {str(e)}")

        # Delete IAM role
        if not keep_iam:
            click.echo("🔐 Deleting IAM role...")
            try:
                iam_success, iam_message = iam_service.delete_agent_role(name, env_name)
                if iam_success:
                    deleted_resources.append(f"IAM Role: agentcore-{name}-{env_name}-role")
                    click.echo("   ✅ IAM role deleted")
                else:
                    errors.append(f"Failed to delete IAM role: {iam_message}")
            except Exception as e:
                errors.append(f"IAM deletion error: {str(e)}")

        # Remove from configuration
        click.echo("💾 Updating configuration...")
        success = config_manager.delete_agent_runtime(name, env_name)
        if success:
            click.echo("   ✅ Configuration updated")
        else:
            errors.append("Failed to update configuration")

        # Show results
        click.echo()
        if deleted_resources:
            click.echo("✅ " + click.style("Deleted successfully:", fg="green"))
            for resource in deleted_resources:
                click.echo(f"   • {resource}")

        if errors:
            click.echo()
            click.echo("❌ " + click.style("Errors encountered:", fg="red"))
            for error in errors:
                click.echo(f"   • {error}")

        if not errors:
            click.echo()
            click.echo("🎉 " + click.style(f"Agent '{name}' deleted successfully!", fg="green", bold=True))

        return

    except Exception as e:
        click.echo(f"❌ Agent deletion failed: {str(e)}", err=True)
        return


if __name__ == "__main__":
    unified_agent_cli()
