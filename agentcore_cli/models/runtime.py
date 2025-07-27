"""Runtime models for AgentCore Platform CLI.

This module defines models related to agent runtimes, their versions, and endpoints.
"""

from .base import (
    AgentEndpointStatusType,
    AgentStatusType,
    BaseAgentCoreModel,
    NetworkModeType,
    ResourceBase,
    ServerProtocolType,
)
from datetime import datetime
from pydantic import Field, field_validator, model_validator, ConfigDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .resources import ECRRepository


class AgentRuntimeVersion(BaseAgentCoreModel):
    """A specific version of an agent runtime.

    Each version references a specific ECR repository and image tag.
    The container URI is constructed from the repository + tag combination.
    """

    version_id: str = Field(description="Version identifier (e.g., 'V1', 'V2')")
    agent_runtime_id: str = Field(description="Runtime ID this version belongs to")

    # ECR Image Reference
    ecr_repository_name: str = Field(
        description="Name of the ECR repository (must exist in global_resources.ecr_repositories)"
    )
    image_tag: str = Field(
        description="Docker image tag in the ECR repository (e.g., 'v1', 'latest', 'prod-2024-01-15')"
    )

    # Runtime Configuration
    status: AgentStatusType = Field(description="Status of this runtime version")
    created_at: datetime | None = Field(default=None, description="When this version was created")
    network_mode: NetworkModeType = Field(default=NetworkModeType.PUBLIC, description="Network mode for this version")
    protocol: ServerProtocolType = Field(default=ServerProtocolType.HTTP, description="Protocol type for this version")
    environment_variables: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for this version"
    )
    execution_role_arn: str = Field(description="IAM role ARN used for this version")
    description: str | None = Field(default=None, description="Description of this version")
    failure_reason: str | None = Field(
        default=None, description="Reason for failure if status is CREATE_FAILED or UPDATE_FAILED"
    )
    updated_at: datetime | None = Field(default=None, description="When this version was last updated")

    model_config = ConfigDict(frozen=False)  # Allow updates for status changes, but versions are conceptually immutable

    @property
    def container_uri(self) -> str:
        """Get the full container URI by combining repository and tag.

        Note: This requires access to the ECR repository configuration to build the full URI.
        Use get_container_uri() method with repository config for the complete URI.
        """
        return f"<repository_uri>:{self.image_tag}"

    def get_container_uri(self, ecr_repository: "ECRRepository") -> str:
        """Get the full container URI using the ECR repository configuration.

        Args:
            ecr_repository: ECR repository configuration

        Returns:
            Full container URI: registry/repository:tag
        """
        return ecr_repository.get_image_uri(self.image_tag)

    @property
    def short_version(self) -> str:
        """Get a shortened version of the version ID for display."""
        # AWS AgentCore uses format like 'V1', 'V2', etc.
        # Handle various possible formats for backward compatibility
        if self.version_id.startswith("version-"):
            return "V" + self.version_id.replace("version-", "")
        elif self.version_id.lower().startswith("v"):
            return self.version_id.upper()
        else:
            # If it's just a number or other format, prefix with V
            return f"V{self.version_id}"

    @property
    def is_immutable(self) -> bool:
        """Check if this version is in an immutable state.

        According to AWS documentation, versions are immutable once created,
        but status can change during creation/update process.
        """
        return self.status in {AgentStatusType.READY, AgentStatusType.CREATE_FAILED, AgentStatusType.UPDATE_FAILED}


class AgentRuntimeEndpoint(BaseAgentCoreModel):
    """An endpoint for accessing a specific version of an agent runtime."""

    name: str = Field(description="Endpoint name (e.g., 'DEFAULT', 'prod', 'dev')")
    agent_runtime_id: str = Field(description="Runtime ID this endpoint belongs to")
    target_version: str = Field(description="Version identifier this endpoint points to")
    status: AgentEndpointStatusType = Field(description="Current endpoint status")
    description: str | None = Field(default=None, description="Endpoint description")
    created_at: datetime | None = Field(default=None, description="When this endpoint was created")
    updated_at: datetime | None = Field(default=None, description="When this endpoint was last updated")
    endpoint_arn: str | None = Field(default=None, description="ARN of this endpoint")
    failure_reason: str | None = Field(
        default=None, description="Reason for failure if status is CREATE_FAILED or UPDATE_FAILED"
    )
    live_version: str | None = Field(default=None, description="Currently active version for this endpoint")

    @field_validator("name")
    @classmethod
    def validate_endpoint_name(cls, v: str) -> str:
        """Validate endpoint name format."""
        if not v:
            raise ValueError("Endpoint name cannot be empty")

        if not v.isalnum() and not all(c.isalnum() or c == "-" for c in v):
            raise ValueError("Endpoint name can only contain alphanumeric characters and hyphens")

        return v


