"""Cognito service operations for AgentCore Platform CLI.

This module provides a service layer for AWS Cognito operations using CloudFormation
to create and manage user pools and identity pools for agent authentication.
"""

from boto3.session import Session
from datetime import datetime
from loguru import logger
from pathlib import Path
from typing import Any

from agentcore_cli.models.resources import CognitoConfig, CognitoUserPool, CognitoIdentityPool
from agentcore_cli.utils.cfn_utils import CFNService


class CognitoService:
    """Service for AWS Cognito operations."""

    def __init__(self, region: str, session: Session | None = None):
        """Initialize the Cognito service.

        Args:
            region: AWS region for Cognito operations.
            session: Boto3 session to use. If None, creates a new session.
        """
        self.region = region
        self.session = session or Session(region_name=region)
        self.cfn_service = CFNService(region)
        self.cognito_idp_client = self.session.client("cognito-idp", region_name=region)
        self.cognito_identity_client = self.session.client("cognito-identity", region_name=region)

    def create_cognito_resources(
        self,
        agent_name: str,
        environment: str | None = "dev",
        resource_name_prefix: str = "agentcore",
        allow_self_registration: bool = False,
        email_verification_required: bool = True,
    ) -> CognitoConfig:
        """Create Cognito user pool and identity pool using CloudFormation.

        Args:
            agent_name: Name of the agent.
            environment: Environment name (default: dev).
            resource_name_prefix: Prefix for resource names (default: agentcore).
            allow_self_registration: Whether to allow users to self-register (default: False).
            email_verification_required: Whether to require email verification (default: True).

        Returns:
            CognitoConfig: Cognito configuration.
        """
        try:
            # Ensure environment has a valid value
            if environment is None:
                environment = "dev"

            # Get the template file path
            template_dir = Path(__file__).parent / "templates"
            template_path = template_dir / "cognito.cloudformation.yaml"

            if not template_path.exists():
                error_msg = f"Template file not found: {template_path}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # Read the template file
            with open(template_path, encoding="utf-8") as f:
                template_body = f.read()

            # Create stack name
            stack_name = f"agentcore-{agent_name}-{environment}-cognito"

            # Set up parameters
            # Using Any type to avoid type errors with CloudFormation parameter types
            parameters: list[Any] = [
                {"ParameterKey": "AgentName", "ParameterValue": agent_name},
                {"ParameterKey": "Environment", "ParameterValue": environment},
                {"ParameterKey": "ResourceNamePrefix", "ParameterValue": resource_name_prefix},
                {"ParameterKey": "AllowSelfRegistration", "ParameterValue": str(allow_self_registration).lower()},
                {
                    "ParameterKey": "EmailVerificationRequired",
                    "ParameterValue": str(email_verification_required).lower(),
                },
            ]

            # Create or update the stack
            logger.info(f"Creating/updating Cognito resources for agent '{agent_name}'...")
            success, message = self.cfn_service.create_update_stack(
                stack_name, template_body, parameters, wait_for_completion=True, timeout_minutes=20
            )

            if not success:
                raise Exception(f"Failed to create/update Cognito stack: {message}")

            # Get stack outputs (stack is guaranteed to be complete now)
            outputs = self.cfn_service.get_stack_outputs(stack_name)

            # Extract resource information from outputs
            cognito_info = {}
            for output in outputs:
                if output.get("OutputKey") == "UserPoolId":
                    cognito_info["user_pool_id"] = output.get("OutputValue")
                elif output.get("OutputKey") == "UserPoolClientId":
                    cognito_info["client_id"] = output.get("OutputValue")
                elif output.get("OutputKey") == "IdentityPoolId":
                    cognito_info["identity_pool_id"] = output.get("OutputValue")
                elif output.get("OutputKey") == "AuthenticatedUserRoleArn":
                    cognito_info["auth_role_arn"] = output.get("OutputValue")

            if "user_pool_id" in cognito_info and "identity_pool_id" in cognito_info:
                # Get additional user pool info
                user_pool_id = str(cognito_info["user_pool_id"])  # Ensure string type
                identity_pool_id = str(cognito_info["identity_pool_id"])  # Ensure string type

                user_pool_details = self.cognito_idp_client.describe_user_pool(UserPoolId=user_pool_id)
                identity_pool_details = self.cognito_identity_client.describe_identity_pool(
                    IdentityPoolId=identity_pool_id
                )

                # Create User Pool model
                user_pool = CognitoUserPool(
                    user_pool_id=user_pool_id,
                    user_pool_name=user_pool_details["UserPool"].get(
                        "Name", f"{resource_name_prefix}-{agent_name}-{environment}"
                    ),
                    user_pool_arn=user_pool_details["UserPool"].get("Arn"),
                    client_id=cognito_info.get("client_id", ""),  # Provide default value
                    created_at=user_pool_details["UserPool"].get("CreationDate"),
                )

                # Create Identity Pool model
                identity_pool = CognitoIdentityPool(
                    identity_pool_id=identity_pool_id,
                    identity_pool_name=identity_pool_details.get(
                        "IdentityPoolName", f"{resource_name_prefix}-{agent_name}-{environment}-identity"
                    ),
                    created_at=datetime.now(),  # Identity Pool doesn't provide creation date
                    allow_unauthenticated_identities=identity_pool_details.get("AllowUnauthenticatedIdentities", False),
                )

                # Create Cognito Config
                cognito_config = CognitoConfig(
                    region=self.region,
                    user_pool=user_pool,
                    identity_pool=identity_pool,
                    created_at=datetime.now(),
                    last_sync=datetime.now(),
                )

                logger.success(
                    f"Cognito resources created: User Pool ID: {user_pool.user_pool_id}, Identity Pool ID: {identity_pool.identity_pool_id}"
                )
                return cognito_config
            else:
                logger.error("Failed to retrieve Cognito resource information from stack outputs")
                raise Exception("Failed to retrieve Cognito resource information from stack outputs")

        except Exception as e:
            error_msg = f"Failed to create Cognito resources: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def delete_cognito_resources(self, agent_name: str, environment: str | None = "dev") -> tuple[bool, str]:
        """Delete Cognito resources by deleting the CloudFormation stack.

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
            stack_name = f"agentcore-{agent_name}-{environment}-cognito"

            # Check if stack exists
            try:
                self.cfn_service.get_stack_status(stack_name)
            except Exception:
                logger.warning(f"Cognito stack for agent '{agent_name}' not found")
                return False, f"Cognito stack for agent '{agent_name}' not found"

            # Delete the stack
            logger.info(f"Deleting Cognito resources for agent '{agent_name}'...")
            self.cfn_service.delete_stack(stack_name)

            logger.success(f"Cognito resources deletion initiated for agent '{agent_name}'")
            return True, f"Cognito resources deletion initiated for agent '{agent_name}'"

        except Exception as e:
            error_msg = f"Failed to delete Cognito resources: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def get_user_pool(self, user_pool_id: str) -> tuple[bool, CognitoUserPool | None, str]:
        """Get details for a specific Cognito user pool.

        Args:
            user_pool_id: ID of the user pool.

        Returns:
            Tuple of (success, user_pool, message).
        """
        try:
            # Get user pool details
            response = self.cognito_idp_client.describe_user_pool(UserPoolId=user_pool_id)
            user_pool_data = response.get("UserPool", {})

            if not user_pool_data:
                return False, None, f"User pool '{user_pool_id}' not found"

            # Get user pool client
            clients_response = self.cognito_idp_client.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=60)
            client_id = None
            client_secret = None

            # Find the first client (or specific client if needed)
            if clients_response.get("UserPoolClients"):
                client = clients_response["UserPoolClients"][0]
                client_id = client.get("ClientId")

                # If we have a client ID, get the client secret
                if client_id:
                    client_details = self.cognito_idp_client.describe_user_pool_client(
                        UserPoolId=user_pool_id, ClientId=client_id
                    )
                    client_secret = client_details.get("UserPoolClient", {}).get("ClientSecret")

            # Create user pool model
            user_pool = CognitoUserPool(
                user_pool_id=user_pool_id,
                user_pool_name=user_pool_data.get("Name", ""),
                user_pool_arn=user_pool_data.get("Arn"),
                client_id=client_id,
                client_secret=client_secret,
                created_at=user_pool_data.get("CreationDate"),
                domain=user_pool_data.get("Domain"),
            )

            return True, user_pool, f"User pool '{user_pool_id}' found"

        except self.cognito_idp_client.exceptions.ResourceNotFoundException:
            return False, None, f"User pool '{user_pool_id}' not found"
        except Exception as e:
            error_msg = f"Failed to get user pool: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def get_identity_pool(self, identity_pool_id: str) -> tuple[bool, CognitoIdentityPool | None, str]:
        """Get details for a specific Cognito identity pool.

        Args:
            identity_pool_id: ID of the identity pool.

        Returns:
            Tuple of (success, identity_pool, message).
        """
        try:
            # Get identity pool details
            response = self.cognito_identity_client.describe_identity_pool(IdentityPoolId=identity_pool_id)

            logger.debug(f"Identity pool details: {response}")
            if not response.get("IdentityPoolName"):
                return False, None, f"Identity pool '{identity_pool_id}' not found"

            # Create identity pool model
            identity_pool = CognitoIdentityPool(
                identity_pool_id=identity_pool_id,
                identity_pool_name=response.get("IdentityPoolName", ""),
                created_at=datetime.now(),  # Identity pool does not provide creation date
                allow_unauthenticated_identities=response.get("AllowUnauthenticatedIdentities", False),
            )

            return True, identity_pool, f"Identity pool '{identity_pool_id}' found"

        except self.cognito_identity_client.exceptions.ResourceNotFoundException:
            return False, None, f"Identity pool '{identity_pool_id}' not found"
        except Exception as e:
            error_msg = f"Failed to get identity pool: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def list_user_pools(self, name_filter: str | None = None) -> tuple[bool, list[dict[str, Any]], str]:
        """List all user pools in the account.

        Args:
            name_filter: Optional filter for user pool names.

        Returns:
            Tuple of (success, user_pools, message).
        """
        try:
            user_pools = []

            # List user pools with pagination - using simpler approach
            paginator = self.cognito_idp_client.get_paginator("list_user_pools")
            for page in paginator.paginate():
                for pool in page.get("UserPools", []):
                    # Apply name filter if provided
                    if name_filter and name_filter not in pool.get("Name", ""):
                        continue

                    user_pools.append(dict(pool))

            return True, user_pools, f"Found {len(user_pools)} user pools"

        except Exception as e:
            error_msg = f"Failed to list user pools: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    def list_identity_pools(self, max_results: int = 60) -> tuple[bool, list[dict[str, Any]], str]:
        """List all identity pools in the account.

        Args:
            max_results: Maximum number of results to return.

        Returns:
            Tuple of (success, identity_pools, message).
        """
        try:
            # List identity pools
            response = self.cognito_identity_client.list_identity_pools(
                MaxResults=int(max_results)
            )  # AWS SDK parameter name
            identity_pools = response.get("IdentityPools", [])

            # Convert to plain dictionaries for compatibility
            pools = []
            for pool in identity_pools:
                pools.append(dict(pool))

            return True, pools, f"Found {len(pools)} identity pools"

        except Exception as e:
            error_msg = f"Failed to list identity pools: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    def get_cognito_config_for_agent(
        self, agent_name: str, environment: str | None = "dev"
    ) -> tuple[bool, CognitoConfig | None, str]:
        """Get Cognito configuration for a specific agent.

        This will attempt to find user pools and identity pools that match the agent name
        and environment naming pattern.

        Args:
            agent_name: Name of the agent.
            environment: Environment name (default: dev).

        Returns:
            Tuple of (success, cognito_config, message).
        """
        try:
            # Ensure environment has a valid value
            if environment is None:
                environment = "dev"
            # Look for user pools matching the agent name pattern
            success, user_pools, _ = self.list_user_pools(f"{agent_name}-{environment}")

            if not success or not user_pools:
                return (
                    False,
                    None,
                    f"No Cognito resources found for agent '{agent_name}' in environment '{environment}'",
                )

            # Find the first matching user pool
            user_pool_id: str | None = None
            for pool in user_pools:
                name = pool.get("Name", "")
                if f"{agent_name}-{environment}" in name:
                    user_pool_id = pool.get("Id")
                    break

            if not user_pool_id:
                return False, None, f"No user pool found for agent '{agent_name}' in environment '{environment}'"

            # Get full user pool details
            success, user_pool, _ = self.get_user_pool(user_pool_id)
            if not success or not user_pool:
                return False, None, f"Failed to get details for user pool '{user_pool_id}'"

            # Look for identity pools matching the agent name pattern
            success, identity_pools, _ = self.list_identity_pools()

            identity_pool: CognitoIdentityPool | None = None
            for pool in identity_pools:
                name = pool.get("IdentityPoolName", "")
                if f"{agent_name}-{environment}" in name:
                    identity_pool_id = pool.get("IdentityPoolId")
                    if identity_pool_id:  # Check if not None
                        success, identity_pool, _ = self.get_identity_pool(identity_pool_id)
                    break

            # Create Cognito config
            cognito_config = CognitoConfig(
                region=self.region,
                user_pool=user_pool,
                identity_pool=identity_pool,
                created_at=user_pool.created_at or datetime.now(),
                last_sync=datetime.now(),
            )

            return True, cognito_config, "Cognito configuration retrieved successfully"

        except Exception as e:
            error_msg = f"Failed to get Cognito configuration: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def create_user(
        self, user_pool_id: str, username: str, password: str, email: str, temp_password: bool = True
    ) -> tuple[bool, str]:
        """Create a new user in a user pool.

        Args:
            user_pool_id: ID of the user pool.
            username: Username for the new user.
            password: Password for the new user.
            email: Email address for the new user.
            temp_password: Whether the password is temporary (default: True).

        Returns:
            Tuple of (success, message).
        """
        try:
            # Create user
            create_params: dict[str, Any] = {
                "UserPoolId": user_pool_id,
                "Username": username,
                "UserAttributes": [{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}],
            }

            # Add optional parameters based on conditions
            if temp_password:
                create_params["TemporaryPassword"] = password
                create_params["MessageAction"] = "SUPPRESS"

            self.cognito_idp_client.admin_create_user(**create_params)

            # If not temporary password, set the permanent password
            if not temp_password:
                self.cognito_idp_client.admin_set_user_password(
                    UserPoolId=user_pool_id, Username=username, Password=password, Permanent=True
                )

            return True, f"User '{username}' created successfully"

        except Exception as e:
            error_msg = f"Failed to create user: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def delete_user(self, user_pool_id: str, username: str) -> tuple[bool, str]:
        """Delete a user from a user pool.

        Args:
            user_pool_id: ID of the user pool.
            username: Username of the user to delete.

        Returns:
            Tuple of (success, message).
        """
        try:
            # Delete user
            self.cognito_idp_client.admin_delete_user(UserPoolId=user_pool_id, Username=username)
            return True, f"User '{username}' deleted successfully"

        except Exception as e:
            error_msg = f"Failed to delete user: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def list_users(self, user_pool_id: str) -> tuple[bool, list[dict[str, Any]], str]:
        """List all users in a user pool.

        Args:
            user_pool_id: ID of the user pool.

        Returns:
            Tuple of (success, users, message).
        """
        try:
            users = []

            # List users with pagination
            paginator = self.cognito_idp_client.get_paginator("list_users")
            for page in paginator.paginate(UserPoolId=user_pool_id):
                for user in page.get("Users", []):
                    users.append(dict(user))

            return True, users, f"Found {len(users)} users in user pool '{user_pool_id}'"

        except Exception as e:
            error_msg = f"Failed to list users: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    def check_user_pool_exists(self, user_pool_id: str) -> bool:
        """Check if a user pool exists.

        Args:
            user_pool_id: ID of the user pool to check.

        Returns:
            bool: True if the user pool exists, False otherwise.
        """
        try:
            self.cognito_idp_client.describe_user_pool(UserPoolId=user_pool_id)
            return True
        except self.cognito_idp_client.exceptions.ResourceNotFoundException:
            return False
        except Exception:
            return False

    def check_identity_pool_exists(self, identity_pool_id: str) -> bool:
        """Check if an identity pool exists.

        Args:
            identity_pool_id: ID of the identity pool to check.

        Returns:
            bool: True if the identity pool exists, False otherwise.
        """
        try:
            self.cognito_identity_client.describe_identity_pool(IdentityPoolId=identity_pool_id)
            return True
        except self.cognito_identity_client.exceptions.ResourceNotFoundException:
            return False
        except Exception:
            return False
