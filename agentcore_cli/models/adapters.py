"""Adapter models for AgentCore Platform CLI.

This module provides adapter classes to convert between AWS API responses
and our internal model structures.
"""

from .base import AgentEndpointStatusType, AgentStatusType, NetworkModeType, ServerProtocolType
from .runtime import AgentRuntime, AgentRuntimeEndpoint, AgentRuntimeVersion, WorkloadIdentity
from typing import Any, TYPE_CHECKING


if TYPE_CHECKING:
    from mypy_boto3_bedrock_agentcore_control.type_defs import (
        AgentEndpointTypeDef,
        GetAgentRuntimeEndpointResponseTypeDef,
    )
else:
    AgentEndpointTypeDef = object
    GetAgentRuntimeEndpointResponseTypeDef = object


class AgentRuntimeResponseAdapter:
    """Helper class to convert AWS API responses to our model structures."""

    @staticmethod
    def from_aws_response(response: Any) -> AgentRuntime:
        """Convert AWS API response to AgentRuntime model."""
        # Extract container URI
        container_uri = response.get("agentRuntimeArtifact", {}).get("containerConfiguration", {}).get("containerUri")

        # Determine network mode
        network_mode = NetworkModeType(
            response.get("networkConfiguration", {}).get("networkMode", NetworkModeType.PUBLIC)
        )

        # Determine protocol
        protocol = ServerProtocolType(
            response.get("protocolConfiguration", {}).get("serverProtocol", ServerProtocolType.HTTP)
        )

        # Extract region from ARN if available
        region = "us-east-1"  # Default region
        if "agentRuntimeArn" in response and response["agentRuntimeArn"]:
            arn_parts = response["agentRuntimeArn"].split(":")
            if len(arn_parts) >= 4:
                region = arn_parts[3]

        # Extract workload identity
        workload_identity = None
        if "workloadIdentityDetails" in response and "workloadIdentityArn" in response["workloadIdentityDetails"]:
            workload_identity = WorkloadIdentity(
                workload_identity_arn=response["workloadIdentityDetails"]["workloadIdentityArn"]
            )

        # Determine status
        status = AgentStatusType(response.get("status", AgentStatusType.CREATING))

        # Parse timestamps
        created_at = response.get("createdAt")
        updated_at = response.get("updatedAt")

        # Extract version info
        version_id = "V1"  # Default to V1 (AWS format)
        if "agentRuntimeVersion" in response:
            raw_version = response["agentRuntimeVersion"]
            # Ensure consistent format - AWS uses V1, V2, etc.
            if raw_version and not raw_version.upper().startswith("V"):
                version_id = f"V{raw_version}"
            else:
                version_id = raw_version.upper() if raw_version else "V1"

        # Parse ECR information from container URI
        ecr_repository_name = ""
        image_tag = "latest"

        if container_uri:
            # Parse container URI: registry/repository:tag
            if ":" in container_uri and "/" in container_uri:
                repo_with_tag = container_uri.split("/")[-1]  # Get last part after /
                if ":" in repo_with_tag:
                    repo_name, tag = repo_with_tag.split(":", 1)
                    ecr_repository_name = repo_name
                    image_tag = tag
                else:
                    ecr_repository_name = repo_with_tag
            elif "/" in container_uri:
                # No tag specified, extract repository name
                ecr_repository_name = container_uri.split("/")[-1]

        # Create runtime version
        runtime_version = AgentRuntimeVersion(
            version_id=version_id,
            agent_runtime_id=response.get("agentRuntimeId", ""),
            ecr_repository_name=ecr_repository_name,
            image_tag=image_tag,
            status=status,
            created_at=created_at,
            network_mode=network_mode,
            protocol=protocol,
            environment_variables=response.get("environmentVariables", {}),
            execution_role_arn=response.get("roleArn", ""),
            failure_reason=response.get("failureReason"),
            updated_at=updated_at,
        )

        # Create default endpoint
        default_endpoint = AgentRuntimeEndpoint(
            name="DEFAULT",
            agent_runtime_id=response.get("agentRuntimeId", ""),
            target_version=version_id,
            status=AgentEndpointStatusType.READY,
            created_at=created_at,
            endpoint_arn=f"{response.get('agentRuntimeArn', '')}/endpoints/DEFAULT"
            if response.get("agentRuntimeArn")
            else None,
        )

        # Create and return AgentRuntime
        return AgentRuntime(
            name=response.get("agentRuntimeName", ""),
            agent_runtime_id=response.get("agentRuntimeId", ""),
            agent_runtime_arn=response.get("agentRuntimeArn"),
            description=response.get("description"),
            latest_version=version_id,
            primary_ecr_repository=ecr_repository_name,
            versions={version_id: runtime_version},
            endpoints={"DEFAULT": default_endpoint},
            created_at=created_at,
            updated_at=updated_at,
            region=region,
            tags=response.get("tags", {}),
            workload_identity=workload_identity,
        )

    @staticmethod
    def from_endpoint_response(
        response: AgentEndpointTypeDef | GetAgentRuntimeEndpointResponseTypeDef, agent_runtime_id: str
    ) -> AgentRuntimeEndpoint:
        """Convert AWS API endpoint response to AgentRuntimeEndpoint model."""
        status = AgentEndpointStatusType(response.get("status", AgentEndpointStatusType.READY))

        return AgentRuntimeEndpoint(
            name=response["name"],
            agent_runtime_id=agent_runtime_id,
            target_version=response.get("targetVersion", ""),
            status=status,
            description=response.get("description", ""),
            created_at=response["createdAt"],
            # Handle potential datetime conversion
            updated_at=response["lastUpdatedAt"],
            endpoint_arn=response.get("agentRuntimeEndpointArn"),
            failure_reason=str(response.get("failureReason")) if response.get("failureReason") else None,
            live_version=str(response.get("liveVersion")) if response.get("liveVersion") else None,
        )
