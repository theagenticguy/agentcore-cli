"""Response models for AgentCore Platform CLI.

This module defines models for responses from AgentCore operations and CLI commands.
"""

import json
from .base import BaseAgentCoreModel
from datetime import datetime
from pydantic import Field
from typing import Any


class AgentInvocationResponse(BaseAgentCoreModel):
    """Response model for agent invocation.

    This model handles both streaming and non-streaming responses from
    the boto3 invoke_agent_runtime API.
    """

    content_type: str | None = Field(default=None, description="Content type of the response")
    streaming: bool = Field(default=False, description="Whether response was streaming")
    session_id: str = Field(description="Session ID used for the invocation")
    agent_name: str = Field(description="Agent name that was invoked")
    endpoint_name: str = Field(description="Endpoint name that was used")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the invocation")

    # For streaming responses
    stream_content: list[str] | None = Field(default=None, description="Collected content from streaming response")

    # For non-streaming responses
    output: Any | None = Field(default=None, description="Response output object for non-streaming response")

    @classmethod
    def from_streaming_response(
        cls, response: Any, agent_name: str, endpoint_name: str, session_id: str
    ) -> "AgentInvocationResponse":
        """Create a response object from a streaming API response."""
        content = []

        # Handle streaming response
        if "response" in response and hasattr(response["response"], "iter_lines"):
            for line in response["response"].iter_lines(chunk_size=1):
                if line:
                    line_text = line.decode("utf-8")
                    # Check for "data: " prefix
                    if line_text.startswith("data: "):
                        line_text = line_text[6:]  # Remove the "data: " prefix
                        content.append(line_text)

        return cls(
            content_type=response.get("contentType"),
            streaming=True,
            session_id=session_id,
            agent_name=agent_name,
            endpoint_name=endpoint_name,
            stream_content=content,
        )

    @classmethod
    def from_nonstreaming_response(
        cls, response: Any, agent_name: str, endpoint_name: str, session_id: str
    ) -> "AgentInvocationResponse":
        """Create a response object from a non-streaming API response."""
        try:
            # Extract response body
            response_body = None
            if "response" in response:
                if hasattr(response["response"], "read"):
                    response_body = response["response"].read()
                    if response_body:
                        response_data = json.loads(response_body)
                        output = response_data.get("output", {})
                    else:
                        output = {}
                else:
                    output = response.get("response", {})
            else:
                output = {}

            return cls(
                content_type=response.get("contentType"),
                streaming=False,
                session_id=session_id,
                agent_name=agent_name,
                endpoint_name=endpoint_name,
                output=output,
            )

        except Exception as e:
            # Handle any parsing errors
            return cls(
                content_type=response.get("contentType"),
                streaming=False,
                session_id=session_id,
                agent_name=agent_name,
                endpoint_name=endpoint_name,
                output={"error": f"Failed to parse response: {str(e)}"},
            )


class SyncStatus(BaseAgentCoreModel):
    """Status of configuration synchronization."""

    environment: str = Field(description="Environment name")
    cloud_config_enabled: bool = Field(description="Whether cloud config is enabled")
    auto_sync_enabled: bool = Field(description="Whether auto-sync is enabled")
    last_sync: datetime | None = Field(default=None, description="Last sync timestamp")
    in_sync: bool = Field(description="Whether local and cloud are in sync")
    drift_details: dict[str, dict[str, list[str]]] | None = Field(default=None, description="Drift details")


class CloudSyncResult(BaseAgentCoreModel):
    """Result of a cloud sync operation."""

    success: bool = Field(description="Whether the operation was successful")
    message: str = Field(description="Status message")
    environment: str = Field(description="Environment name")
    synced_items: dict[str, int] = Field(default_factory=dict, description="Count of synced items by type")
    errors: list[str] = Field(default_factory=list, description="Errors encountered during sync")


class ActionResult(BaseAgentCoreModel):
    """Base model for CLI action results."""

    success: bool = Field(description="Whether the action was successful")
    message: str = Field(description="Status message")


class AgentCreationResult(ActionResult):
    """Result of agent creation."""

    agent_name: str = Field(description="Agent name")
    runtime_id: str | None = Field(default=None, description="Runtime ID")
    runtime_arn: str | None = Field(default=None, description="Runtime ARN")
    container_uri: str | None = Field(default=None, description="Container URI")
    role_arn: str | None = Field(default=None, description="IAM role ARN")
    environment: str = Field(description="Environment name")
    default_endpoint: str = Field(default="DEFAULT", description="Default endpoint name")


class AgentUpdateResult(ActionResult):
    """Result of agent update."""

    agent_name: str = Field(description="Agent name")
    runtime_id: str = Field(description="Runtime ID")
    version: str = Field(description="New runtime version created")
    container_uri: str = Field(description="Container URI used")
    environment: str = Field(description="Environment name")


class EndpointCreationResult(ActionResult):
    """Result of endpoint creation."""

    agent_name: str = Field(description="Agent name")
    runtime_id: str = Field(description="Runtime ID")
    endpoint_name: str = Field(description="Endpoint name")
    endpoint_arn: str | None = Field(default=None, description="Endpoint ARN")
    target_version: str = Field(description="Version the endpoint points to")
    environment: str | None = Field(default=None, description="Environment mapped to this endpoint")


class EndpointUpdateResult(ActionResult):
    """Result of endpoint update."""

    agent_name: str = Field(description="Agent name")
    runtime_id: str = Field(description="Runtime ID")
    endpoint_name: str = Field(description="Endpoint name")
    previous_version: str = Field(description="Previous version")
    new_version: str = Field(description="New version the endpoint points to")
    environment: str | None = Field(default=None, description="Environment mapped to this endpoint")


class AgentDeletionResult(ActionResult):
    """Result of agent deletion."""

    agent_name: str = Field(description="Agent name")
    deleted_resources: list[str] = Field(default_factory=list, description="Deleted resources")
    environment: str = Field(description="Environment name")


class EnvironmentCreationResult(ActionResult):
    """Result of environment creation."""

    name: str = Field(description="Environment name")
    region: str = Field(description="AWS region")


class EnvironmentDeletionResult(ActionResult):
    """Result of environment deletion."""

    name: str = Field(description="Environment name")


class ImageBuildResult(ActionResult):
    """Result of image build."""

    repo_name: str = Field(description="Repository name")
    tag: str = Field(description="Image tag")
    image_id: str | None = Field(default=None, description="Image ID")
