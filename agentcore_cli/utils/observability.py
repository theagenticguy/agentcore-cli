"""Observability utilities for AgentCore Platform CLI.

This module provides utilities for setting up and managing AWS observability features
including CloudWatch Transaction Search for cost-effective tracing.
"""

import json
import time

import click
from botocore.exceptions import ClientError

from agentcore_cli.utils.aws_utils import get_aws_account_id, get_aws_session, validate_aws_credentials
from agentcore_cli.utils.validation import validate_region


class TransactionSearchManager:
    """Manages AWS CloudWatch Transaction Search configuration."""

    def __init__(self, region: str):
        """Initialize the Transaction Search manager.

        Args:
            region: AWS region to operate in
        """
        self.region = region

        # Validate AWS credentials first
        if not validate_aws_credentials():
            raise ValueError("AWS credentials not configured")

        # Validate region format
        is_valid, error_msg = validate_region(region)
        if not is_valid:
            raise ValueError(f"Invalid region: {error_msg}")

        # Create AWS clients using the session utility
        session = get_aws_session(region=region)
        self.xray_client = session.client("xray")
        self.logs_client = session.client("logs")
        self.account_id = get_aws_account_id()

    def is_transaction_search_enabled(self) -> tuple[bool, str | None]:
        """Check if Transaction Search is enabled.

        Returns:
            Tuple of (is_enabled, status_message)
        """
        try:
            response = self.xray_client.get_trace_segment_destination()
            destination = response.get("Destination")
            status = response.get("Status")

            if destination == "CloudWatchLogs" and status == "ACTIVE":
                return True, "Transaction Search is enabled and active"
            else:
                return False, f"Transaction Search status: destination={destination}, status={status}"

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ResourceNotFoundException":
                return False, "Transaction Search not configured"
            else:
                return False, f"Error checking Transaction Search: {e}"

    def create_resource_policy(self) -> bool:
        """Create the resource policy for X-Ray to send traces to CloudWatch Logs.

        Returns:
            True if policy was created successfully, False otherwise
        """
        try:
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "TransactionSearchXRayAccess",
                        "Effect": "Allow",
                        "Principal": {"Service": "xray.amazonaws.com"},
                        "Action": "logs:PutLogEvents",
                        "Resource": [
                            f"arn:aws:logs:{self.region}:{self.account_id}:log-group:aws/spans:*",
                            f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/application-signals/data:*",
                        ],
                        "Condition": {
                            "ArnLike": {"aws:SourceArn": f"arn:aws:logs:{self.region}:{self.account_id}:*"},
                            "StringEquals": {"aws:SourceAccount": self.account_id},
                        },
                    }
                ],
            }

            self.logs_client.put_resource_policy(
                policyName="AgentCoreTransactionSearchPolicy", policyDocument=json.dumps(policy_document)
            )

            return True

        except ClientError as e:
            click.echo(f"   ❌ Failed to create resource policy: {e}")
            return False

    def configure_trace_destination(self) -> bool:
        """Configure X-Ray to send traces to CloudWatch Logs.

        Returns:
            True if destination was configured successfully, False otherwise
        """
        try:
            self.xray_client.update_trace_segment_destination(Destination="CloudWatchLogs")
            return True

        except ClientError as e:
            click.echo(f"   ❌ Failed to configure trace destination: {e}")
            return False

    def configure_indexing_rule(self, sampling_percentage: float = 1.0) -> bool:
        """Configure the span indexing rule.

        Args:
            sampling_percentage: Percentage of spans to index (default 1.0 for free tier)

        Returns:
            True if indexing rule was configured successfully, False otherwise
        """
        try:
            self.xray_client.update_indexing_rule(
                Name="Default", Rule={"Probabilistic": {"DesiredSamplingPercentage": sampling_percentage}}
            )
            return True

        except ClientError as e:
            click.echo(f"   ❌ Failed to configure indexing rule: {e}")
            return False

    def enable_transaction_search(self, sampling_percentage: float = 1.0) -> bool:
        """Enable Transaction Search with all required configuration.

        Args:
            sampling_percentage: Percentage of spans to index (default 1.0 for free tier)

        Returns:
            True if Transaction Search was enabled successfully, False otherwise
        """
        click.echo("   🔄 Enabling Transaction Search...")

        # Step 1: Create resource policy
        click.echo("   📋 Creating resource policy...")
        if not self.create_resource_policy():
            return False

        # Step 2: Configure trace destination
        click.echo("   🎯 Configuring trace destination...")
        if not self.configure_trace_destination():
            return False

        # Step 3: Configure indexing rule
        click.echo(f"   📊 Configuring indexing rule ({sampling_percentage}% sampling)...")
        if not self.configure_indexing_rule(sampling_percentage):
            return False

        # Step 4: Wait a moment for configuration to propagate
        click.echo("   ⏳ Waiting for configuration to propagate...")
        time.sleep(5)

        # Step 5: Verify configuration
        is_enabled, status_msg = self.is_transaction_search_enabled()
        if is_enabled:
            click.echo("   ✅ Transaction Search enabled successfully")
            click.echo("   📝 Note: It may take up to 10 minutes for spans to become available for search")
            return True
        else:
            click.echo(f"   ❌ Transaction Search enablement verification failed: {status_msg}")
            return False


def validate_and_enable_transaction_search(region: str = "us-west-2", interactive: bool = True) -> bool:
    """Validate Transaction Search status and enable if needed.

    Args:
        region: AWS region to check/configure
        interactive: Whether to prompt user for confirmation

    Returns:
        True if Transaction Search is enabled (or was enabled successfully), False otherwise
    """
    try:
        manager = TransactionSearchManager(region)

        # Check current status
        is_enabled, status_msg = manager.is_transaction_search_enabled()

        if is_enabled:
            click.echo("   ✅ Transaction Search is already enabled")
            return True

        click.echo(f"   ℹ️  Transaction Search status: {status_msg}")

        if interactive:
            enable_search = click.confirm(
                "   Would you like to enable Transaction Search for cost-effective observability?", default=True
            )
            if not enable_search:
                click.echo("   ⏭️  Skipped Transaction Search setup")
                return False

        # Get sampling percentage if interactive
        sampling_percentage = 1.0
        if interactive:
            custom_sampling = click.confirm(
                "   Use custom sampling percentage? (default: 1% - free tier)", default=False
            )
            if custom_sampling:
                sampling_percentage = click.prompt("   Enter sampling percentage (1-100)", default=1.0, type=float)
                if sampling_percentage < 1 or sampling_percentage > 100:
                    click.echo("   ❌ Sampling percentage must be between 1 and 100")
                    sampling_percentage = 1.0

        # Enable Transaction Search
        return manager.enable_transaction_search(sampling_percentage)

    except ValueError as e:
        click.echo(f"   ❌ {e}")
        return False
    except Exception as e:
        click.echo(f"   ❌ Unexpected error: {e}")
        return False


def get_transaction_search_status(region: str = "us-west-2") -> dict[str, str | bool | None]:
    """Get detailed Transaction Search status information.

    Args:
        region: AWS region to check

    Returns:
        Dictionary with status information
    """
    try:
        manager = TransactionSearchManager(region)
        is_enabled, status_msg = manager.is_transaction_search_enabled()

        return {
            "enabled": is_enabled,
            "status_message": status_msg,
            "region": region,
            "account_id": get_aws_account_id(),
        }
    except Exception as e:
        return {"enabled": False, "status_message": f"Error checking status: {e}", "region": region, "account_id": None}
