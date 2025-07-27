"""Unit tests for AgentCore service."""

from agentcore_cli.models.base import NetworkModeType, ServerProtocolType
from agentcore_cli.models.inputs import (
    CreateAgentRuntimeInput,
    CreateEndpointInput,
    UpdateAgentRuntimeInput,
    UpdateEndpointInput,
)
from agentcore_cli.services.agentcore import AgentCoreService
from moto import mock_aws
from unittest.mock import Mock, patch


class TestAgentCoreService:
    """Test cases for AgentCoreService."""

    @mock_aws
    def test_init(self, test_region, aws_session):
        """Test AgentCoreService initialization."""
        service = AgentCoreService(test_region, aws_session)
        assert service.region == test_region
        assert service.session == aws_session
        assert service.agentcore_control_client is not None
        assert service.agentcore_client is not None

    @mock_aws
    def test_init_without_session(self, test_region):
        """Test AgentCoreService initialization without session."""
        service = AgentCoreService(test_region)
        assert service.region == test_region
        assert service.session is not None
        assert service.agentcore_control_client is not None
        assert service.agentcore_client is not None

    @mock_aws
    def test_create_agent_runtime_success(self, test_region, aws_session):
        """Test successful agent runtime creation."""
        service = AgentCoreService(test_region, aws_session)

        # Mock the boto3 client response
        mock_response = {
            "agentRuntimeId": "test-runtime-123",
            "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-runtime-123",
        }

        with patch.object(service.agentcore_control_client, "create_agent_runtime", return_value=mock_response):
            input_params = CreateAgentRuntimeInput(
                name="test-agent",
                container_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo:latest",
                role_arn="arn:aws:iam::123456789012:role/test-role",
                network_mode=NetworkModeType.PUBLIC,
                protocol=ServerProtocolType.HTTP,
                description="Test agent",
                environment_variables={"ENV": "test"},
                client_token="test-token",
            )

            result = service.create_agent_runtime(input_params)

            assert result.success is True
            assert "created successfully" in result.message
            assert result.agent_name == "test-agent"
            assert result.container_uri == input_params.container_uri
            assert result.role_arn == input_params.role_arn
            assert result.environment == test_region

    @mock_aws
    def test_create_agent_runtime_minimal_params(self, test_region, aws_session):
        """Test agent runtime creation with minimal parameters."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {
            "agentRuntimeId": "test-runtime-123",
            "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-runtime-123",
        }

        with patch.object(service.agentcore_control_client, "create_agent_runtime", return_value=mock_response):
            input_params = CreateAgentRuntimeInput(
                name="test-agent",
                container_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo:latest",
                role_arn="arn:aws:iam::123456789012:role/test-role",
                network_mode=NetworkModeType.PUBLIC,
                protocol=ServerProtocolType.HTTP,
            )

            result = service.create_agent_runtime(input_params)

            assert result.success is True
            assert result.agent_name == "test-agent"

    @mock_aws
    def test_create_agent_runtime_failure(self, test_region, aws_session):
        """Test agent runtime creation failure."""
        service = AgentCoreService(test_region, aws_session)

        # Mock the client to raise an exception
        with patch.object(service.agentcore_control_client, "create_agent_runtime") as mock_create:
            mock_create.side_effect = Exception("AWS API Error")

            input_params = CreateAgentRuntimeInput(
                name="test-agent",
                container_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo:latest",
                role_arn="arn:aws:iam::123456789012:role/test-role",
                network_mode=NetworkModeType.PUBLIC,
                protocol=ServerProtocolType.HTTP,
            )

            result = service.create_agent_runtime(input_params)

            assert result.success is False
            assert "Failed to create agent runtime" in result.message

    @mock_aws
    def test_update_agent_runtime_success(self, test_region, aws_session):
        """Test successful agent runtime update."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {"agentRuntimeId": "test-runtime-123", "agentRuntimeVersion": "v2"}

        with patch.object(service.agentcore_control_client, "update_agent_runtime", return_value=mock_response):
            input_params = UpdateAgentRuntimeInput(
                agent_runtime_id="test-runtime-123",
                container_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo:v2",
                description="Updated test agent",
                environment_variables={"ENV": "updated"},
                client_token="update-token",
            )

            result = service.update_agent_runtime(input_params)

            assert result.success is True
            assert "updated successfully" in result.message
            assert result.runtime_id == "test-runtime-123"

    @mock_aws
    def test_create_endpoint_success(self, test_region, aws_session):
        """Test successful endpoint creation."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {
            "agentRuntimeEndpointArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime-endpoint/test-endpoint"
        }

        with patch.object(
            service.agentcore_control_client, "create_agent_runtime_endpoint", return_value=mock_response
        ):
            input_params = CreateEndpointInput(
                agent_runtime_id="test-runtime-123",
                name="test-endpoint",
                description="Test endpoint",
                client_token="endpoint-token",
            )

            result = service.create_endpoint(input_params)

            assert result.success is True
            assert "created successfully" in result.message
            assert result.endpoint_name == "test-endpoint"

    @mock_aws
    def test_update_endpoint_success(self, test_region, aws_session):
        """Test successful endpoint update."""
        service = AgentCoreService(test_region, aws_session)

        with patch.object(service.agentcore_control_client, "update_agent_runtime_endpoint", return_value={}):
            input_params = UpdateEndpointInput(
                agent_runtime_id="test-runtime-123",
                endpoint_name="test-endpoint",
                target_version="v2",
                description="Updated test endpoint",
                client_token="update-endpoint-token",
            )

            result = service.update_endpoint(input_params)

            assert result.success is True
            assert "updated successfully" in result.message

    @mock_aws
    def test_delete_agent_runtime_success(self, test_region, aws_session):
        """Test successful agent runtime deletion."""
        service = AgentCoreService(test_region, aws_session)

        with patch.object(service.agentcore_control_client, "delete_agent_runtime", return_value={}):
            result = service.delete_agent_runtime("test-runtime-123")

            assert result.success is True
            assert "deleted successfully" in result.message
            assert result.agent_name == "test-agent"

    @mock_aws
    def test_list_agent_runtimes(self, test_region, aws_session):
        """Test listing agent runtimes."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {
            "agentRuntimes": [
                {"agentRuntimeId": "test-runtime-123", "agentRuntimeName": "test-agent", "status": "READY"}
            ]
        }

        with patch.object(service.agentcore_control_client, "list_agent_runtimes", return_value=mock_response):
            runtimes = service.list_agent_runtimes()

            assert isinstance(runtimes, list)
            assert len(runtimes) >= 1

    @mock_aws
    def test_get_agent_runtime(self, test_region, aws_session):
        """Test getting a specific agent runtime."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {
            "agentRuntime": {"agentRuntimeId": "test-runtime-123", "agentRuntimeName": "test-agent", "status": "READY"}
        }

        with patch.object(service.agentcore_control_client, "get_agent_runtime", return_value=mock_response):
            runtime = service.get_agent_runtime("test-runtime-123")

            assert runtime is not None
            assert runtime.name == "test-agent"

    @mock_aws
    def test_get_agent_runtime_not_found(self, test_region, aws_session):
        """Test getting a non-existent agent runtime."""
        service = AgentCoreService(test_region, aws_session)

        with patch.object(service.agentcore_control_client, "get_agent_runtime") as mock_get:
            mock_get.side_effect = Exception("ResourceNotFoundException")
            runtime = service.get_agent_runtime("non-existent-runtime")

            assert runtime is None

    @mock_aws
    def test_list_agent_runtime_versions(self, test_region, aws_session):
        """Test listing agent runtime versions."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {"agentRuntimeVersions": [{"agentRuntimeVersion": "v1", "status": "READY"}]}

        with patch.object(service.agentcore_control_client, "list_agent_runtime_versions", return_value=mock_response):
            versions = service.list_agent_runtime_versions("test-runtime-123")

            assert isinstance(versions, list)

    @mock_aws
    def test_list_agent_runtime_endpoints(self, test_region, aws_session):
        """Test listing agent runtime endpoints."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {"agentRuntimeEndpoints": [{"agentRuntimeEndpointName": "test-endpoint", "status": "READY"}]}

        with patch.object(service.agentcore_control_client, "list_agent_runtime_endpoints", return_value=mock_response):
            endpoints = service.list_agent_runtime_endpoints("test-runtime-123")

            assert isinstance(endpoints, list)

    @mock_aws
    def test_get_agent_runtime_endpoint(self, test_region, aws_session):
        """Test getting a specific agent runtime endpoint."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {"agentRuntimeEndpoint": {"agentRuntimeEndpointName": "test-endpoint", "status": "READY"}}

        with patch.object(service.agentcore_control_client, "get_agent_runtime_endpoint", return_value=mock_response):
            endpoint = service.get_agent_runtime_endpoint("test-runtime-123", "test-endpoint")

            assert endpoint is not None
            assert endpoint.name == "test-endpoint"

    @mock_aws
    def test_invoke_agent_runtime(self, test_region, aws_session):
        """Test invoking an agent runtime."""
        service = AgentCoreService(test_region, aws_session)

        mock_response = {"statusCode": 200, "response": Mock(read=lambda: b'{"output": "Hello, world!"}')}

        with patch.object(service.agentcore_client, "invoke_agent_runtime", return_value=mock_response):
            status_code, response_body = service.invoke_agent_runtime(
                agent_runtime_arn="arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-runtime-123",
                qualifier="DEFAULT",
                runtime_session_id="test-session-123",
                payload='{"prompt": "Hello, world!"}',
                content_type="application/json",
                accept="application/json",
            )

            assert isinstance(status_code, int)
            assert isinstance(response_body, str)
