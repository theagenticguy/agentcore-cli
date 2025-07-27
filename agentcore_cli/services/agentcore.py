"""AgentCore service operations for AgentCore Platform CLI.

This module provides a service layer for AWS AgentCore operations using boto3
to create and manage agent runtimes, their versions, and endpoints.
"""

from boto3.session import Session
from loguru import logger
from typing import Any, TYPE_CHECKING
from botocore.response import StreamingBody

from agentcore_cli.models.runtime import AgentRuntime, AgentRuntimeEndpoint
from agentcore_cli.models.adapters import AgentRuntimeResponseAdapter
from agentcore_cli.models.inputs import (
    CreateAgentRuntimeInput,
    UpdateAgentRuntimeInput,
    CreateEndpointInput,
    UpdateEndpointInput,
)
from agentcore_cli.models.responses import (
    AgentCreationResult,
    AgentUpdateResult,
    EndpointCreationResult,
    EndpointUpdateResult,
    AgentDeletionResult,
)
from agentcore_cli.models.adapters import AgentRuntimeResponseAdapter

if TYPE_CHECKING:
    from mypy_boto3_bedrock_agentcore_control.type_defs import AgentTypeDef
else:
    AgentTypeDef = object


class AgentCoreService:
    """Service for AWS AgentCore operations."""

    def __init__(self, region: str, session: Session | None = None):
        """Initialize the AgentCore service.

        Args:
            region: AWS region for AgentCore operations.
            session: Boto3 session to use. If None, creates a new session.
        """
        self.region = region
        self.session = session or Session(region_name=region)

        # Initialize the boto3 clients
        self.agentcore_control_client = self.session.client("bedrock-agentcore-control", region_name=region)
        self.agentcore_client = self.session.client("bedrock-agentcore", region_name=region)

    def create_agent_runtime(self, input_params: CreateAgentRuntimeInput) -> AgentCreationResult:
        """Create an agent runtime.

        Args:
            input_params: Parameters for creating the agent runtime.

        Returns:
            AgentCreationResult: Result of the agent creation operation.
        """
        try:
            # Prepare the request parameters
            create_params: dict[str, Any] = {
                "agentRuntimeName": input_params.name,
                "agentRuntimeArtifact": {"containerConfiguration": {"containerUri": input_params.container_uri}},
                "roleArn": input_params.role_arn,
                "networkConfiguration": {"networkMode": input_params.network_mode},
                "protocolConfiguration": {"serverProtocol": input_params.protocol},
            }

            # Add optional parameters if provided
            if input_params.description:
                create_params["description"] = input_params.description

            if input_params.environment_variables:
                create_params["environmentVariables"] = input_params.environment_variables

            if input_params.client_token:
                create_params["clientToken"] = input_params.client_token

            # Call the API to create the agent runtime
            logger.info(f"Creating agent runtime '{input_params.name}'...")
            response = self.agentcore_control_client.create_agent_runtime(**create_params)

            # Return success result
            return AgentCreationResult(
                success=True,
                message=f"Agent runtime '{input_params.name}' created successfully",
                agent_name=input_params.name,
                runtime_id=response.get("agentRuntimeId"),
                runtime_arn=response.get("agentRuntimeArn"),
                container_uri=input_params.container_uri,
                role_arn=input_params.role_arn,
                environment=self.region,
                default_endpoint="DEFAULT",
            )

        except Exception as e:
            # Handle error cases
            logger.error(f"Failed to create agent runtime: {str(e)}")
            return AgentCreationResult(
                success=False,
                message=f"Failed to create agent runtime: {str(e)}",
                agent_name=input_params.name,
                environment=self.region,
            )

    def update_agent_runtime(self, input_params: UpdateAgentRuntimeInput) -> AgentUpdateResult:
        """Update an agent runtime, creating a new version.

        Args:
            input_params: Parameters for updating the agent runtime.

        Returns:
            AgentUpdateResult: Result of the agent update operation.
        """
        try:
            # Prepare the request parameters
            update_params: dict[str, Any] = {"agentRuntimeId": input_params.agent_runtime_id}

            # Add optional parameters if provided
            if input_params.description:
                update_params["description"] = input_params.description

            if input_params.container_uri:
                update_params["agentRuntimeArtifact"] = {
                    "containerConfiguration": {"containerUri": input_params.container_uri}
                }

            if input_params.role_arn:
                update_params["roleArn"] = input_params.role_arn

            if input_params.network_mode:
                update_params["networkConfiguration"] = {"networkMode": input_params.network_mode}

            if input_params.protocol:
                update_params["protocolConfiguration"] = {"serverProtocol": input_params.protocol}

            if input_params.environment_variables:
                update_params["environmentVariables"] = input_params.environment_variables

            if input_params.client_token:
                update_params["clientToken"] = input_params.client_token

            # Call the API to update the agent runtime
            logger.info(f"Updating agent runtime {input_params.agent_runtime_id}...")
            response = self.agentcore_control_client.update_agent_runtime(**update_params)

            # Get the new version
            new_version = response.get("agentRuntimeVersion", "unknown")

            # Return success result
            container_uri = input_params.container_uri or "unchanged"
            return AgentUpdateResult(
                success=True,
                message=f"Agent runtime updated successfully, new version: {new_version}",
                agent_name=input_params.agent_runtime_id,  # We don't have the name here, just ID
                runtime_id=input_params.agent_runtime_id,
                version=new_version,
                container_uri=container_uri,
                environment=self.region,
            )

        except Exception as e:
            # Handle error cases
            logger.error(f"Failed to update agent runtime: {str(e)}")
            return AgentUpdateResult(
                success=False,
                message=f"Failed to update agent runtime: {str(e)}",
                agent_name=input_params.agent_runtime_id,  # We don't have the name here, just ID
                runtime_id=input_params.agent_runtime_id,
                version="N/A",
                container_uri="N/A",
                environment=self.region,
            )

    def create_endpoint(self, input_params: CreateEndpointInput) -> EndpointCreationResult:
        """Create an agent runtime endpoint.

        Args:
            input_params: Parameters for creating the endpoint.

        Returns:
            EndpointCreationResult: Result of the endpoint creation operation.
        """
        try:
            # Prepare the request parameters
            create_params: dict[str, Any] = {"agentRuntimeId": input_params.agent_runtime_id, "name": input_params.name}

            # Add optional parameters if provided
            if input_params.target_version:
                create_params["agentRuntimeVersion"] = input_params.target_version

            if input_params.description:
                create_params["description"] = input_params.description

            if input_params.client_token:
                create_params["clientToken"] = input_params.client_token

            # Call the API to create the endpoint
            logger.info(f"Creating endpoint '{input_params.name}' for agent runtime {input_params.agent_runtime_id}...")
            response = self.agentcore_control_client.create_agent_runtime_endpoint(**create_params)

            # Get the target version and endpoint ARN
            target_version = response.get("targetVersion", "latest")
            endpoint_arn = response.get("agentRuntimeEndpointArn")

            # Return success result
            return EndpointCreationResult(
                success=True,
                message=f"Endpoint '{input_params.name}' created successfully",
                agent_name=input_params.agent_runtime_id,  # We don't have the name here, just ID
                runtime_id=input_params.agent_runtime_id,
                endpoint_name=input_params.name,
                endpoint_arn=endpoint_arn,
                target_version=target_version,
            )

        except Exception as e:
            # Handle error cases
            logger.error(f"Failed to create endpoint: {str(e)}")
            return EndpointCreationResult(
                success=False,
                message=f"Failed to create endpoint: {str(e)}",
                agent_name=input_params.agent_runtime_id,
                runtime_id=input_params.agent_runtime_id,
                endpoint_name=input_params.name,
                target_version="N/A",
            )

    def update_endpoint(self, input_params: UpdateEndpointInput) -> EndpointUpdateResult:
        """Update an agent runtime endpoint.

        Args:
            input_params: Parameters for updating the endpoint.

        Returns:
            EndpointUpdateResult: Result of the endpoint update operation.
        """
        try:
            # First get the current endpoint details to know the previous version
            try:
                endpoint_response = self.agentcore_control_client.get_agent_runtime_endpoint(
                    agentRuntimeId=input_params.agent_runtime_id, endpointName=input_params.endpoint_name
                )
                previous_version = endpoint_response.get("targetVersion", "unknown")
            except Exception as e:
                logger.warning(f"Could not retrieve current endpoint details: {str(e)}")
                previous_version = "unknown"

            # Prepare the request parameters
            update_params: dict[str, Any] = {
                "agentRuntimeId": input_params.agent_runtime_id,
                "name": input_params.endpoint_name,
                "agentRuntimeVersion": input_params.target_version,
            }

            # Add optional parameters if provided
            if input_params.description:
                update_params["description"] = input_params.description

            if input_params.client_token:
                update_params["clientToken"] = input_params.client_token

            # Call the API to update the endpoint
            logger.info(f"Updating endpoint '{input_params.endpoint_name}' to version {input_params.target_version}...")
            response = self.agentcore_control_client.update_agent_runtime_endpoint(**update_params)

            # Return success result
            return EndpointUpdateResult(
                success=True,
                message=f"Endpoint '{input_params.endpoint_name}' updated successfully to version {input_params.target_version}",
                agent_name=input_params.agent_runtime_id,  # We don't have the name here, just ID
                runtime_id=input_params.agent_runtime_id,
                endpoint_name=input_params.endpoint_name,
                previous_version=previous_version,
                new_version=input_params.target_version,
            )

        except Exception as e:
            # Handle error cases
            logger.error(f"Failed to update endpoint: {str(e)}")
            return EndpointUpdateResult(
                success=False,
                message=f"Failed to update endpoint: {str(e)}",
                agent_name=input_params.agent_runtime_id,
                runtime_id=input_params.agent_runtime_id,
                endpoint_name=input_params.endpoint_name,
                previous_version="unknown",
                new_version=input_params.target_version,
            )

    def delete_agent_runtime(self, agent_runtime_id: str) -> AgentDeletionResult:
        """Delete an agent runtime.

        Args:
            agent_runtime_id: ID of the agent runtime to delete.

        Returns:
            AgentDeletionResult: Result of the agent deletion operation.
        """
        try:
            # First, list and delete all endpoints
            deleted_resources: list[str] = []

            try:
                # List all endpoints
                endpoints_response = self.agentcore_control_client.list_agent_runtime_endpoints(
                    agentRuntimeId=agent_runtime_id
                )

                # Get endpoints list with fallback to empty list
                endpoints_list = endpoints_response.get("endpoints", []) or []

                # Ensure we have an iterable before looping
                if not hasattr(endpoints_list, "__iter__"):
                    logger.warning("Endpoints list is not iterable, skipping endpoint deletion")
                    endpoints_list = []

                # Delete each endpoint
                for endpoint in endpoints_list:
                    endpoint_name = endpoint.get("name")
                    if endpoint_name:
                        try:
                            self.agentcore_control_client.delete_agent_runtime_endpoint(
                                agentRuntimeId=agent_runtime_id, endpointName=endpoint_name
                            )
                            deleted_resources.append(f"Endpoint: {endpoint_name}")
                            logger.info(f"Deleted endpoint '{endpoint_name}'")
                        except Exception as endpoint_error:
                            logger.warning(f"Failed to delete endpoint '{endpoint_name}': {str(endpoint_error)}")
            except Exception as list_error:
                logger.warning(f"Failed to list endpoints: {str(list_error)}")

            # Then delete the agent runtime itself
            logger.info(f"Deleting agent runtime {agent_runtime_id}...")
            self.agentcore_control_client.delete_agent_runtime(agentRuntimeId=agent_runtime_id)
            deleted_resources.append(f"Agent Runtime: {agent_runtime_id}")

            # Return success result
            return AgentDeletionResult(
                success=True,
                message=f"Agent runtime {agent_runtime_id} and its endpoints deleted successfully",
                agent_name=agent_runtime_id,  # We don't have the name here, just ID
                deleted_resources=deleted_resources,
                environment=self.region,
            )

        except Exception as e:
            # Handle error cases
            logger.error(f"Failed to delete agent runtime: {str(e)}")
            return AgentDeletionResult(
                success=False,
                message=f"Failed to delete agent runtime: {str(e)}",
                agent_name=agent_runtime_id,
                deleted_resources=[],
                environment=self.region,
            )

    def list_agent_runtimes(self) -> list[AgentRuntime]:
        """List all agent runtimes.

        Returns:
            list[AgentTypeDef]: List of agent runtimes.
        """
        response = self.agentcore_control_client.list_agent_runtimes()

        return [AgentRuntimeResponseAdapter.from_aws_response(runtime) for runtime in response["agentRuntimes"]]

    def get_agent_runtime(self, agent_runtime_id: str) -> AgentRuntime | None:
        """Get details for a specific agent runtime.

        Args:
            agent_runtime_id: ID of the agent runtime to retrieve.

        Returns:
            Optional[AgentRuntime]: Agent runtime details or None if not found.
        """
        try:
            response = self.agentcore_control_client.get_agent_runtime(agentRuntimeId=agent_runtime_id)

            # Convert API response to our model
            agent_runtime = AgentRuntimeResponseAdapter.from_aws_response(response)
            return agent_runtime

        except Exception as e:
            logger.error(f"Failed to get agent runtime {agent_runtime_id}: {str(e)}")
            return None

    def list_agent_runtime_versions(self, agent_runtime_id: str) -> list[AgentRuntime]:
        """List all versions of an agent runtime.

        Args:
            agent_runtime_id: ID of the agent runtime to list versions for.

        Returns:
            list[dict[str, Any]]: List of agent runtime versions.
        """
        response = self.agentcore_control_client.list_agent_runtime_versions(agentRuntimeId=agent_runtime_id)

        return [AgentRuntimeResponseAdapter.from_aws_response(version) for version in response["agentRuntimes"]]

    def list_agent_runtime_endpoints(self, agent_runtime_id: str) -> list[AgentRuntimeEndpoint]:
        """List all endpoints for an agent runtime.

        Args:
            agent_runtime_id: ID of the agent runtime to list endpoints for.

        Returns:
            list[dict[str, Any]]: List of agent runtime endpoints.
        """
        response = self.agentcore_control_client.list_agent_runtime_endpoints(agentRuntimeId=agent_runtime_id)
        return [
            AgentRuntimeResponseAdapter.from_endpoint_response(endpoint, agent_runtime_id)
            for endpoint in response["runtimeEndpoints"]
        ]

    def get_agent_runtime_endpoint(self, agent_runtime_id: str, endpoint_name: str) -> AgentRuntimeEndpoint | None:
        """Get details for a specific agent runtime endpoint.

        Args:
            agent_runtime_id: ID of the agent runtime.
            endpoint_name: Name of the endpoint to retrieve.

        Returns:
            Optional[AgentRuntimeEndpoint]: Endpoint details or None if not found.
        """
        try:
            response = self.agentcore_control_client.get_agent_runtime_endpoint(
                agentRuntimeId=agent_runtime_id, endpointName=endpoint_name
            )

            # Convert API response to our model
            endpoint = AgentRuntimeResponseAdapter.from_endpoint_response(response, agent_runtime_id)
            return endpoint

        except Exception as e:
            logger.error(f"Failed to get endpoint {endpoint_name} for agent runtime {agent_runtime_id}: {str(e)}")
            return None

    def invoke_agent_runtime(
        self,
        agent_runtime_arn: str,
        qualifier: str,
        runtime_session_id: str,
        payload: str,
        content_type: str = "application/json",
        accept: str = "application/json",
    ) -> tuple[int, str]:
        """Invoke an agent runtime with a given payload.

        Args:
            agent_runtime_arn: ARN of the agent runtime to invoke.
            qualifier: Qualifier (endpoint name or version) to use.
            runtime_session_id: Session ID for the invocation.
            payload: Payload to send to the agent runtime.
            content_type: Content type of the payload.
            accept: Accept header value.

        Returns:
            Tuple[int, StreamingBody]: Status code and response object.
        """
        try:
            # Prepare the invoke parameters
            invoke_params: dict[str, Any] = {
                "agentRuntimeArn": agent_runtime_arn,
                "qualifier": qualifier,
                "runtimeSessionId": runtime_session_id,
                "contentType": content_type,
                "accept": accept,
                "payload": payload.encode("utf-8"),
            }

            # Call the API to invoke the agent runtime
            response = self.agentcore_client.invoke_agent_runtime(**invoke_params)

            # Extract status code and response body
            status_code = response.get("statusCode", 500)
            response_body = response.get("response")
            if not response_body:
                raise Exception("No response body received from agent runtime")
            else:
                agent_response = response_body.read().decode("utf-8")

            return status_code, agent_response
        except Exception as e:
            logger.error(f"Failed to invoke agent runtime: {str(e)}")
            return 500, str(e)
