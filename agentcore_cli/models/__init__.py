"""Models package for AgentCore Platform CLI.

This package provides data models for the AgentCore Platform CLI.
"""

# Base models
from .base import (
    AgentEndpointStatusType,
    AgentStatusType,
    BaseAgentCoreModel,
    NetworkModeType,
    ResourceBase,
    ResourceTag,
    ServerProtocolType,
)

# Resource models
from .resources import CognitoConfig, CognitoIdentityPool, CognitoUserPool, ECRRepository, IAMRoleConfig

# Runtime models
from .runtime import (
    AgentRuntime,
    AgentRuntimeEndpoint,
    AgentRuntimeVersion,
    AuthorizerConfig,
    CustomJWTAuthorizer,
    WorkloadIdentity,
)

# Configuration models
from .config import AgentCoreConfig, EnvironmentConfig, GlobalResourceConfig, SyncConfig

# Input models
from .inputs import (
    ContainerBuildInput,
    CreateAgentRuntimeInput,
    CreateEndpointInput,
    EnvironmentInput,
    InvokeAgentInput,
    UpdateAgentRuntimeInput,
    UpdateEndpointInput,
)

# Response models
from .responses import (
    ActionResult,
    AgentCreationResult,
    AgentDeletionResult,
    AgentInvocationResponse,
    AgentUpdateResult,
    CloudSyncResult,
    EndpointCreationResult,
    EndpointUpdateResult,
    EnvironmentCreationResult,
    EnvironmentDeletionResult,
    ImageBuildResult,
    SyncStatus,
)

# Adapters
from .adapters import AgentRuntimeResponseAdapter

__all__ = [
    "AgentEndpointStatusType",
    "AgentStatusType",
    "BaseAgentCoreModel",
    "NetworkModeType",
    "ResourceBase",
    "ResourceTag",
    "ServerProtocolType",
    "CognitoConfig",
    "CognitoIdentityPool",
    "CognitoUserPool",
    "ECRRepository",
    "IAMRoleConfig",
    "AgentRuntime",
    "AgentRuntimeEndpoint",
    "AgentRuntimeVersion",
    "AuthorizerConfig",
    "CustomJWTAuthorizer",
    "WorkloadIdentity",
    "AgentCoreConfig",
    "EnvironmentConfig",
    "GlobalResourceConfig",
    "SyncConfig",
    "ContainerBuildInput",
    "CreateAgentRuntimeInput",
    "CreateEndpointInput",
    "EnvironmentInput",
    "InvokeAgentInput",
    "UpdateAgentRuntimeInput",
    "UpdateEndpointInput",
    "ActionResult",
    "AgentCreationResult",
    "AgentDeletionResult",
    "AgentInvocationResponse",
    "AgentUpdateResult",
    "CloudSyncResult",
    "EndpointCreationResult",
    "EndpointUpdateResult",
    "EnvironmentCreationResult",
    "EnvironmentDeletionResult",
    "ImageBuildResult",
    "SyncStatus",
    "AgentRuntimeResponseAdapter",
]
