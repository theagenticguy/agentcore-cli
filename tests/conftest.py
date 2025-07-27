"""Pytest configuration and common fixtures for AgentCore Platform CLI tests."""

import os
import pytest
from boto3.session import Session
from moto import mock_aws


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def aws_session(aws_credentials):
    """Create a boto3 session with mocked credentials."""
    with mock_aws():
        return Session(region_name="us-east-1")


@pytest.fixture
def mock_aws_services(aws_credentials):
    """Mock all AWS services used in the application."""
    with mock_aws():
        yield


@pytest.fixture
def test_region():
    """Test AWS region."""
    return "us-east-1"


@pytest.fixture
def test_agent_name():
    """Test agent name."""
    return "test-agent"


@pytest.fixture
def test_environment():
    """Test environment."""
    return "dev"


@pytest.fixture
def test_repository_name():
    """Test ECR repository name."""
    return "test-repo"


@pytest.fixture
def test_user_pool_id():
    """Test Cognito user pool ID."""
    return "us-east-1_testpool123"


@pytest.fixture
def test_identity_pool_id():
    """Test Cognito identity pool ID."""
    return "us-east-1:test-identity-pool-123"


@pytest.fixture
def test_agent_runtime_id():
    """Test AgentCore runtime ID."""
    return "test-runtime-123"


@pytest.fixture
def test_agent_runtime_arn():
    """Test AgentCore runtime ARN."""
    return "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/test-runtime-123"
