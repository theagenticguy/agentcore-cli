"""Unit tests for Cognito service."""

import pytest
from agentcore_cli.models.resources import CognitoConfig, CognitoIdentityPool, CognitoUserPool
from agentcore_cli.services.cognito import CognitoService
from moto import mock_aws
from unittest.mock import patch


class TestCognitoService:
    """Test cases for CognitoService."""

    @mock_aws
    def test_init(self, test_region, aws_session):
        """Test CognitoService initialization."""
        service = CognitoService(test_region, aws_session)
        assert service.region == test_region
        assert service.session == aws_session
        assert service.cfn_service is not None
        assert service.cognito_idp_client is not None
        assert service.cognito_identity_client is not None

    @mock_aws
    def test_init_without_session(self, test_region):
        """Test CognitoService initialization without session."""
        service = CognitoService(test_region)
        assert service.region == test_region
        assert service.session is not None
        assert service.cfn_service is not None
        assert service.cognito_idp_client is not None
        assert service.cognito_identity_client is not None

    @mock_aws
    def test_create_cognito_resources_success(self, test_region, aws_session, test_agent_name):
        """Test successful Cognito resources creation."""
        service = CognitoService(test_region, aws_session)

        # Mock CloudFormation service
        with patch.object(service.cfn_service, "create_update_stack") as mock_cfn:
            mock_cfn.return_value = (True, "Stack created successfully")

            with patch.object(service.cfn_service, "get_stack_outputs") as mock_outputs:
                mock_outputs.return_value = [
                    {"OutputKey": "UserPoolId", "OutputValue": "us-east-1_testpool123"},
                    {
                        "OutputKey": "UserPoolArn",
                        "OutputValue": "arn:aws:cognito-idp:us-east-1:123456789012:userpool/us-east-1_testpool123",
                    },
                    {"OutputKey": "UserPoolClientId", "OutputValue": "test-client-id"},
                    {"OutputKey": "IdentityPoolId", "OutputValue": "us-east-1:test-identity-pool-123"},
                    {
                        "OutputKey": "IdentityPoolArn",
                        "OutputValue": "arn:aws:cognito-identity:us-east-1:123456789012:identitypool/us-east-1:test-identity-pool-123",
                    },
                ]

                config = service.create_cognito_resources(
                    agent_name=test_agent_name,
                    environment="dev",
                    resource_name_prefix="agentcore",
                    allow_self_registration=False,
                    email_verification_required=True,
                )

                assert isinstance(config, CognitoConfig)
                assert config.user_pool is not None
                assert config.identity_pool is not None
                assert config.user_pool.user_pool_id == "us-east-1_testpool123"
                assert config.identity_pool.identity_pool_id == "us-east-1:test-identity-pool-123"

    @mock_aws
    def test_create_cognito_resources_template_not_found(self, test_region, aws_session, test_agent_name):
        """Test Cognito resources creation with missing template."""
        service = CognitoService(test_region, aws_session)

        # Mock template file not found
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(Exception, match="Template file not found"):
                service.create_cognito_resources(test_agent_name)

    @mock_aws
    def test_create_cognito_resources_cfn_failure(self, test_region, aws_session, test_agent_name):
        """Test Cognito resources creation with CloudFormation failure."""
        service = CognitoService(test_region, aws_session)

        # Mock CloudFormation failure
        with patch.object(service.cfn_service, "create_update_stack") as mock_cfn:
            mock_cfn.return_value = (False, "CloudFormation error")

            with pytest.raises(Exception, match="Failed to create/update Cognito stack"):
                service.create_cognito_resources(test_agent_name)

    @mock_aws
    def test_delete_cognito_resources_success(self, test_region, aws_session, test_agent_name):
        """Test successful Cognito resources deletion."""
        service = CognitoService(test_region, aws_session)

        # Mock CloudFormation service
        with patch.object(service.cfn_service, "delete_stack") as mock_delete:
            mock_delete.return_value = (True, "Stack deleted successfully")

            success, message = service.delete_cognito_resources(test_agent_name, environment="dev")

            assert success is True
            assert "deleted successfully" in message

    @mock_aws
    def test_get_user_pool_success(self, test_region, aws_session, test_user_pool_id):
        """Test successful user pool retrieval."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito IDP client response
        mock_response = {
            "UserPool": {
                "Id": test_user_pool_id,
                "Name": "test-user-pool",
                "Arn": f"arn:aws:cognito-idp:{test_region}:123456789012:userpool/{test_user_pool_id}",
                "CreationDate": "2024-01-01T00:00:00Z",
            }
        }

        with patch.object(service.cognito_idp_client, "describe_user_pool", return_value=mock_response):
            success, user_pool, message = service.get_user_pool(test_user_pool_id)

            assert success is True
            assert user_pool is not None
            assert isinstance(user_pool, CognitoUserPool)
            assert user_pool.user_pool_id == test_user_pool_id

    @mock_aws
    def test_get_user_pool_not_found(self, test_region, aws_session, test_user_pool_id):
        """Test user pool retrieval when not found."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito IDP client exception
        with patch.object(service.cognito_idp_client, "describe_user_pool") as mock_describe:
            mock_describe.side_effect = Exception("ResourceNotFoundException")

            success, user_pool, message = service.get_user_pool(test_user_pool_id)

            assert success is False
            assert user_pool is None
            assert "resourcenotfound" in message.lower() or "not found" in message.lower()

    @mock_aws
    def test_get_identity_pool_success(self, test_region, aws_session, test_identity_pool_id):
        """Test successful identity pool retrieval."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito Identity client response
        mock_response = {
            "IdentityPool": {
                "IdentityPoolId": test_identity_pool_id,
                "IdentityPoolName": "test-identity-pool",
                "CreationDate": "2024-01-01T00:00:00Z",
            }
        }

        with patch.object(service.cognito_identity_client, "describe_identity_pool", return_value=mock_response):
            success, identity_pool, message = service.get_identity_pool(test_identity_pool_id)

            assert success is True
            assert identity_pool is not None
            assert isinstance(identity_pool, CognitoIdentityPool)
            assert identity_pool.identity_pool_id == test_identity_pool_id

    @mock_aws
    def test_list_user_pools_success(self, test_region, aws_session):
        """Test successful user pools listing."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito IDP client response
        mock_response = {
            "UserPools": [
                {"Id": "us-east-1_pool1", "Name": "test-pool-1", "CreationDate": "2024-01-01T00:00:00Z"},
                {"Id": "us-east-1_pool2", "Name": "test-pool-2", "CreationDate": "2024-01-02T00:00:00Z"},
            ]
        }

        with patch.object(service.cognito_idp_client, "list_user_pools", return_value=mock_response):
            success, user_pools, message = service.list_user_pools()

            assert success is True
            assert isinstance(user_pools, list)
            assert len(user_pools) == 2
            assert user_pools[0]["Id"] == "us-east-1_pool1"

    @mock_aws
    def test_list_identity_pools_success(self, test_region, aws_session):
        """Test successful identity pools listing."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito Identity client response
        mock_response = {
            "IdentityPools": [
                {"IdentityPoolId": "us-east-1:pool1", "IdentityPoolName": "test-identity-pool-1"},
                {"IdentityPoolId": "us-east-1:pool2", "IdentityPoolName": "test-identity-pool-2"},
            ]
        }

        with patch.object(service.cognito_identity_client, "list_identity_pools", return_value=mock_response):
            success, identity_pools, message = service.list_identity_pools()

            assert success is True
            assert isinstance(identity_pools, list)
            assert len(identity_pools) == 2
            assert identity_pools[0]["IdentityPoolId"] == "us-east-1:pool1"

    @mock_aws
    def test_create_user_success(self, test_region, aws_session, test_user_pool_id):
        """Test successful user creation."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito IDP client response
        with patch.object(service.cognito_idp_client, "admin_create_user", return_value={}):
            success, message = service.create_user(
                user_pool_id=test_user_pool_id,
                username="testuser",
                password="TestPass123!",  # pragma: allowlist secret
                email="test@example.com",
                temp_password=True,
            )

            assert success is True
            assert "created successfully" in message

    @mock_aws
    def test_delete_user_success(self, test_region, aws_session, test_user_pool_id):
        """Test successful user deletion."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito IDP client response
        with patch.object(service.cognito_idp_client, "admin_delete_user", return_value={}):
            success, message = service.delete_user(test_user_pool_id, "testuser")

            assert success is True
            assert "deleted successfully" in message

    @mock_aws
    def test_list_users_success(self, test_region, aws_session, test_user_pool_id):
        """Test successful users listing."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito IDP client response
        mock_response = {
            "Users": [
                {"Username": "user1", "Attributes": [{"Name": "email", "Value": "user1@example.com"}]},
                {"Username": "user2", "Attributes": [{"Name": "email", "Value": "user2@example.com"}]},
            ]
        }

        with patch.object(service.cognito_idp_client, "list_users", return_value=mock_response):
            success, users, message = service.list_users(test_user_pool_id)

            assert success is True
            assert isinstance(users, list)
            assert len(users) == 2
            assert users[0]["Username"] == "user1"

    @mock_aws
    def test_check_user_pool_exists_true(self, test_region, aws_session, test_user_pool_id):
        """Test user pool existence check when it exists."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito IDP client response
        with patch.object(service.cognito_idp_client, "describe_user_pool", return_value={"UserPool": {}}):
            exists = service.check_user_pool_exists(test_user_pool_id)

            assert exists is True

    @mock_aws
    def test_check_user_pool_exists_false(self, test_region, aws_session, test_user_pool_id):
        """Test user pool existence check when it doesn't exist."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito IDP client exception
        with patch.object(service.cognito_idp_client, "describe_user_pool") as mock_describe:
            mock_describe.side_effect = Exception("ResourceNotFoundException")

            exists = service.check_user_pool_exists(test_user_pool_id)

            assert exists is False

    @mock_aws
    def test_check_identity_pool_exists_true(self, test_region, aws_session, test_identity_pool_id):
        """Test identity pool existence check when it exists."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito Identity client response
        with patch.object(service.cognito_identity_client, "describe_identity_pool", return_value={"IdentityPool": {}}):
            exists = service.check_identity_pool_exists(test_identity_pool_id)

            assert exists is True

    @mock_aws
    def test_check_identity_pool_exists_false(self, test_region, aws_session, test_identity_pool_id):
        """Test identity pool existence check when it doesn't exist."""
        service = CognitoService(test_region, aws_session)

        # Mock Cognito Identity client exception
        with patch.object(service.cognito_identity_client, "describe_identity_pool") as mock_describe:
            mock_describe.side_effect = Exception("ResourceNotFoundException")

            exists = service.check_identity_pool_exists(test_identity_pool_id)

            assert exists is False

    @pytest.mark.parametrize("environment", [None, "dev", "staging", "prod"])
    @mock_aws
    def test_create_cognito_resources_with_different_environments(
        self, test_region, aws_session, test_agent_name, environment
    ):
        """Test Cognito resources creation with different environments."""
        service = CognitoService(test_region, aws_session)

        # Mock CloudFormation service
        with patch.object(service.cfn_service, "create_update_stack") as mock_cfn:
            mock_cfn.return_value = (True, "Stack created successfully")

            with patch.object(service.cfn_service, "get_stack_outputs") as mock_outputs:
                mock_outputs.return_value = [
                    {"OutputKey": "UserPoolId", "OutputValue": "us-east-1_testpool123"},
                    {"OutputKey": "IdentityPoolId", "OutputValue": "us-east-1:test-identity-pool-123"},
                ]

                config = service.create_cognito_resources(agent_name=test_agent_name, environment=environment)

                assert isinstance(config, CognitoConfig)
                assert config.user_pool is not None
                assert config.identity_pool is not None

    @pytest.mark.parametrize("allow_self_registration", [True, False])
    @pytest.mark.parametrize("email_verification_required", [True, False])
    @mock_aws
    def test_create_cognito_resources_with_registration_options(
        self, test_region, aws_session, test_agent_name, allow_self_registration, email_verification_required
    ):
        """Test Cognito resources creation with different registration options."""
        service = CognitoService(test_region, aws_session)

        # Mock CloudFormation service
        with patch.object(service.cfn_service, "create_update_stack") as mock_cfn:
            mock_cfn.return_value = (True, "Stack created successfully")

            with patch.object(service.cfn_service, "get_stack_outputs") as mock_outputs:
                mock_outputs.return_value = [
                    {"OutputKey": "UserPoolId", "OutputValue": "us-east-1_testpool123"},
                    {"OutputKey": "IdentityPoolId", "OutputValue": "us-east-1:test-identity-pool-123"},
                ]

                config = service.create_cognito_resources(
                    agent_name=test_agent_name,
                    allow_self_registration=allow_self_registration,
                    email_verification_required=email_verification_required,
                )

                assert isinstance(config, CognitoConfig)
