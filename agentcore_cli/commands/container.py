"""Container management commands for AgentCore Platform CLI.

This module provides commands for building, pushing, and managing Docker containers
with integrated ECR support.
"""

import click
from pathlib import Path

from agentcore_cli.services.containers import ContainerService
from agentcore_cli.services.ecr import ECRService
from agentcore_cli.services.config import config_manager
from agentcore_cli.models.inputs import ContainerBuildInput
from agentcore_cli.utils.validation import validate_agent_name
from agentcore_cli.utils.command_executor import execute_command
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
def container_group() -> None:
    """Container and Docker management commands.

    Build, tag, and push Docker containers to ECR repositories.
    Integrated with the environment-first architecture.
    """
    pass


@container_group.command("build")
@click.argument("name")
@click.option("--dockerfile", "-f", default="Dockerfile", help="Path to Dockerfile")
@click.option("--context", "-c", default=".", help="Build context directory")
@click.option("--tag", "-t", default="latest", help="Image tag")
@click.option("--no-cache", is_flag=True, help="Disable build cache")
@click.option("--build-arg", multiple=True, help="Build arguments (KEY=VALUE)")
@click.option("--region", help="AWS region (defaults to current environment)")
def build_container(
    name: str, dockerfile: str, context: str, tag: str, no_cache: bool, build_arg: tuple[str, ...], region: str | None
) -> None:
    """Build a Docker container image.

    Builds a Docker image for the specified agent name using the provided Dockerfile.
    The image is tagged with the agent name and specified tag.

    Examples:
      agentcore-cli container build my-agent
      agentcore-cli container build my-agent --dockerfile ./docker/Dockerfile --tag v1.0.0
      agentcore-cli container build my-agent --build-arg API_KEY=secret --no-cache
    """
    # Validate agent name
    is_valid, error_msg = validate_agent_name(name)
    if not is_valid:
        print_error("Invalid agent name", error_msg)
        return

    # Validate dockerfile exists
    dockerfile_path = Path(dockerfile)
    if not dockerfile_path.exists():
        print_error("Dockerfile not found", dockerfile)
        return

    # Validate context directory exists
    context_path = Path(context)
    if not context_path.exists():
        print_error("Build context directory not found", context)
        return

    # Get region
    if not region:
        try:
            region = config_manager.get_region()
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-east-1"

    print_step(1, "Building Container", f"Building container image for '{name}'")

    build_data = {
        "Agent": name,
        "Dockerfile": dockerfile,
        "Context": context,
        "Tag": tag,
        "Region": region,
        "Cache": "Disabled" if no_cache else "Enabled",
    }

    print_summary_box("Build Configuration", build_data)

    if build_arg:
        console.print()
        console.print("[bold]Build Arguments:[/bold]")
        for arg in build_arg:
            # Mask sensitive values
            if any(sensitive in arg.lower() for sensitive in ["key", "secret", "token", "password"]):
                key, _ = arg.split("=", 1) if "=" in arg else (arg, "")
                console.print(f"     {key}=***")
            else:
                console.print(f"     {arg}")

    console.print()

    try:
        # Parse build arguments
        build_args = {}
        for arg in build_arg:
            if "=" in arg:
                key, value = arg.split("=", 1)
                build_args[key] = value
            else:
                print_warning(f"Ignoring invalid build arg: {arg}")

        # Create build input
        build_input = ContainerBuildInput(
            ecr_repository_name=name,
            image_tag=tag,
            dockerfile_path=str(dockerfile_path.absolute()),
            build_context=str(context_path.absolute()),
            no_cache=no_cache,
            build_args=build_args,
        )

        # Initialize container service
        container_service = ContainerService(region=region)

        # Build the image
        success = container_service.build_image(
            repo_name=build_input.ecr_repository_name,
            tag=build_input.image_tag,
            dockerfile=build_input.dockerfile_path,
            build_args=[f"{k}={v}" for k, v in build_input.build_args.items()],
            platform=build_input.platform,
            use_cache=not build_input.no_cache,
        )

        if success:
            print_success("Container image built successfully")
            console.print()

            next_steps: list[tuple[str, str | None]] = [
                (f"agentcore-cli container push {name} --tag {tag}", "Push to ECR"),
                (f"agentcore-cli agent create {name}", "Create agent"),
                (f"docker images {name}", "List images"),
            ]

            print_commands(next_steps, title="🎉 Next steps")
            return
        else:
            print_error("Failed to build container image")
            return

    except Exception as e:
        print_error("Build failed", str(e))
        return


