class NexraError(Exception):
    """Base exception for all Nexra application errors.

    Attributes:
        status_code: HTTP status code to return.
        code: Machine-readable error code string (e.g., 'POLICY_BLOCKED').
        message: Human-readable error message.
        details: Optional dict with additional context.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


# Auth errors
UNAUTHORIZED = "UNAUTHORIZED"
INVALID_DELEGATION_TOKEN = "INVALID_DELEGATION_TOKEN"
AGENT_QUARANTINED = "AGENT_QUARANTINED"
INSUFFICIENT_ROLE = "INSUFFICIENT_ROLE"

# Validation errors
INVALID_SCHEMA = "INVALID_SCHEMA"
INVALID_WEBHOOK_URL = "INVALID_WEBHOOK_URL"
INVALID_AGENT_ID = "INVALID_AGENT_ID"
INVALID_REQUEST = "INVALID_REQUEST"
MAX_DEPTH_EXCEEDED = "MAX_DEPTH_EXCEEDED"
SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
OUTPUT_SCHEMA_FAILED = "OUTPUT_SCHEMA_FAILED"

# Policy errors
POLICY_BLOCKED = "POLICY_BLOCKED"

# Budget errors
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"

# Delegation errors
AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
DELEGATION_NOT_FOUND = "DELEGATION_NOT_FOUND"
POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
DELEGATION_TIMEOUT = "DELEGATION_TIMEOUT"
DELEGATION_ALREADY_COMPLETE = "DELEGATION_ALREADY_COMPLETE"

# External errors
CALLEE_WEBHOOK_FAILED = "CALLEE_WEBHOOK_FAILED"
WEBHOOK_SIGNATURE_REJECTED = "WEBHOOK_SIGNATURE_REJECTED"
EMBEDDING_SERVICE_UNAVAILABLE = "EMBEDDING_SERVICE_UNAVAILABLE"

# Rate limit
RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

# Internal
INTERNAL_ERROR = "INTERNAL_ERROR"
