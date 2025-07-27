"""AWS utility functions for AgentCore CLI."""

import boto3
from boto3.session import Session


def validate_aws_credentials() -> bool:
    """Check if AWS credentials are configured.

    Returns:
        bool: True if valid credentials are found, False otherwise.
    """
    try:
        session = boto3.Session()
        identity = session.client("sts").get_caller_identity()
        return "Account" in identity
    except Exception:
        return False


def get_aws_session(region: str | None = None, profile: str | None = None) -> Session:
    """Get a boto3 session with optional region configuration.

    Args:
        region: Optional AWS region name. If not provided, uses the default region.

    Returns:
        Session: A boto3 session object.
    """
    return boto3.Session(region_name=region, profile_name=profile)


def get_aws_account_id() -> str | None:
    """Get the AWS account ID for the current credentials.

    Returns:
        Optional[str]: The AWS account ID or None if credentials are invalid.
    """
    try:
        sts_client = boto3.client("sts")
        return sts_client.get_caller_identity()["Account"]
    except Exception:
        return None


def get_aws_region() -> str:
    """Get the configured AWS region from the current session.

    Returns:
        str: The current AWS region name.
    """
    return boto3.session.Session().region_name


def get_ecr_repository_uri(repo_name: str, region: str | None = None) -> str | None:
    """Get the URI for an ECR repository.

    Args:
        repo_name: The name of the ECR repository.
        region: Optional region name. If not provided, uses the default region.

    Returns:
        Optional[str]: The repository URI or None if repository does not exist.
    """
    try:
        ecr_client = boto3.client("ecr", region_name=region)
        response = ecr_client.describe_repositories(repositoryNames=[repo_name])
        repositories = response.get("repositories", [])
        if repositories:
            return repositories[0].get("repositoryUri")
        return None
    except Exception:
        return None


def authenticate_with_ecr(region: str | None = None) -> tuple[bool, str]:
    """Get ECR authentication command for Docker login.

    Args:
        region: Optional region name. If not provided, uses the default region.

    Returns:
        Tuple[bool, str]: A tuple containing success status and either the auth command
                          or an error message.
    """
    try:
        if not region:
            region = get_aws_region()

        account_id = get_aws_account_id()
        if not account_id:
            return False, "Failed to get AWS account ID"

        auth_cmd = f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {account_id}.dkr.ecr.{region}.amazonaws.com"
        return True, auth_cmd
    except Exception as e:
        return False, f"Error creating ECR auth command: {str(e)}"