@container_group.command("push")
@click.argument("name")
@click.option("--tag", "-t", default="latest", help="Image tag to push")
@click.option("--region", help="AWS region (defaults to current environment)")
@click.option("--create-repo", is_flag=True, help="Create ECR repository if it doesn't exist")
def push_container(name: str, tag: str, region: str | None, create_repo: bool) -> None:
    """Push a container image to ECR.

    Pushes a locally built Docker image to the corresponding ECR repository.
    Requires the image to be built first with 'agentcore container build'.

    Examples:
      agentcore-cli container push my-agent
      agentcore-cli container push my-agent --tag v1.0.0
      agentcore-cli container push my-agent --create-repo
    """
    # Validate agent name
    is_valid, error_msg = validate_agent_name(name)
    if not is_valid:
        print_error("Invalid agent name", error_msg)
        return

    # Get region
    if not region:
        try:
            region = config_manager.get_region()
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-east-1"

    print_step(1, "Pushing Container", f"Pushing container image '{name}:{tag}' to ECR")
    print_info(f"Region: {region}")

    try:
        # Initialize services
        container_service = ContainerService(region=region)
        ecr_service = ECRService(region=region)

        # Check if ECR repository exists
        success, repo_info, message = ecr_service.get_repository(name)

        if not success:
            if create_repo:
                print_info(f"Creating ECR repository '{name}'...")
                success, repo_info, message = ecr_service.create_repository(name)
                if not success:
                    print_error("Failed to create ECR repository", message)
                    return
                print_success("ECR repository created", name)
            else:
                print_error("ECR repository not found", name)
                print_commands([("agentcore-cli container push --create-repo", "Create it first")])
                return

        # Get ECR URI
        ecr_uri = repo_info.repository_uri if repo_info else None
        if not ecr_uri:
            print_error("Could not determine ECR repository URI")
            return

        print_info(f"Target repository: {ecr_uri}")

        # Push the image
        pushed_uri = container_service.push_image(name, tag, ecr_uri)

        if pushed_uri:
            print_success("Image pushed successfully", pushed_uri)

            # Update config if agent runtime exists
            try:
                agent_runtime = config_manager.get_agent_runtime(name)
                if agent_runtime:
                    print_info("Updating agent runtime configuration...")
                    # Update the primary ECR repository reference
                    agent_runtime.primary_ecr_repository = name
                    config_manager.save_config()
                    print_success("Configuration updated")
            except Exception:
                print_warning("Failed to update agent runtime configuration")

            console.print()

            next_steps: list[tuple[str, str | None]] = [
                (f"agentcore-cli agent create {name}", "Deploy agent"),
                (f"agentcore-cli agent update {name} --image-tag {tag}", "Update runtime"),
                (f"AWS ECR > {name}", "View in console"),
            ]

            print_commands(next_steps, title="🎉 Next steps")
            return
        else:
            print_error("Failed to push image to ECR")
            return

    except Exception as e:
        print_error("Push failed", str(e))
        return


