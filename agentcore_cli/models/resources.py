"""Resource models for AgentCore Platform CLI.

This module defines models for AWS resources like IAM roles, ECR repositories, and Cognito configurations.
"""

from .base import BaseAgentCoreModel, ResourceBase
from datetime import datetime
from pydantic import Field, field_validator
from typing import Any


class IAMRoleConfig(ResourceBase):
    """IAM role configuration."""

    name: str = Field(description="Role name")
    arn: str = Field(description="Role ARN")
    path: str = Field(default="/", description="Role path")
    description: str | None = Field(default=None, description="Role description")
    assume_role_policy_document: dict[str, Any] | None = Field(default=None, description="Assume role policy")
    last_sync: datetime | None = Field(default=None, description="Last sync timestamp with AWS")


class ECRRepository(ResourceBase):
    """ECR repository configuration.

    Represents an Amazon ECR repository that can contain multiple image tags.
    Each AgentRuntimeVersion should reference this repository and specify an image tag.
    """

    name: str = Field(description="Repository name (e.g., 'my-chat-agent', 'my-data-processor')")
    registry_id: str = Field(description="AWS account ID that owns this repository")
    repository_uri: str = Field(
        description="Full repository URI without image tag (e.g., '123456789.dkr.ecr.us-east-1.amazonaws.com/my-agent')"
    )

    # Repository settings
    image_scanning_config: bool = Field(default=True, description="Whether images are scanned on push")
    image_tag_mutability: str = Field(default="MUTABLE", description="Image tag mutability: MUTABLE or IMMUTABLE")
    lifecycle_policy: dict[str, Any] | None = Field(default=None, description="Repository lifecycle policy")

    # Image tracking
    available_tags: set[str] = Field(default_factory=set, description="Set of available image tags in this repository")
    last_push: datetime | None = Field(default=None, description="Last image push timestamp")
    last_sync: datetime | None = Field(default=None, description="Last sync timestamp with AWS")

    @property
    def registry_url(self) -> str:
        """Get the ECR registry URL (without repository name)."""
        # Extract registry from repository_uri
        # Format: registry_id.dkr.ecr.region.amazonaws.com/repo_name
        if "/" in self.repository_uri:
            return self.repository_uri.split("/")[0]
        return self.repository_uri

    def get_image_uri(self, tag: str) -> str:
        """Get the full container image URI for a specific tag.

        Args:
            tag: Image tag (e.g., 'v1', 'latest', 'prod-2024-01-15')

        Returns:
            Full container URI: registry/repository:tag
        """
        return f"{self.repository_uri}:{tag}"

    def validate_tag_exists(self, tag: str) -> bool:
        """Check if an image tag exists in this repository."""
        return tag in self.available_tags

    @field_validator("repository_uri")
    @classmethod
    def validate_repository_uri(cls, v: str) -> str:
        """Validate ECR repository URI format."""
        if not v:
            raise ValueError("Repository URI cannot be empty")

        # Should match ECR pattern: account.dkr.ecr.region.amazonaws.com/repo-name
        import re

        ecr_pattern = r"^[0-9]+\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com\/[a-z0-9][a-z0-9._-]*$"
        if not re.match(ecr_pattern, v):
            raise ValueError(
                f"Repository URI '{v}' does not match ECR format: account.dkr.ecr.region.amazonaws.com/repository-name"
            )

        return v


class CognitoUserPool(BaseAgentCoreModel):
    """Cognito user pool configuration."""

    user_pool_id: str = Field(description="User pool ID")
    user_pool_name: str = Field(description="User pool name")
    user_pool_arn: str | None = Field(default=None, description="User pool ARN")
    client_id: str | None = Field(default=None, description="App client ID")
    client_secret: str | None = Field(default=None, description="App client secret")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    domain: str | None = Field(default=None, description="User pool domain")


class CognitoIdentityPool(BaseAgentCoreModel):
    """Cognito identity pool configuration."""

    identity_pool_id: str = Field(description="Identity pool ID")
    identity_pool_name: str = Field(description="Identity pool name")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    allow_unauthenticated_identities: bool = Field(
        default=False, description="Whether unauthenticated identities are allowed"
    )


class CognitoConfig(ResourceBase):
    """Cognito user pool and identity pool configuration."""

    user_pool: CognitoUserPool | None = Field(default=None, description="User pool configuration")
    identity_pool: CognitoIdentityPool | None = Field(default=None, description="Identity pool configuration")
    last_sync: datetime | None = Field(default=None, description="Last sync timestamp")
