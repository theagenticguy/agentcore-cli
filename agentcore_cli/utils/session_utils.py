"""Session utilities for AgentCore CLI."""

import uuid
from datetime import datetime


def generate_session_id(prefix: str | None = None) -> str:
    """Generate a unique session ID for agent runtime invocations.

    Args:
        prefix: Optional prefix to add to the session ID.

    Returns:
        str: A string of at least 33 characters as required by AgentCore.
    """
    # Prefix with timestamp for sortability
    timestamp = int(datetime.now().timestamp())

    # Use UUID4 for uniqueness (36 chars)
    unique_id = str(uuid.uuid4())

    # Add custom prefix if provided
    if prefix:
        # Combine for a session ID that's guaranteed to be > 33 chars
        return f"{prefix}-{timestamp}-{unique_id}"

    # Combine for a session ID that's guaranteed to be > 33 chars
    return f"{timestamp}-{unique_id}"