@container_group.command("list")
@click.option("--repository", "-r", help="Filter by ECR repository name")
@click.option("--region", help="AWS region (defaults to current environment)")
def list_images(repository: str | None, region: str | None) -> None:
    """List container images in ECR repositories.

    Shows available images and tags in ECR repositories associated with
    the current environment.

    Examples:
      agentcore-cli container list
      agentcore-cli container list --repository my-agent
    """
    # Get region
    if not region:
        try:
            region = config_manager.get_region()
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-east-1"

    console.print(f"📦 [bold]Container images in region {region}[/bold]")
    console.print()

    try:
        ecr_service = ECRService(region=region)

        # Get repositories to check
        repositories = []
        if repository:
            repositories = [repository]
        else:
            # Get repositories from global config
            if config_manager.config.global_resources and config_manager.config.global_resources.ecr_repositories:
                repositories = list(config_manager.config.global_resources.ecr_repositories.keys())

        if not repositories:
            print_info("No ECR repositories found in configuration")
            print_commands([("agentcore-cli container push <name> --create-repo", "Create one")])
            return

        for repo_name in repositories:
            success, repo_info, message = ecr_service.get_repository(repo_name)

            if success and repo_info:
                console.print(f"🗂️  [bright_blue bold]{repo_name}[/bright_blue bold]")
                console.print(f"   URI: {repo_info.repository_uri}")
                console.print(f"   Registry: {repo_info.registry_id}")

                if repo_info.available_tags:
                    tags_list = sorted(repo_info.available_tags)
                    console.print(f"   Tags: {', '.join(tags_list[:10])}")
                    if len(tags_list) > 10:
                        console.print(f"         ... and {len(tags_list) - 10} more")
                else:
                    console.print("   Tags: No images pushed yet")

                if repo_info.last_push:
                    console.print(f"   Last Push: {repo_info.last_push.strftime('%Y-%m-%d %H:%M')}")

                console.print()
            else:
                print_warning(f"Repository '{repo_name}' not found in AWS", message)

    except Exception as e:
        print_error("Failed to list images", str(e))


@container_group.command("pull")
@click.argument("name")
@click.option("--tag", "-t", default="latest", help="Image tag to pull")
@click.option("--region", help="AWS region (defaults to current environment)")
def pull_container(name: str, tag: str, region: str | None) -> None:
    """Pull a container image from ECR.

    Downloads a container image from ECR to the local Docker environment.
    Useful for testing or running images locally.

    Examples:
      agentcore-cli container pull my-agent
      agentcore-cli container pull my-agent --tag v1.0.0
    """
    # Validate agent name
    is_valid, error_msg = validate_agent_name(name)
    if not is_valid:
        print_error("Invalid agent name", error_msg)
        return

    # Get region
    if not region:
        try:
            region = config_manager.get_region()
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-west-2"

    print_step(1, "Pulling Container", f"Pulling container image '{name}:{tag}' from ECR")
    print_info(f"Region: {region}")

    try:
        # Initialize services
        container_service = ContainerService(region=region)
        ecr_service = ECRService(region=region)

        # Get ECR repository info
        success, repo_info, message = ecr_service.get_repository(name)
        if not success or not repo_info:
            print_error("ECR repository not found", f"{name}: {message}")
            return

        ecr_uri = repo_info.repository_uri
        full_image = f"{ecr_uri}:{tag}"

        print_info(f"Source: {full_image}")

        # Pull the image using Docker CLI directly
        try:
            # Authenticate with ECR first
            if not container_service._authenticate_ecr():
                print_error("Failed to authenticate with ECR")
                return

            # Pull the image
            returncode, stdout, stderr = execute_command(["docker", "pull", full_image], log_cmd=True, log_output=False)

            if returncode == 0:
                print_success("Image pulled successfully", full_image)
                console.print()

                commands: list[tuple[str, str | None]] = [
                    (f"docker run -it {name}:{tag}", "Run locally"),
                    (f"docker inspect {name}:{tag}", "Inspect"),
                    (f"docker rmi {name}:{tag}", "Remove"),
                ]

                print_commands(commands, title="🎉 Available commands")
                return
            else:
                print_error("Failed to pull image from ECR")
                if stderr:
                    print_info(f"Error: {stderr.strip()}")
                return
        except Exception as e:
            print_error("Pull failed", str(e))
            return

    except Exception as e:
        print_error("Pull failed", str(e))
        return


