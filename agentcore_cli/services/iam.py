"""IAM service operations for AgentCore Platform CLI.

This module provides a service layer for AWS IAM operations using CloudFormation
to create and manage IAM roles for AgentCore agents.
"""

from boto3.session import Session
from datetime import datetime
from loguru import logger
from pathlib import Path
from typing import Any
import time

from agentcore_cli.models.resources import IAMRoleConfig
from agentcore_cli.utils.cfn_utils import CFNService


class IAMService:
    """Service for AWS IAM operations."""

    def __init__(self, region: str, session: Session | None = None):
        """Initialize the IAM service.

        Args:
            region: AWS region for IAM operations.
            session: Boto3 session to use. If None, creates a new session.
        """
        self.region = region
        self.session = session or Session(region_name=region)
        self.cfn_service = CFNService(region)
        self.iam_client = self.session.client("iam", region_name=region)

    def create_agent_role(
        self, agent_name: str, environment: str | None = "dev", role_name_prefix: str = "agentcore"
    ) -> IAMRoleConfig | None:
        """Create an IAM role for an AgentCore agent using CloudFormation.

        Args:
            agent_name: Name of the agent.
            environment: Environment name (default: dev).
            role_name_prefix: Prefix for the IAM role name (default: agentcore).

        Returns:
            Tuple of (success, role_config, message).
        """
        try:
            # Ensure environment has a valid value
            if environment is None:
                environment = "dev"

            # Get the template file path
            template_dir = Path(__file__).parent / "templates"
            template_path = template_dir / "iam.cloudformation.yaml"

            if not template_path.exists():
                error_msg = f"Template file not found: {template_path}"
                logger.error(error_msg)
                return None

            # Read the template file
            with open(template_path, encoding="utf-8") as f:
                template_body = f.read()

            # Create stack name
            stack_name = f"agentcore-{agent_name}-{environment}-iam"

            # Set up parameters
            # Using Any type to avoid type errors with CloudFormation parameter types
            parameters: list[Any] = [
                {"ParameterKey": "AgentName", "ParameterValue": agent_name},
                {"ParameterKey": "Environment", "ParameterValue": environment},
                {"ParameterKey": "RoleNamePrefix", "ParameterValue": role_name_prefix},
            ]

            # Create or update the stack
            logger.info(f"Creating/updating IAM role for agent '{agent_name}'...")
            self.cfn_service.create_update_stack(stack_name, template_body, parameters)

            # Wait for stack creation/update to complete
            logger.info("Waiting for IAM role creation to complete...")

            # Get stack outputs
            stack_status = self.cfn_service.get_stack_status(stack_name)
            while stack_status not in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
                logger.info(f"Waiting for IAM role creation to complete... {stack_status}")
                time.sleep(1)
                stack_status = self.cfn_service.get_stack_status(stack_name)
            outputs = self.cfn_service.get_stack_outputs(stack_name)

            # Extract role name and ARN from outputs
            role_info: dict[str, Any] = {}
            for output in outputs:
                if output.get("OutputKey") == "RoleName":
                    role_info["role_name"] = output.get("OutputValue")
                elif output.get("OutputKey") == "RoleArn":
                    role_info["role_arn"] = output.get("OutputValue")

            if "role_name" in role_info and "role_arn" in role_info:
                # Create IAM role config
                role_config = IAMRoleConfig(
                    name=str(role_info["role_name"]),
                    arn=str(role_info["role_arn"]),
                    region=self.region,
                    path="/service-role/",
                    description=f"Execution role for {agent_name} agent in {environment} environment",
                    created_at=datetime.now(),  # Use current time since CloudFormation doesn't provide creation time
                )

                logger.success(f"IAM role created: {role_info['role_name']} ({role_info['role_arn']})")
                return role_config
            else:
                logger.error("Failed to retrieve role information from stack outputs")
                return None

        except Exception as e:
            error_msg = f"Failed to create IAM role: {str(e)}"
            logger.error(error_msg)
            return None

    def delete_agent_role(self, agent_name: str, environment: str | None = "dev") -> tuple[bool, str]:
        """Delete an IAM role for an AgentCore agent by deleting the CloudFormation stack.

        Args:
            agent_name: Name of the agent.
            environment: Environment name (default: dev).

        Returns:
            Tuple of (success, message).
        """
        try:
            # Ensure environment has a valid value
            if environment is None:
                environment = "dev"

            # Create stack name
            stack_name = f"agentcore-{agent_name}-{environment}-iam"

            # Check if stack exists
            try:
                self.cfn_service.get_stack_status(stack_name)
            except Exception:
                logger.warning(f"IAM role stack for agent '{agent_name}' not found")
                return False, f"IAM role stack for agent '{agent_name}' not found"

            # Delete the stack
            logger.info(f"Deleting IAM role for agent '{agent_name}'...")
            self.cfn_service.delete_stack(stack_name)

            logger.success(f"IAM role deletion initiated for agent '{agent_name}'")
            return True, f"IAM role deletion initiated for agent '{agent_name}'"

        except Exception as e:
            error_msg = f"Failed to delete IAM role: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def get_role(self, role_name: str) -> tuple[bool, IAMRoleConfig | None, str]:
        """Get details for a specific IAM role.

        Args:
            role_name: Name of the IAM role.

        Returns:
            Tuple of (success, role_config, message).
        """
        try:
            # Get role details
            response = self.iam_client.get_role(RoleName=role_name)
            role_data = response.get("Role", {})

            if not role_data:
                return False, None, f"Role '{role_name}' not found"

            # Create IAM role config
            role_config = IAMRoleConfig(
                name=role_name,
                arn=str(role_data.get("Arn", "")),
                region=self.region,
                path=str(role_data.get("Path", "/")),
                description=str(role_data.get("Description", "")),
                created_at=role_data.get("CreateDate"),  # AWS API returns datetime objects directly
                # Cast to datetime | None to satisfy type checker
                updated_at=datetime.now() if role_data.get("LastModifiedDate") else None,
            )

            return True, role_config, f"Role '{role_name}' found"

        except self.iam_client.exceptions.NoSuchEntityException:
            return False, None, f"Role '{role_name}' not found"
        except Exception as e:
            error_msg = f"Failed to get IAM role: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def list_agent_roles(self, prefix: str = "agentcore") -> tuple[bool, list[dict[str, Any]], str]:
        """List all IAM roles for AgentCore agents.

        Args:
            prefix: Prefix for the IAM role name (default: agentcore).

        Returns:
            Tuple of (success, roles, message).
        """
        try:
            path_prefix = "/service-role/"
            roles: list[dict[str, Any]] = []

            # List roles with pagination
            paginator = self.iam_client.get_paginator("list_roles")
            for page in paginator.paginate(PathPrefix=path_prefix):
                for role in page.get("Roles", []):
                    role_name = role.get("RoleName", "")
                    if role_name.startswith(prefix):
                        roles.append(dict(role))

            return True, roles, f"Found {len(roles)} agent roles"

        except Exception as e:
            error_msg = f"Failed to list agent roles: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    def get_role_policy(self, role_name: str, policy_name: str) -> tuple[bool, dict[str, Any], str]:
        """Get a specific policy attached to an IAM role.

        Args:
            role_name: Name of the IAM role.
            policy_name: Name of the policy.

        Returns:
            Tuple of (success, policy_document, message).
        """
        try:
            # Get role policy
            response = self.iam_client.get_role_policy(RoleName=role_name, PolicyName=policy_name)

            # Convert policy document to dict if needed
            raw_policy: Any = response.get("PolicyDocument", {})

            # Convert to dict[str, Any] using a deep copy approach
            if isinstance(raw_policy, dict):
                # Create a new dict with explicit string keys and Any values
                result_dict: dict[str, Any] = {}
                for key, value in raw_policy.items():
                    result_dict[str(key)] = value
            else:
                # Parse JSON string to dict
                import json

                result_dict = json.loads(raw_policy) if raw_policy else {}

            return True, result_dict, f"Policy '{policy_name}' retrieved"

        except self.iam_client.exceptions.NoSuchEntityException:
            return False, {}, f"Policy '{policy_name}' not found for role '{role_name}'"
        except Exception as e:
            error_msg = f"Failed to get role policy: {str(e)}"
            logger.error(error_msg)
            return False, {}, error_msg

    def check_role_exists(self, role_name: str) -> bool:
        """Check if an IAM role exists.

        Args:
            role_name: Name of the IAM role to check.

        Returns:
            bool: True if the role exists, False otherwise.
        """
        try:
            self.iam_client.get_role(RoleName=role_name)
            return True
        except self.iam_client.exceptions.NoSuchEntityException:
            return False
        except Exception:
            return False
