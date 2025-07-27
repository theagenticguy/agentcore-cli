"""Command execution utilities with security validation for AgentCore CLI.

This module provides a centralized utility for executing shell commands with security validation.
It ensures that all subprocess calls consistently capture stdout and stderr while maintaining
proper error handling and security validation for AgentCore CLI use cases.

The module is designed to be used as a utility for other modules in the AgentCore CLI.
"""

import subprocess  # nosec: B404
import re
from typing import Union
from loguru import logger


def execute_command(
    cmd: Union[list[str], str], check: bool = False, text: bool = True, log_cmd: bool = True, log_output: bool = True
) -> tuple[int, str, str]:
    """Execute a shell command and capture all output with security validation.

    This is a centralized utility to ensure all subprocess calls consistently capture
    stdout and stderr while maintaining proper error handling and security validation
    for AgentCore CLI use cases.

    Args:
        cmd: Command to execute, either as list of arguments or shell string
        check: Whether to raise an exception if command fails
        text: Whether to decode output as text (vs bytes)
        log_cmd: Whether to log the command being executed
        log_output: Whether to log command output

    Returns:
        Tuple[int, str, str]: (return_code, stdout, stderr)
    """
    if log_cmd:
        if isinstance(cmd, list):
            logger.info(f"Executing: {' '.join(cmd)}")
        else:
            logger.info(f"Executing: {cmd}")

    # Validate command for security
    is_valid, error_msg = _validate_command_security(cmd)
    if not is_valid:
        logger.warning(f"Command rejected by security validation: {error_msg}")
        return -1, "", f"Command rejected: {error_msg}"

    try:
        # Handle shell commands with pipes for AWS ECR authentication
        if isinstance(cmd, str) and "|" in cmd and "aws ecr get-login-password" in cmd:
            # Special case for ECR authentication command - requires shell=True for pipe
            # nosemgrep: subprocess-shell-true
            result = subprocess.run(cmd, shell=True, check=check, text=text, capture_output=True)  # nosec: B602 inputs are validated
        else:
            # Standard execution without shell for security
            result = subprocess.run(cmd, shell=False, check=check, text=text, capture_output=True)  # nosec: B603 inputs are validated

        if log_output:
            if result.returncode == 0:
                if result.stdout and result.stdout.strip():
                    logger.debug(f"Command output: {result.stdout.strip()}")
            else:
                if result.stderr and result.stderr.strip():
                    logger.error(f"Command error: {result.stderr.strip()}")

        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}: {e.stderr}")
        return e.returncode, e.stdout or "", e.stderr or ""
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        return -1, "", str(e)


def _validate_command_security(cmd: Union[list[str], str]) -> tuple[bool, str]:
    """Validate command for security based on AgentCore CLI use cases.

    This function allows only specific command patterns that are legitimate
    for AgentCore CLI operations and prevents command injection.

    Args:
        cmd: Command to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Convert command to string for validation
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
        first_arg = cmd[0] if cmd else ""
    else:
        cmd_str = cmd
        first_arg = cmd_str.split()[0] if cmd_str.strip() else ""

    # Define allowed command patterns for AgentCore CLI
    allowed_commands = {
        # Docker commands
        "docker": ["build", "tag", "push", "pull", "images", "inspect", "rmi", "buildx"],
        # AWS CLI commands
        "aws": ["--version", "ecr", "sts"],
    }

    # Check if command starts with allowed binary
    if first_arg not in allowed_commands:
        return False, f"Command must start with one of: {', '.join(allowed_commands.keys())}"

    # For Docker commands, validate subcommands
    if first_arg == "docker":
        if isinstance(cmd, list) and len(cmd) > 1:
            subcommand = cmd[1]
            if subcommand not in allowed_commands["docker"]:
                return (
                    False,
                    f"Docker subcommand '{subcommand}' not allowed. Allowed: {', '.join(allowed_commands['docker'])}",
                )
        elif isinstance(cmd, str):
            # Extract subcommand from string
            parts = cmd_str.split()
            if len(parts) > 1:
                subcommand = parts[1]
                if subcommand not in allowed_commands["docker"]:
                    return (
                        False,
                        f"Docker subcommand '{subcommand}' not allowed. Allowed: {', '.join(allowed_commands['docker'])}",
                    )

    # Special validation for AWS ECR authentication (allows pipes in this specific case)
    if "aws ecr get-login-password" in cmd_str and "docker login" in cmd_str:
        # Validate the ECR authentication pattern
        ecr_pattern = re.compile(
            r"aws ecr get-login-password --region [\w-]+ \| docker login --username AWS --password-stdin [\w.-]+\.dkr\.ecr\.[\w-]+\.amazonaws\.com"
        )
        if ecr_pattern.match(cmd_str.strip()):
            return True, ""
        else:
            return False, "Invalid ECR authentication command pattern"

    # Check for dangerous characters that could indicate command injection
    dangerous_chars = ["$", "`", "&&", ";"]
    if any(char in cmd_str for char in dangerous_chars):
        return False, f"Command contains potentially dangerous characters: {', '.join(dangerous_chars)}"

    # Allow pipes only for specific AWS ECR authentication
    if "|" in cmd_str and "aws ecr get-login-password" not in cmd_str:
        return False, "Pipe character not allowed except for AWS ECR authentication"

    # Additional validation for argument patterns
    # Check for standalone 'rm' command (not as part of other words like '--platform')
    rm_pattern = re.compile(r"\brm\b")
    if rm_pattern.search(cmd_str) and not cmd_str.startswith("docker rmi"):
        return False, "Remove commands not allowed except 'docker rmi'"

    return True, ""