@container_group.command("remove")
@click.argument("name")
@click.option("--tag", "-t", help="Specific tag to remove (default: remove all tags)")
@click.option("--local-only", is_flag=True, help="Remove only local images, keep ECR")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def remove_container(name: str, tag: str | None, local_only: bool, force: bool) -> None:
    """Remove container images.

    Removes container images from local Docker and optionally from ECR.
    Use --local-only to keep ECR images intact.

    Examples:
        agentcore-cli container remove my-agent --local-only
        agentcore-cli container remove my-agent --tag latest
        agentcore-cli container remove my-agent --force
    """
    # Validate agent name
    is_valid, error_msg = validate_agent_name(name)
    if not is_valid:
        print_error("Invalid agent name", error_msg)
        return

    print_step(1, "Removing Container", f"Removing container images for '{name}'")

    removal_data = {
        "Agent": name,
        "Tag": tag if tag else "All tags",
        "Location": "Local only (ECR preserved)" if local_only else "Local and ECR",
    }

    print_summary_box("Removal Configuration", removal_data)

    # Confirmation
    if not force:
        console.print()
        if local_only:
            message = f"Remove local images for '{name}'?"
        else:
            message = f"Remove ALL images for '{name}' (local and ECR)?"

        if not confirm_action(message):
            print_info("Removal cancelled")
            return

    try:
        # Get region for services
        try:
            region = config_manager.get_region()
        except Exception:
            from agentcore_cli.utils.aws_utils import get_aws_region

            region = get_aws_region() or "us-west-2"

        removed_items = []
        errors = []

        # Remove local images using Docker CLI directly
        print_info("🐳 Removing local Docker images...")
        try:
            if tag:
                # Remove specific tag
                returncode, stdout, stderr = execute_command(
                    ["docker", "rmi", f"{name}:{tag}"], log_cmd=True, log_output=False
                )
                if returncode == 0:
                    removed_items.append(f"Local image: {name}:{tag}")
                else:
                    errors.append(f"Failed to remove local image: {name}:{tag}")
            else:
                # Remove all tags for this name
                returncode, stdout, stderr = execute_command(
                    ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", name], log_cmd=True, log_output=False
                )

                if returncode == 0:
                    local_images = stdout.strip().split("\n")
                    for image in local_images:
                        if image.strip() and image.strip() != f"{name}:<none>":
                            remove_returncode, remove_stdout, remove_stderr = execute_command(
                                ["docker", "rmi", image.strip()], log_cmd=True, log_output=False
                            )
                            if remove_returncode == 0:
                                removed_items.append(f"Local image: {image.strip()}")
                            else:
                                errors.append(f"Failed to remove local image: {image.strip()}")
        except Exception as e:
            errors.append(f"Local image removal error: {str(e)}")

        # Remove ECR images if not local-only
        if not local_only:
            try:
                ecr_service = ECRService(region=region)
                print_info("☁️  Removing ECR images...")

                if tag:
                    # For specific tags, we'd need to implement ECR image deletion
                    # For now, suggest using AWS CLI or console
                    print_warning("ECR tag deletion not implemented. Use AWS CLI:")
                    console.print(f"   aws ecr batch-delete-image --repository-name {name} --image-ids imageTag={tag}")
                    errors.append(f"ECR tag deletion not implemented: {name}:{tag}")
                else:
                    # Remove entire repository
                    current_env = config_manager.current_environment
                    success, message = ecr_service.delete_repository(name, current_env, force=True)
                    if success:
                        removed_items.append(f"ECR repository: {name}")
                    else:
                        errors.append(f"Failed to remove ECR repository: {message}")

            except Exception as e:
                errors.append(f"ECR removal error: {str(e)}")

        # Show results
        console.print()
        if removed_items:
            print_success("Removed successfully")
            for item in removed_items:
                console.print(f"   • {item}")

        if errors:
            console.print()
            print_error("Errors encountered")
            for error in errors:
                console.print(f"   • {error}")

        if removed_items and not errors:
            console.print()
            print_success("Container removal completed successfully")
        elif not removed_items and not errors:
            print_info("No images found to remove")

    except Exception as e:
        print_error("Removal failed", str(e))


if __name__ == "__main__":
    container_group()
