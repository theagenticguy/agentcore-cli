"""Unit tests for ECR service."""

import pytest
from agentcore_cli.models.resources import ECRRepository
from agentcore_cli.services.ecr import ECRService
from moto import mock_aws
from unittest.mock import patch


class TestECRService:
    """Test cases for ECRService."""

    @mock_aws
    def test_init(self, test_region, aws_session):
        """Test ECRService initialization."""
        service = ECRService(test_region, aws_session)
        assert service.region == test_region
        assert service.session == aws_session
        assert service.cfn_service is not None
        assert service.ecr_client is not None

    @mock_aws
    def test_init_without_session(self, test_region):
        """Test ECRService initialization without session."""
        service = ECRService(test_region)
        assert service.region == test_region
        assert service.session is not None
        assert service.cfn_service is not None
        assert service.ecr_client is not None

    @mock_aws
    def test_create_repository_success(self, test_region, aws_session, test_repository_name):
        """Test successful repository creation."""
        service = ECRService(test_region, aws_session)

        # Mock CloudFormation service
        with patch.object(service.cfn_service, "create_update_stack") as mock_cfn:
            mock_cfn.return_value = (True, "Stack created successfully")

            with patch.object(service.cfn_service, "get_stack_outputs") as mock_outputs:
                mock_outputs.return_value = [
                    {
                        "OutputKey": "RepositoryUri",
                        "OutputValue": f"123456789012.dkr.ecr.{test_region}.amazonaws.com/{test_repository_name}",
                    },
                    {
                        "OutputKey": "RepositoryArn",
                        "OutputValue": f"arn:aws:ecr:{test_region}:123456789012:repository/{test_repository_name}",
                    },
                ]

                success, repository, message = service.create_repository(
                    repository_name=test_repository_name,
                    environment="dev",
                    image_scanning=True,
                    lifecycle_policy_days=30,
                    tags={"Environment": "dev"},
                )

                assert success is True
                assert repository is not None
                assert isinstance(repository, ECRRepository)
                assert repository.name == test_repository_name
                assert (
                    repository.repository_uri
                    == f"123456789012.dkr.ecr.{test_region}.amazonaws.com/{test_repository_name}"
                )

    @mock_aws
    def test_create_repository_template_not_found(self, test_region, aws_session, test_repository_name):
        """Test repository creation with missing template."""
        service = ECRService(test_region, aws_session)

        # Mock template file not found
        with patch("pathlib.Path.exists", return_value=False):
            success, repository, message = service.create_repository(test_repository_name)

            assert success is False
            assert repository is None
            assert "Template file not found" in message

    @mock_aws
    def test_create_repository_cfn_failure(self, test_region, aws_session, test_repository_name):
        """Test repository creation with CloudFormation failure."""
        service = ECRService(test_region, aws_session)

        # Mock CloudFormation failure
        with patch.object(service.cfn_service, "create_update_stack") as mock_cfn:
            mock_cfn.return_value = (False, "CloudFormation error")

            success, repository, message = service.create_repository(test_repository_name)

            assert success is False
            assert repository is None
            assert "Failed to create/update ECR stack" in message

    @mock_aws
    def test_delete_repository_success(self, test_region, aws_session, test_repository_name):
        """Test successful repository deletion."""
        service = ECRService(test_region, aws_session)

        # Mock CloudFormation service
        with patch.object(service.cfn_service, "delete_stack") as mock_delete:
            mock_delete.return_value = (True, "Stack deleted successfully")

            success, message = service.delete_repository(test_repository_name, environment="dev")

            assert success is True
            assert "deleted successfully" in message

    @mock_aws
    def test_delete_repository_force(self, test_region, aws_session, test_repository_name):
        """Test repository deletion with force flag."""
        service = ECRService(test_region, aws_session)

        # Mock ECR client for force deletion
        with patch.object(service.ecr_client, "delete_repository") as mock_ecr_delete:
            mock_ecr_delete.return_value = {}

            success, message = service.delete_repository(test_repository_name, environment="dev", force=True)

            assert success is True
            assert "deleted successfully" in message

    @mock_aws
    def test_get_repository_success(self, test_region, aws_session, test_repository_name):
        """Test successful repository retrieval."""
        service = ECRService(test_region, aws_session)

        # Mock ECR client response
        mock_response = {
            "repositories": [
                {
                    "repositoryName": test_repository_name,
                    "repositoryUri": f"123456789012.dkr.ecr.{test_region}.amazonaws.com/{test_repository_name}",
                    "repositoryArn": f"arn:aws:ecr:{test_region}:123456789012:repository/{test_repository_name}",
                    "createdAt": "2024-01-01T00:00:00Z",
                    "imageScanningConfiguration": {"scanOnPush": True},
                    "encryptionConfiguration": {"encryptionType": "AES256"},
                }
            ]
        }

        with patch.object(service.ecr_client, "describe_repositories", return_value=mock_response):
            success, repository, message = service.get_repository(test_repository_name)

            assert success is True
            assert repository is not None
            assert isinstance(repository, ECRRepository)
            assert repository.name == test_repository_name

    @mock_aws
    def test_get_repository_not_found(self, test_region, aws_session, test_repository_name):
        """Test repository retrieval when not found."""
        service = ECRService(test_region, aws_session)

        # Mock ECR client exception
        with patch.object(service.ecr_client, "describe_repositories") as mock_describe:
            mock_describe.side_effect = Exception("RepositoryNotFoundException")

            success, repository, message = service.get_repository(test_repository_name)

            assert success is False
            assert repository is None
            assert "not found" in message.lower()

    @mock_aws
    def test_list_repositories_success(self, test_region, aws_session):
        """Test successful repository listing."""
        service = ECRService(test_region, aws_session)

        # Mock ECR client response
        mock_response = {
            "repositories": [
                {
                    "repositoryName": "test-repo-1",
                    "repositoryUri": f"123456789012.dkr.ecr.{test_region}.amazonaws.com/test-repo-1",
                    "createdAt": "2024-01-01T00:00:00Z",
                },
                {
                    "repositoryName": "test-repo-2",
                    "repositoryUri": f"123456789012.dkr.ecr.{test_region}.amazonaws.com/test-repo-2",
                    "createdAt": "2024-01-02T00:00:00Z",
                },
            ]
        }

        with patch.object(service.ecr_client, "describe_repositories", return_value=mock_response):
            success, repositories, message = service.list_repositories()

            assert success is True
            assert isinstance(repositories, list)
            assert len(repositories) == 2
            assert repositories[0]["repositoryName"] == "test-repo-1"

    @mock_aws
    def test_get_auth_token_success(self, test_region, aws_session):
        """Test successful auth token retrieval."""
        service = ECRService(test_region, aws_session)

        # Mock ECR client response
        mock_response = {
            "authorizationData": [
                {
                    "authorizationToken": "base64-encoded-token",
                    "expiresAt": "2024-01-01T01:00:00Z",
                    "proxyEndpoint": f"https://123456789012.dkr.ecr.{test_region}.amazonaws.com",
                }
            ]
        }

        with patch.object(service.ecr_client, "get_authorization_token", return_value=mock_response):
            success, auth_data, message = service.get_auth_token()

            assert success is True
            assert auth_data is not None
            assert "authorizationToken" in auth_data
            assert "proxyEndpoint" in auth_data

    @mock_aws
    def test_set_lifecycle_policy_success(self, test_region, aws_session, test_repository_name):
        """Test successful lifecycle policy setting."""
        service = ECRService(test_region, aws_session)

        # Mock ECR client response
        with patch.object(service.ecr_client, "put_lifecycle_policy", return_value={}):
            success, message = service.set_lifecycle_policy(test_repository_name, max_days=30)

            assert success is True
            assert "set successfully" in message

    @mock_aws
    def test_set_lifecycle_policy_failure(self, test_region, aws_session, test_repository_name):
        """Test lifecycle policy setting failure."""
        service = ECRService(test_region, aws_session)

        # Mock ECR client exception
        with patch.object(service.ecr_client, "put_lifecycle_policy") as mock_policy:
            mock_policy.side_effect = Exception("RepositoryNotFoundException")

            success, message = service.set_lifecycle_policy(test_repository_name, max_days=30)

            assert success is False
            assert "Failed to set lifecycle policy" in message

    @pytest.mark.parametrize("environment", [None, "dev", "staging", "prod"])
    @mock_aws
    def test_create_repository_with_different_environments(
        self, test_region, aws_session, test_repository_name, environment
    ):
        """Test repository creation with different environments."""
        service = ECRService(test_region, aws_session)

        # Mock CloudFormation service
        with patch.object(service.cfn_service, "create_update_stack") as mock_cfn:
            mock_cfn.return_value = (True, "Stack created successfully")

            with patch.object(service.cfn_service, "get_stack_outputs") as mock_outputs:
                mock_outputs.return_value = [
                    {
                        "OutputKey": "RepositoryUri",
                        "OutputValue": f"123456789012.dkr.ecr.{test_region}.amazonaws.com/{test_repository_name}",
                    }
                ]

                success, repository, message = service.create_repository(
                    repository_name=test_repository_name, environment=environment
                )

                assert success is True
                assert repository is not None

    @pytest.mark.parametrize("image_scanning", [True, False])
    @mock_aws
    def test_create_repository_with_scanning_options(
        self, test_region, aws_session, test_repository_name, image_scanning
    ):
        """Test repository creation with different scanning options."""
        service = ECRService(test_region, aws_session)

        # Mock CloudFormation service
        with patch.object(service.cfn_service, "create_update_stack") as mock_cfn:
            mock_cfn.return_value = (True, "Stack created successfully")

            with patch.object(service.cfn_service, "get_stack_outputs") as mock_outputs:
                mock_outputs.return_value = [
                    {
                        "OutputKey": "RepositoryUri",
                        "OutputValue": f"123456789012.dkr.ecr.{test_region}.amazonaws.com/{test_repository_name}",
                    }
                ]

                success, repository, message = service.create_repository(
                    repository_name=test_repository_name, image_scanning=image_scanning
                )

                assert success is True
                assert repository is not None
