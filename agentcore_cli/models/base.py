"""Base models for AgentCore Platform CLI.

This module defines base classes and enums used throughout the AgentCore CLI models.
All enums align with AWS Bedrock AgentCore API specifications.
"""

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class AgentStatusType(StrEnum):
    """Status of an agent runtime.

    These statuses reflect the lifecycle of an AWS AgentCore runtime.
    Runtimes transition through these states during creation, updates, and deletion.
    """

    CREATING = "CREATING"
    CREATE_FAILED = "CREATE_FAILED"
    UPDATING = "UPDATING"
    UPDATE_FAILED = "UPDATE_FAILED"
    READY = "READY"
    DELETING = "DELETING"


class NetworkModeType(StrEnum):
    """Network mode for AgentCore runtimes.

    Defines how the agent runtime is exposed within AWS networking:
    - PUBLIC: Runtime is accessible from the internet via public endpoints
    - PRIVATE: Runtime is only accessible within VPC (future AWS enhancement)
    """

    PUBLIC = "PUBLIC"
    # Note: PRIVATE mode may be supported in future AWS AgentCore versions
    # PRIVATE = "PRIVATE"


class ServerProtocolType(StrEnum):
    """Server protocol type for AgentCore runtimes.

    Defines the communication protocol the agent runtime uses:
    - HTTP: Standard HTTP protocol for REST API communication
    - MCP: Model Context Protocol for advanced agent interactions
    """

    HTTP = "HTTP"
    MCP = "MCP"


class AgentEndpointStatusType(StrEnum):
    """Status of an agent runtime endpoint.

    Endpoints go through these states during their lifecycle.
    Unlike runtimes, endpoints can be updated to point to different versions.
    """

    CREATING = "CREATING"
    CREATE_FAILED = "CREATE_FAILED"
    UPDATING = "UPDATING"
    UPDATE_FAILED = "UPDATE_FAILED"
    READY = "READY"
    DELETING = "DELETING"


class BaseAgentCoreModel(BaseModel):
    """Base model with common configuration for all AgentCore models.

    Provides strict validation and consistent behavior across all models.
    All AgentCore CLI models inherit from this base class.
    """

    model_config = ConfigDict(
        extra="forbid",  # Forbid extra attributes for strict AWS API alignment
        validate_default=True,  # Validate default values
        validate_assignment=True,  # Validate attribute assignments
        str_strip_whitespace=True,  # Strip whitespace from string values
        use_enum_values=True,  # Use enum values for JSON serialization
        arbitrary_types_allowed=True,  # Allow datetime and other complex types
    )


class ResourceTag(BaseAgentCoreModel):
    """AWS resource tag for cost allocation and resource management."""

    key: str = Field(description="Tag key (case-sensitive)")
    value: str = Field(description="Tag value")


class ResourceBase(BaseAgentCoreModel):
    """Base class for all AWS resource models.

    Provides common fields that all AWS resources share:
    region, timestamps, and tags for resource management.
    """

    region: str = Field(description="AWS region where this resource exists")
    created_at: datetime | None = Field(default=None, description="Resource creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last modification timestamp")
    tags: dict[str, str] = Field(default_factory=dict, description="AWS resource tags")
