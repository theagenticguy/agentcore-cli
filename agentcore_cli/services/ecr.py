"""ECR service operations for AgentCore Platform CLI.

This module provides a service layer for AWS ECR operations using CloudFormation
to create and manage repositories for agent containers.
"""

from boto3.session import Session
from datetime import datetime
from loguru import logger
from pathlib import Path
from typing import Any

from agentcore_cli.models.resources import ECRRepository
from agentcore_cli.utils.cfn_utils import CFNService


class ECRService:
    """Service for AWS ECR operations."""

    def __init__(self, region: str, session: Session | None = None):
        """Initialize the ECR service.

        Args:
            region: AWS region for ECR operations.
            session: Boto3 session to use. If None, creates a new session.
        """
        self.region = region
        self.session = session or Session(region_name=region)
        self.cfn_service = CFNService(region)
        self.ecr_client = self.session.client("ecr", region_name=region)

    def create_repository(
        self,
        repository_name: str,
        environment: str | None = "dev",
        image_scanning: bool = True,
        lifecycle_policy_days: int = 30,
        tags: dict[str, str] | None = None,
    ) -> tuple[bool, ECRRepository | None, str]:
        """Create an ECR repository using CloudFormation.

        Args:
            repository_name: Name of the repository to create.
            environment: Environment name (default: dev).
            image_scanning: Whether to enable image scanning (default: True).
            lifecycle_policy_days: Number of days before untagged images are expired (default: 30).
            tags: Optional tags to apply to the repository.

        Returns:
            Tuple of (success, repository, message).
        """
        try:
            # Ensure environment has a valid value
            if environment is None:
                environment = "dev"

            # Get the template file path
            template_dir = Path(__file__).parent / "templates"
            template_path = template_dir / "ecr.cloudformation.yaml"

            if not template_path.exists():
                error_msg = f"Template file not found: {template_path}"
                logger.error(error_msg)
                return False, None, error_msg

            # Read the template file
            with open(template_path, encoding="utf-8") as f:
                template_body = f.read()

            # Create stack name
            stack_name = f"agentcore-{repository_name}-{environment}-ecr"

            # Set up parameters
            # Using Any type to avoid type errors with CloudFormation parameter types
            parameters: list[Any] = [
                {"ParameterKey": "RepositoryName", "ParameterValue": repository_name},
                {"ParameterKey": "Environment", "ParameterValue": environment},
                {"ParameterKey": "ImageScanningEnabled", "ParameterValue": str(image_scanning).lower()},
                {"ParameterKey": "LifecyclePolicyDays", "ParameterValue": str(lifecycle_policy_days)},
            ]

            # Create or update the stack
            logger.info(f"Creating/updating ECR repository '{repository_name}'...")
            success, message = self.cfn_service.create_update_stack(
                stack_name, template_body, parameters, wait_for_completion=True, timeout_minutes=15
            )

            if not success:
                error_msg = f"Failed to create/update ECR stack: {message}"
                logger.error(error_msg)
                return False, None, error_msg

            # Get stack outputs (stack is guaranteed to be complete now)
            outputs = self.cfn_service.get_stack_outputs(stack_name)

            # Extract repository URI and ARN from outputs
            repo_info = {}
            for output in outputs:
                if output.get("OutputKey") == "RepositoryUri":
                    repo_info["uri"] = output.get("OutputValue")
                elif output.get("OutputKey") == "RepositoryArn":
                    repo_info["arn"] = output.get("OutputValue")

            if "uri" in repo_info:
                # Extract registry_id from the repository URI
                # Format: registry_id.dkr.ecr.region.amazonaws.com/repo_name
                repo_uri = str(repo_info["uri"])
                registry_id = repo_uri.split(".")[0]  # Extract account ID

                # Create ECR repository model
                repository = ECRRepository(
                    name=repository_name,
                    registry_id=registry_id,
                    repository_uri=repo_uri,
                    region=self.region,
                    image_scanning_config=image_scanning,
                    image_tag_mutability="MUTABLE",  # Default
                    created_at=datetime.now(),
                    last_sync=datetime.now(),
                )

                logger.success(f"ECR repository created: {repository_name} ({repo_info['uri']})")
                return True, repository, f"Repository {repository_name} created successfully"
            else:
                logger.error("Failed to retrieve repository URI from stack outputs")
                return False, None, "Failed to retrieve repository URI from stack outputs"

        except Exception as e:
            error_msg = f"Failed to create ECR repository: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def delete_repository(
        self, repository_name: str, environment: str | None = "dev", force: bool = False
    ) -> tuple[bool, str]:
        """Delete an ECR repository by deleting the CloudFormation stack.

        Args:
            repository_name: Name of the repository to delete.
            environment: Environment name (default: dev).
            force: Whether to force deletion of the repository even if it contains images.

        Returns:
            Tuple of (success, message).
        """
        try:
            # Ensure environment has a valid value
            if environment is None:
                environment = "dev"
            # Check if repository exists
            try:
                self.ecr_client.describe_repositories(repositoryNames=[repository_name])

                # If force is True, delete all images first
                if force:
                    logger.info(f"Force delete requested, deleting all images in '{repository_name}'...")
                    try:
                        # Get image IDs
                        images = self.ecr_client.list_images(repositoryName=repository_name)
                        image_ids = images.get("imageIds", [])

                        if image_ids:
                            # Delete images
                            self.ecr_client.batch_delete_image(repositoryName=repository_name, imageIds=image_ids)
                            logger.info(f"Deleted {len(image_ids)} images from '{repository_name}'")
                    except Exception as img_err:
                        logger.warning(f"Error deleting images: {str(img_err)}")

            except self.ecr_client.exceptions.RepositoryNotFoundException:
                logger.warning(f"Repository '{repository_name}' not found")
            except Exception as e:
                logger.warning(f"Error checking repository existence: {str(e)}")

            # Create stack name
            stack_name = f"agentcore-{repository_name}-{environment}-ecr"

            # Check if stack exists
            try:
                self.cfn_service.get_stack_status(stack_name)
            except Exception:
                logger.warning(f"ECR stack for repository '{repository_name}' not found")
                return False, f"ECR stack for repository '{repository_name}' not found"

            # Delete the stack
            logger.info(f"Deleting ECR repository '{repository_name}'...")
            success, message = self.cfn_service.delete_stack(stack_name, wait_for_completion=True, timeout_minutes=10)

            if success:
                logger.success(f"ECR repository '{repository_name}' deleted successfully")
                return True, message
            else:
                logger.error(f"ECR repository deletion failed: {message}")
                return False, message

        except Exception as e:
            error_msg = f"Failed to delete ECR repository: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def get_repository(self, repository_name: str) -> tuple[bool, ECRRepository | None, str]:
        """Get details about an ECR repository.

        Args:
            repository_name: Name of the repository.

        Returns:
            Tuple of (success, repository, message).
        """
        try:
            # Get repository details
            response = self.ecr_client.describe_repositories(repositoryNames=[repository_name])
            repositories = response.get("repositories", [])

            if not repositories:
                return False, None, f"Repository '{repository_name}' not found"

            repo_data = repositories[0]

            # Create ECR repository model
            repo_uri = str(repo_data.get("repositoryUri", ""))
            registry_id = repo_uri.split(".")[0] if repo_uri else ""  # Extract account ID

            repository = ECRRepository(
                name=repository_name,
                registry_id=registry_id,
                repository_uri=repo_uri,
                region=self.region,
                image_scanning_config=repo_data.get("imageScanningConfiguration", {}).get("scanOnPush", False),
                image_tag_mutability=repo_data.get("imageTagMutability", "MUTABLE"),
                created_at=repo_data.get("createdAt"),
                last_sync=datetime.now(),
            )

            return True, repository, f"Repository '{repository_name}' found"

        except self.ecr_client.exceptions.RepositoryNotFoundException:
            return False, None, f"Repository '{repository_name}' not found"
        except Exception as e:
            error_msg = f"Failed to get ECR repository: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def list_repositories(self) -> tuple[bool, list[dict[str, Any]], str]:
        """List all ECR repositories in the account.

        Returns:
            Tuple of (success, repositories, message).
        """
        try:
            # List repositories
            response = self.ecr_client.describe_repositories()
            repos = response.get("repositories", [])

            # Convert to plain dictionaries for compatibility
            repositories = []
            for repo in repos:
                repositories.append(dict(repo))

            return True, repositories, f"Found {len(repositories)} repositories"

        except Exception as e:
            error_msg = f"Failed to list ECR repositories: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    def get_auth_token(self) -> tuple[bool, dict[str, Any] | None, str]:
        """Get an ECR authentication token.

        Returns:
            Tuple of (success, auth_data, message).
        """
        try:
            # Get auth token
            response = self.ecr_client.get_authorization_token()
            auth_data = response.get("authorizationData", [])

            if not auth_data:
                return False, None, "No authorization data returned"

            # Convert to plain dictionary for compatibility
            auth_dict = dict(auth_data[0])

            return True, auth_dict, "Authorization token retrieved"

        except Exception as e:
            error_msg = f"Failed to get ECR authorization token: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def set_lifecycle_policy(self, repository_name: str, max_days: int = 30) -> tuple[bool, str]:
        """Set a lifecycle policy on an ECR repository.

        Args:
            repository_name: Name of the repository.
            max_days: Maximum number of days to keep untagged images.

        Returns:
            Tuple of (success, message).
        """
        try:
            # Define a lifecycle policy to expire untagged images after max_days
            policy_text = f"""{{
                "rules": [
                    {{
                        "rulePriority": 1,
                        "description": "Expire untagged images older than {max_days} days",
                        "selection": {{
                            "tagStatus": "untagged",
                            "countType": "sinceImagePushed",
                            "countUnit": "days",
                            "countNumber": {max_days}
                        }},
                        "action": {{
                            "type": "expire"
                        }}
                    }}
                ]
            }}"""

            # Apply the policy
            self.ecr_client.put_lifecycle_policy(repositoryName=repository_name, lifecyclePolicyText=policy_text)

            return True, f"Lifecycle policy set on repository '{repository_name}'"

        except self.ecr_client.exceptions.RepositoryNotFoundException:
            return False, f"Repository '{repository_name}' not found"
        except Exception as e:
            error_msg = f"Failed to set lifecycle policy: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
