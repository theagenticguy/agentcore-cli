"""Validation utilities for AgentCore CLI."""

import re
from agentcore_cli.utils.command_executor import execute_command


def validate_aws_cli() -> bool:
    """Check if AWS CLI is available on the system.

    Returns:
        bool: True if AWS CLI is available, False otherwise.
    """
    try:
        returncode, _, _ = execute_command(["aws", "--version"], log_output=False)
        return returncode == 0
    except FileNotFoundError:
        return False


def validate_repo_name(repo_name: str) -> tuple[bool, str]:
    """Validate ECR repository name.

    Repository names must match: `[a-z0-9][a-z0-9._-]{0,254}`

    Args:
        repo_name: Repository name to validate.

    Returns:
        uple[bool, str]: Success status and error message if any.
    """
    pattern: re.Pattern = re.compile(r"^[a-z0-9][a-z0-9._-]{0,254}$")

    if not pattern.match(repo_name):
        return False, "Repository names must match: [a-z0-9][a-z0-9._-]{0,254}"

    return True, ""


def validate_arn(arn: str) -> tuple[bool, str]:
    """Validate AWS ARN format.

    Args:
        arn: ARN to validate.

    Returns:
        Tuple[bool, str]: Success status and error message if any.
    """
    pattern: re.Pattern = re.compile(r"^arn:(?:aws|aws-cn|aws-us-gov):([^:]*):([^:]*):([^:]*):([^:]*)(?::(.*))?$")

    if not pattern.match(arn):
        return False, "Invalid ARN format. Expected: arn:partition:service:region:account-id:resource"

    return True, ""


def validate_region(region: str) -> tuple[bool, str]:
    """Validate AWS region format.

    Args:
        region: AWS region to validate.

    Returns:
        Tuple[bool, str]: Success status and error message if any.
    """
    pattern: re.Pattern = re.compile(r"^[a-z]{2}-[a-z]+-\d+$")

    if not pattern.match(region):
        return False, "Invalid region format. Expected: e.g., us-east-1, eu-west-2"

    return True, ""


def validate_agent_name(name: str) -> tuple[bool, str]:
    """Validate agent name.

    Agent names must be 3-64 characters, start with a letter, and contain only
    letters, numbers, hyphens, and underscores.

    Args:
        name: Agent name to validate.

    Returns:
        Tuple[bool, str]: Success status and error message if any.
    """
    pattern: re.Pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,63}$")

    if not pattern.match(name):
        return False, (
            "Agent names must be 3-64 characters, start with a letter, "
            "and contain only letters, numbers, hyphens, and underscores."
        )

    return True, ""