class CustomJWTAuthorizer(BaseAgentCoreModel):
    """JWT authorizer configuration for AgentCore runtime."""

    discovery_url: str = Field(description="Discovery URL for JWT validation")
    allowed_audience: list[str] = Field(default_factory=list, description="Allowed audiences")
    allowed_clients: list[str] = Field(default_factory=list, description="Allowed clients")


class AuthorizerConfig(BaseAgentCoreModel):
    """Authorizer configuration for AgentCore runtime."""

    custom_jwt_authorizer: CustomJWTAuthorizer | None = Field(default=None, description="JWT authorizer configuration")


class WorkloadIdentity(BaseAgentCoreModel):
    """Workload identity details for AgentCore runtime."""

    workload_identity_arn: str = Field(description="Workload identity ARN")


class AgentRuntime(ResourceBase):
    """Configuration for an agent runtime.

    Agent runtimes are associated with ECR repositories where their container images are stored.
    Each runtime can have multiple versions, each pointing to different image tags.
    """

    name: str = Field(description="Agent runtime name")
    agent_runtime_id: str = Field(description="Runtime ID")
    agent_runtime_arn: str | None = Field(default=None, description="Runtime ARN")
    description: str | None = Field(default=None, description="Runtime description")
    latest_version: str = Field(description="Latest version identifier")

    # ECR Repository association
    primary_ecr_repository: str = Field(
        description="Primary ECR repository name for this runtime (must exist in global_resources.ecr_repositories)"
    )

    # Runtime components
    versions: dict[str, AgentRuntimeVersion] = Field(
        default_factory=dict, description="Available versions by version identifier"
    )
    endpoints: dict[str, AgentRuntimeEndpoint] = Field(default_factory=dict, description="Available endpoints by name")
    workload_identity: WorkloadIdentity | None = Field(default=None, description="Workload identity details")
    authorizer_config: AuthorizerConfig | None = Field(default=None, description="Authorizer configuration")

    @field_validator("name")
    @classmethod
    def validate_runtime_name(cls, v: str) -> str:
        """Validate agent runtime name format."""
        if not v:
            raise ValueError("Agent runtime name cannot be empty")

        if not v[0].isalpha():
            raise ValueError("Agent runtime name must start with a letter")

        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError("Agent runtime name can only contain alphanumeric characters and hyphens")

        if len(v) < 3 or len(v) > 63:
            raise ValueError("Agent runtime name must be between 3 and 63 characters")

        return v

    @model_validator(mode="after")
    def validate_version_repository_consistency(cls, model):
        """Validate that all versions reference valid ECR repositories."""
        for version_id, version in model.versions.items():
            # All versions should typically use the same repository as the runtime's primary repository
            # This is a soft validation - you could have versions in different repositories
            if version.ecr_repository_name != model.primary_ecr_repository:
                import warnings

                warnings.warn(
                    f"Version '{version_id}' uses repository '{version.ecr_repository_name}' "
                    f"but runtime '{model.name}' primary repository is '{model.primary_ecr_repository}'"
                )
        return model

    @model_validator(mode="after")
    def ensure_default_endpoint(cls, model):
        """Ensure the DEFAULT endpoint exists and points to latest version.

        Note: AWS AgentCore automatically creates and manages the DEFAULT endpoint.
        This validator ensures our model reflects this AWS behavior.
        """
        if model.versions and model.latest_version in model.versions:
            # If we have versions but no DEFAULT endpoint info, create a placeholder
            # representing what AWS would automatically create
            if "DEFAULT" not in model.endpoints:
                model.endpoints["DEFAULT"] = AgentRuntimeEndpoint(
                    name="DEFAULT",
                    agent_runtime_id=model.agent_runtime_id,
                    target_version=model.latest_version,
                    status=AgentEndpointStatusType.READY,
                    created_at=model.created_at,
                    description="Default endpoint (automatically managed by AWS)",
                )
            else:
                # Ensure DEFAULT endpoint points to latest version (AWS behavior)
                default_endpoint = model.endpoints["DEFAULT"]
                if default_endpoint.target_version != model.latest_version:
                    default_endpoint.target_version = model.latest_version
        return model

    def get_version_container_uri(self, version_id: str, ecr_repository: "ECRRepository") -> str | None:
        """Get the full container URI for a specific version.

        Args:
            version_id: Version identifier
            ecr_repository: ECR repository configuration

        Returns:
            Full container URI or None if version not found
        """
        if version_id not in self.versions:
            return None

        version = self.versions[version_id]
        return version.get_container_uri(ecr_repository)
