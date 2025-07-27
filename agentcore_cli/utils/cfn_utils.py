from boto3.session import Session
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
import botocore.exceptions
import time
from datetime import datetime, timedelta
from loguru import logger

if TYPE_CHECKING:
    from mypy_boto3_cloudformation.type_defs import ParameterTypeDef
    from mypy_boto3_cloudformation.client import CloudFormationClient
else:
    ParameterTypeDef = object
    CloudFormationClient = object


class CFNService:
    """CloudFormation service with robust stack management and polling capabilities."""

    # CloudFormation stack states
    CREATE_IN_PROGRESS = "CREATE_IN_PROGRESS"
    CREATE_COMPLETE = "CREATE_COMPLETE"
    CREATE_FAILED = "CREATE_FAILED"
    UPDATE_IN_PROGRESS = "UPDATE_IN_PROGRESS"
    UPDATE_COMPLETE = "UPDATE_COMPLETE"
    UPDATE_FAILED = "UPDATE_FAILED"
    DELETE_IN_PROGRESS = "DELETE_IN_PROGRESS"
    DELETE_COMPLETE = "DELETE_COMPLETE"
    DELETE_FAILED = "DELETE_FAILED"
    ROLLBACK_IN_PROGRESS = "ROLLBACK_IN_PROGRESS"
    ROLLBACK_COMPLETE = "ROLLBACK_COMPLETE"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"

    # Success states
    SUCCESS_STATES = {CREATE_COMPLETE, UPDATE_COMPLETE, DELETE_COMPLETE}

    # Failure states
    FAILURE_STATES = {CREATE_FAILED, UPDATE_FAILED, DELETE_FAILED, ROLLBACK_FAILED}

    # In-progress states
    IN_PROGRESS_STATES = {CREATE_IN_PROGRESS, UPDATE_IN_PROGRESS, DELETE_IN_PROGRESS, ROLLBACK_IN_PROGRESS}

    def __init__(self, region: str):
        self.session = Session(region_name=region)
        self.cfn_client: Any = self.session.client("cloudformation")

    def _stack_exists(self, stack_name: str) -> bool:
        """Check if a CloudFormation stack exists."""
        try:
            self.cfn_client.describe_stacks(StackName=stack_name)
            return True
        except Exception:
            logger.info(f"Stack {stack_name} does not exist, creating it...")
            return False

    def wait_for_stack_completion(
        self, stack_name: str, timeout_minutes: int = 30, poll_interval: int = 10
    ) -> tuple[bool, str, str]:
        """Wait for CloudFormation stack operation to complete.

        Args:
            stack_name: Name of the CloudFormation stack
            timeout_minutes: Maximum time to wait in minutes (default: 30)
            poll_interval: Polling interval in seconds (default: 10)

        Returns:
            Tuple of (success, final_status, reason)
        """
        start_time = datetime.now()
        timeout = timedelta(minutes=timeout_minutes)

        logger.info(f"Waiting for stack '{stack_name}' to complete (timeout: {timeout_minutes}m)...")

        while datetime.now() - start_time < timeout:
            try:
                status = self.get_stack_status(stack_name)
                logger.debug(f"Stack '{stack_name}' status: {status}")

                # Check for completion states
                if status in self.SUCCESS_STATES:
                    logger.success(f"Stack '{stack_name}' completed successfully with status: {status}")
                    return True, status, "Stack operation completed successfully"

                # Check for failure states
                if status in self.FAILURE_STATES:
                    # Get more detailed error information
                    reason = self._get_stack_failure_reason(stack_name)
                    logger.error(f"Stack '{stack_name}' failed with status: {status}. Reason: {reason}")
                    return False, status, reason

                # Still in progress - continue waiting
                if status in self.IN_PROGRESS_STATES:
                    elapsed = datetime.now() - start_time
                    elapsed_str = f"{int(elapsed.total_seconds())}s"
                    logger.info(
                        f"Stack '{stack_name}' still {status.lower().replace('_', ' ')} ({elapsed_str} elapsed)..."
                    )
                    time.sleep(poll_interval)
                    continue

                # Unexpected status
                logger.warning(f"Stack '{stack_name}' has unexpected status: {status}")
                time.sleep(poll_interval)

            except Exception as e:
                if "does not exist" in str(e):
                    # Stack was deleted
                    return True, self.DELETE_COMPLETE, "Stack was deleted"

                logger.error(f"Error checking stack status: {str(e)}")
                time.sleep(poll_interval)

        # Timeout reached
        try:
            final_status = self.get_stack_status(stack_name)
        except Exception:
            final_status = "UNKNOWN"

        timeout_msg = f"Timeout after {timeout_minutes} minutes waiting for stack completion"
        logger.error(f"Stack '{stack_name}' operation timed out. Final status: {final_status}")
        return False, final_status, timeout_msg

    def _get_stack_failure_reason(self, stack_name: str) -> str:
        """Get detailed failure reason for a failed stack."""
        try:
            # Get stack events to find the failure reason
            response = self.cfn_client.describe_stack_events(StackName=stack_name)
            events = response.get("StackEvents", [])

            # Look for failure events
            for event in events:
                status = event.get("ResourceStatus", "")
                if "FAILED" in status:
                    reason = event.get("ResourceStatusReason", "Unknown failure")
                    resource_type = event.get("ResourceType", "Unknown")
                    logical_id = event.get("LogicalResourceId", "Unknown")
                    return f"{resource_type} '{logical_id}': {reason}"

            return "Unknown failure reason"

        except Exception as e:
            return f"Could not retrieve failure reason: {str(e)}"

    def create_update_stack(
        self,
        stack_name: str,
        template_body: str,
        parameters: Sequence[ParameterTypeDef],
        wait_for_completion: bool = True,
        timeout_minutes: int = 30,
    ) -> tuple[bool, str]:
        """Create or update a CloudFormation stack with optional completion waiting.

        Args:
            stack_name: Name of the CloudFormation stack
            template_body: CloudFormation template content
            parameters: Stack parameters
            wait_for_completion: Whether to wait for operation completion (default: True)
            timeout_minutes: Timeout for waiting (default: 30)

        Returns:
            Tuple of (success, message)
        """
        operation_type = "update" if self._stack_exists(stack_name) else "create"

        try:
            if operation_type == "update":
                logger.info(f"Updating stack {stack_name}")
                try:
                    self.cfn_client.update_stack(
                        StackName=stack_name,
                        TemplateBody=template_body,
                        Parameters=parameters,
                        Capabilities=["CAPABILITY_NAMED_IAM"],
                    )
                except botocore.exceptions.ClientError as e:
                    if "No updates are to be performed" in str(e):
                        logger.info(f"No updates needed for stack {stack_name}")
                        return True, "No updates needed"
                    else:
                        logger.error(f"Failed to update stack {stack_name}: {e}")
                        return False, f"Update failed: {str(e)}"
            else:
                logger.info(f"Creating stack {stack_name}")
                self.cfn_client.create_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=["CAPABILITY_NAMED_IAM"],
                )

            # Wait for completion if requested
            if wait_for_completion:
                success, status, reason = self.wait_for_stack_completion(stack_name, timeout_minutes)
                if success:
                    return True, f"Stack {operation_type} completed successfully"
                else:
                    return False, f"Stack {operation_type} failed: {reason}"
            else:
                return True, f"Stack {operation_type} initiated"

        except Exception as e:
            error_msg = f"Failed to {operation_type} stack {stack_name}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def delete_stack(
        self, stack_name: str, wait_for_completion: bool = True, timeout_minutes: int = 20
    ) -> tuple[bool, str]:
        """Delete a CloudFormation stack with optional completion waiting.

        Args:
            stack_name: Name of the CloudFormation stack
            wait_for_completion: Whether to wait for deletion completion (default: True)
            timeout_minutes: Timeout for waiting (default: 20)

        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Deleting stack {stack_name}")
            self.cfn_client.delete_stack(StackName=stack_name)

            if wait_for_completion:
                success, status, reason = self.wait_for_stack_completion(stack_name, timeout_minutes)
                if success:
                    return True, f"Stack deletion completed successfully"
                else:
                    return False, f"Stack deletion failed: {reason}"
            else:
                return True, f"Stack deletion initiated"

        except Exception as e:
            error_msg = f"Failed to delete stack {stack_name}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def get_stack_status(self, stack_name: str) -> str:
        """Get the current status of a CloudFormation stack."""
        response = self.cfn_client.describe_stacks(StackName=stack_name)
        return str(response["Stacks"][0]["StackStatus"])

    def get_stack_outputs(self, stack_name: str) -> list[dict]:
        """Get the outputs of a CloudFormation stack.

        Args:
            stack_name: Name of the CloudFormation stack

        Returns:
            List of stack outputs

        Raises:
            Exception: If stack is not in a completed state
        """
        try:
            status = self.get_stack_status(stack_name)
            if status not in self.SUCCESS_STATES:
                raise Exception(f"Cannot get outputs for stack in status: {status}")

            response = self.cfn_client.describe_stacks(StackName=stack_name)
            outputs = response["Stacks"][0].get("Outputs", [])
            return list(outputs) if outputs else []

        except Exception as e:
            logger.error(f"Failed to get stack outputs for {stack_name}: {str(e)}")
            raise

    def stack_exists_and_complete(self, stack_name: str) -> bool:
        """Check if stack exists and is in a completed/stable state."""
        try:
            status = self.get_stack_status(stack_name)
            return status in self.SUCCESS_STATES
        except Exception:
            return False
