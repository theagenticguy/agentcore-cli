"""Input models for AgentCore Platform CLI.

This module defines input models for CLI commands and API interactions.
All models align with AWS Bedrock AgentCore API requirements.
"""

from .base import BaseAgentCoreModel, NetworkModeType, ServerProtocolType
from pydantic import Field, model_validator


class CreateAgentRuntimeInput(BaseAgentCoreModel):
    """Input for creating a new agent runtime.

    Maps directly to AWS create_agent_runtime API parameters.
    """

    name: str = Field(description="Agent runtime name")
    container_uri: str = Field(description="Full ECR container URI including tag")
    role_arn: str = Field(description="IAM execution role ARN for the agent runtime")

    # Optional parameters
    description: str | None = Field(default=None, description="Agent runtime description")
    network_mode: NetworkModeType = Field(default=NetworkModeType.PUBLIC, description="Network configuration mode")
    protocol: ServerProtocolType = Field(default=ServerProtocolType.HTTP, description="Server protocol type")
    environment_variables: dict[str, str] = Field(default_factory=dict, description="Runtime environment variables")
    client_token: str | None = Field(default=None, description="Client token for idempotency")


class UpdateAgentRuntimeInput(BaseAgentCoreModel):
    """Input for updating an agent runtime.

    Updates create a new immutable version. Maps to AWS update_agent_runtime API.
    """

    agent_runtime_id: str = Field(description="Agent runtime ID to update")

    # Optional update parameters - at least one must be provided
    description: str | None = Field(default=None, description="Updated description")
    container_uri: str | None = Field(default=None, description="New container URI")
    role_arn: str | None = Field(default=None, description="New IAM execution role ARN")
    network_mode: NetworkModeType | None = Field(default=None, description="New network mode")
    protocol: ServerProtocolType | None = Field(default=None, description="New protocol type")
    environment_variables: dict[str, str] | None = Field(default=None, description="Updated environment variables")
    client_token: str | None = Field(default=None, description="Client token for idempotency")

    @model_validator(mode="after")
    def validate_at_least_one_update(cls, model):
        """Ensure at least one field is being updated."""
        update_fields = [
            model.description,
            model.container_uri,
            model.role_arn,
            model.network_mode,
            model.protocol,
            model.environment_variables,
        ]
        if not any(field is not None for field in update_fields):
            raise ValueError("At least one field must be provided for update")
        return model


class CreateEndpointInput(BaseAgentCoreModel):
    """Input for creating an agent runtime endpoint.

    Maps to AWS create_agent_runtime_endpoint API parameters.
    """

    agent_runtime_id: str = Field(description="Agent runtime ID")
    name: str = Field(description="Endpoint name")
    target_version: str | None = Field(default=None, description="Specific runtime version (defaults to latest)")
    description: str | None = Field(default=None, description="Endpoint description")
    client_token: str | None = Field(default=None, description="Client token for idempotency")


class UpdateEndpointInput(BaseAgentCoreModel):
    """Input for updating an agent runtime endpoint.

    Maps to AWS update_agent_runtime_endpoint API parameters.
    """

    agent_runtime_id: str = Field(description="Agent runtime ID")
    endpoint_name: str = Field(description="Endpoint name to update")
    target_version: str = Field(description="New runtime version to point endpoint to")
    description: str | None = Field(default=None, description="Updated description")
    client_token: str | None = Field(default=None, description="Client token for idempotency")


class InvokeAgentInput(BaseAgentCoreModel):
    """Input for invoking an agent runtime.

    Maps directly to AWS invoke_agent_runtime API requirements.
    The API requires a full ARN and qualifier (endpoint name).
    """

    agent_runtime_arn: str = Field(description="Full ARN of the agent runtime to invoke")
    qualifier: str = Field(description="Endpoint name or version qualifier (e.g., 'DEFAULT', 'production')")
    runtime_session_id: str = Field(description="Session ID for the runtime invocation")
    prompt: str = Field(description="Prompt to send to the agent")

    # Additional fields for CLI convenience
    environment: str | None = Field(default=None, description="Environment context (for CLI reference only)")
    agent_name: str | None = Field(default=None, description="Agent name (for CLI reference only)")


class EnvironmentInput(BaseAgentCoreModel):
    """Input for environment operations."""

    name: str = Field(description="Environment name")
    region: str | None = Field(default=None, description="AWS region for the environment")


class ContainerBuildInput(BaseAgentCoreModel):
    """Input for building and pushing a container image to ECR."""

    ecr_repository_name: str = Field(description="ECR repository name (must exist in configuration)")
    image_tag: str = Field(default="latest", description="Image tag to assign")
    dockerfile_path: str = Field(default="Dockerfile", description="Path to Dockerfile")
    build_context: str = Field(default=".", description="Docker build context directory")
    build_args: dict[str, str] = Field(default_factory=dict, description="Docker build arguments")
    platform: str = Field(default="linux/arm64", description="Target platform for the build")
    no_cache: bool = Field(default=False, description="Disable Docker build cache")

    @property
    def dockerfile(self) -> str:
        """Legacy property for backward compatibility."""
        return self.dockerfile_path
