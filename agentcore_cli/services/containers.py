"""Container service operations for AgentCore CLI.

This module provides a service layer for container operations that were previously
duplicated across multiple command files.
"""

from boto3.session import Session
from loguru import logger
from typing import Any
from agentcore_cli.services.config import config_manager
from agentcore_cli.utils.command_executor import execute_command


class ContainerService:
    """Service for Docker image and container operations."""

    def __init__(self, region: str, session: Session | None = None):
        """Initialize the Container service.

        Args:
            region: AWS region for container operations.
            session: Boto3 session to use. If None, creates a new session.
        """
        self.region = region
        self.session = session

    def _build_docker_command(self, command: str, args: list[str], capture_output: bool = True) -> tuple[bool, str]:
        """Build and execute a Docker command with provided arguments.

        Args:
            command: The Docker command to execute (e.g., 'build', 'push').
            args: List of arguments for the Docker command.
            capture_output: Whether to capture command output.

        Returns:
            Tuple[bool, str]: Success status and command output or error message.
        """
        cmd = ["docker", command] + args
        try:
            # Always capture output with our utility but respect the log_output parameter
            returncode, stdout, stderr = execute_command(cmd, log_cmd=True, log_output=capture_output)

            if returncode == 0:
                return True, stdout
            else:
                return False, f"Command failed with error: {stderr}"
        except Exception as e:
            return False, f"Error executing Docker command: {str(e)}"

    def _tag_docker_image(self, source_tag: str, target_tag: str) -> tuple[bool, str]:
        """Tag a Docker image with a new tag.

        Args:
            source_tag: Source image tag.
            target_tag: Target image tag.

        Returns:
            Tuple[bool, str]: Success status and command output or error message.
        """
        return self._build_docker_command("tag", [source_tag, target_tag])

    def _push_docker_image(self, tag: str) -> tuple[bool, str]:
        """Push a Docker image to a registry.

        Args:
            tag: Image tag to push.

        Returns:
            Tuple[bool, str]: Success status and command output or error message.
        """
        return self._build_docker_command("push", [tag], capture_output=True)

    def _build_docker_image(
        self,
        tag: str,
        context: str = ".",
        platform: str = "linux/arm64",
        build_args: list[str] | None = None,
        no_cache: bool = False,
        quiet: bool = False,
    ) -> tuple[bool, str]:
        """Build a Docker image.

        Args:
            tag: Image tag (e.g., 'my-image:latest').
            context: Build context path.
            platform: Target platform (default: linux/arm64 for AgentCore).
            build_args: List of build args in the format ["KEY=VALUE", ...].
            no_cache: Whether to use cache or not.
            quiet: Whether to suppress output.

        Returns:
            Tuple[bool, str]: Success status and command output or error message.
        """
        # Start with buildx build command
        args = ["build", "--platform", platform, "-t", tag, "--load"]

        # Add build args
        if build_args:
            for arg in build_args:
                args.extend(["--build-arg", arg])

        # Add options
        if no_cache:
            args.append("--no-cache")

        if quiet:
            args.append("--quiet")

        # Add context at the end
        args.append(context)

        # Use buildx as the command
        return self._build_docker_command("buildx", args, capture_output=True)

    def _authenticate_ecr(self) -> bool:
        """Authenticate with ECR using AWS credentials.

        Returns:
            bool: True if authentication successful, False otherwise.
        """
        try:
            # Get account ID
            if self.session:
                sts_client = self.session.client("sts")
            else:
                import boto3

                sts_client = boto3.client("sts", region_name=self.region)

            account_id = sts_client.get_caller_identity()["Account"]

            # ECR Authentication
            auth_cmd = f"aws ecr get-login-password --region {self.region} | docker login --username AWS --password-stdin {account_id}.dkr.ecr.{self.region}.amazonaws.com"
            returncode, stdout, stderr = execute_command(auth_cmd, check=True)

            if returncode != 0:
                logger.error(f"ECR authentication failed: {stderr}")
                return False

            logger.success("ECR authentication successful")
            return True

        except Exception as e:
            logger.error(f"Failed to authenticate with ECR: {e}")
            return False

    def build_image(
        self,
        repo_name: str,
        tag: str = "latest",
        dockerfile: str = "Dockerfile",
        build_args: list[str] | None = None,
        platform: str = "linux/arm64",
        use_cache: bool = True,
    ) -> bool:
        """Build a Docker image for the agent.

        Args:
            repo_name: Name of the ECR repository (used for local image tagging).
            tag: Image tag.
            dockerfile: Path to Dockerfile.
            build_args: List of build arguments as key=value strings.
            platform: Target platform for the image (default: linux/arm64).
            use_cache: Whether to use Docker build cache.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Create a display tag for logging
            image_tag = f"{repo_name}:{tag}"

            logger.info(f"Building {platform} Docker image: '{image_tag}'")
            logger.info(f"Dockerfile: {dockerfile}")

            # Build Docker command directly
            cmd = ["docker", "buildx", "build", "--platform", platform, "-t", image_tag, "--load"]

            # Add build args
            if build_args:
                for arg in build_args:
                    cmd.extend(["--build-arg", arg])

            # Add cache option
            if not use_cache:
                cmd.append("--no-cache")

            # Add dockerfile if not default
            if dockerfile != "Dockerfile":
                cmd.extend(["-f", dockerfile])

            # Add context
            cmd.append(".")

            # Execute the build command using our utility function
            returncode, stdout, stderr = execute_command(cmd, check=False)

            if returncode == 0:
                logger.success(f"Docker image built successfully: {image_tag}")
                return True
            else:
                logger.error(f"Docker build failed with exit code: {returncode}")
                if stderr:
                    logger.error(f"Error details: {stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            return False

    def tag_image(self, source_tag: str, target_tag: str) -> bool:
        """Tag a Docker image with a new tag.

        Args:
            source_tag: Source image tag.
            target_tag: Target image tag.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            success, message = self._tag_docker_image(source_tag, target_tag)

            if success:
                logger.success(f"Docker image tagged as {target_tag}")
                return True
            else:
                logger.error(f"Failed to tag Docker image: {message}")
                return False
        except Exception as e:
            logger.error("Failed to tag Docker image", exception=e)
            return False

    def push_image(self, repo_name: str, tag: str, repo_uri: str, save_config: bool = True) -> str | None:
        """Push Docker image to ECR.

        Args:
            repo_name: Name of the ECR repository.
            tag: Image tag.
            repo_uri: Repository URI.
            save_config: Whether to save repository details to config.

        Returns:
            str: Full remote image URI or None on failure.
        """
        try:
            # Authenticate with ECR first
            if not self._authenticate_ecr():
                return None

            # Tag image with ECR URI
            local_image = f"{repo_name}:{tag}"

            # Debug logging to see what we're getting
            logger.info(f"DEBUG: repo_uri = '{repo_uri}'")
            logger.info(f"DEBUG: tag = '{tag}'")

            # Ensure repo_uri doesn't already contain a tag
            if ":" in repo_uri and not repo_uri.endswith(".amazonaws.com"):
                # If there's a colon and it's not just the domain part, strip the tag
                repo_uri_clean = repo_uri.rsplit(":", 1)[0]
                logger.info(f"DEBUG: Stripped existing tag from repo_uri: '{repo_uri}' -> '{repo_uri_clean}'")
                repo_uri = repo_uri_clean

            remote_image = f"{repo_uri}:{tag}"
            logger.info(f"DEBUG: final remote_image = '{remote_image}'")

            logger.info(f"Tagging image as {remote_image}...")
            if not self.tag_image(local_image, remote_image):
                return None

            # Push to ECR
            logger.info("Pushing image to ECR...")
            success, message = self._push_docker_image(remote_image)

            if not success:
                logger.error(f"Failed to push image to ECR: {message}")
                return None

            logger.success(f"Image pushed to ECR: {remote_image}")

            # Save to config
            if save_config:
                from ..models import ECRRepository
                from datetime import datetime

                # Extract registry_id and repository_uri from the remote image
                # remote_image format: registry_id.dkr.ecr.region.amazonaws.com/repo_name:tag
                registry_id = remote_image.split(".")[0]  # Extract account ID
                repo_uri_without_tag = remote_image.rsplit(":", 1)[0]  # Remove tag

                # Create ECR repository config with proper parameters
                ecr_config = ECRRepository(
                    name=repo_name,
                    registry_id=registry_id,
                    repository_uri=repo_uri_without_tag,
                    region=self.region,
                    image_scanning_config=True,  # Default to enabled
                    image_tag_mutability="MUTABLE",  # Default
                    available_tags={tag},  # Add the current tag
                    created_at=datetime.now(),
                    last_sync=datetime.now(),
                    last_push=datetime.now(),
                )

                # Add to global resources
                config_manager.add_ecr_repository(repo_name, ecr_config)

            return remote_image
        except Exception as e:
            logger.error("Failed to push image to ECR", exception=e)
            return None

    def validate_image(self, image_name: str) -> tuple[bool, str]:
        """Validate that a Docker image exists locally.

        Args:
            image_name: Name of the image to check.

        Returns:
            tuple: (exists, message)
        """
        try:
            # Execute the docker images command
            cmd = ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", image_name]
            returncode, stdout, stderr = execute_command(cmd, check=False)
            output = stdout.strip()

            # Check if the image exists
            if returncode == 0 and output:
                return True, f"Image {image_name} exists"
            else:
                return False, f"Image {image_name} does not exist locally"
        except Exception as e:
            return False, f"Error checking image: {str(e)}"

    def get_image_details(self, image_name: str) -> dict[str, Any] | None:
        """Get metadata about a local Docker image.

        Args:
            image_name: Name of the image to inspect.

        Returns:
            dict: Image metadata or None if not found.
        """
        try:
            # Execute the docker inspect command
            cmd = ["docker", "inspect", image_name]
            returncode, stdout, stderr = execute_command(cmd, check=False)

            if returncode != 0:
                # Image likely doesn't exist
                return None

            import json

            # Parse the JSON output - result is a list of one object
            image_data = json.loads(stdout)
            if image_data and len(image_data) > 0:
                return dict(image_data[0])
            return None
        except Exception as e:
            logger.error(f"Error getting image details: {e}")
            return None
