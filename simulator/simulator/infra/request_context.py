"""Request context management for distributed system simulation.

This module provides RequestContext for tracking requests across components.

Moved from models/internal.py:50-52 to infra as it's a generic concept
applicable to any distributed system simulation.

Phase 3 enhancements: Added request ID generation utilities and factory functions.
"""

import uuid
from typing import Optional
from pydantic import BaseModel


class RequestContext(BaseModel):
    """Context for tracking a request through the system.

    Contains request-specific metadata that flows with messages across
    components.

    Moved from models/internal.py (lines 50-52).
    """

    request_id: str
    retries: int = 0


# Phase 3: Request ID generation utilities

def generate_request_id() -> str:
    """Generate a unique request ID using UUID4.

    Returns:
        A unique request ID string

    Example:
        >>> request_id = generate_request_id()
        >>> len(request_id) == 36  # UUID4 format
        True
    """
    return str(uuid.uuid4())


def create_request_context(
    request_id: Optional[str] = None,
    retries: int = 0,
    **kwargs
) -> RequestContext:
    """Factory function for creating RequestContext instances.

    Automatically generates a request ID if not provided.

    Args:
        request_id: Optional request ID. If None, generates a new UUID
        retries: Number of retries for this request (default: 0)
        **kwargs: Additional fields to pass to RequestContext

    Returns:
        A new RequestContext instance

    Example:
        >>> ctx = create_request_context()
        >>> ctx.request_id is not None
        True
        >>> ctx.retries
        0
        >>> ctx2 = create_request_context(request_id="custom-123", retries=2)
        >>> ctx2.request_id
        'custom-123'
    """
    if request_id is None:
        request_id = generate_request_id()

    return RequestContext(request_id=request_id, retries=retries, **kwargs)
