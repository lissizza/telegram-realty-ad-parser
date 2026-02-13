"""
Custom exceptions for the application
"""


class LLMQuotaExceededError(Exception):
    """Raised when LLM API quota/rate limit is exceeded"""
    
    def __init__(
        self, 
        message: str, 
        provider: str = "unknown", 
        original_error: Exception = None,
        is_quota: bool = False,
        is_concurrency: bool = False,
        is_rate_limit: bool = False
    ):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        self.is_quota = is_quota  # Insufficient balance - stop processing
        self.is_concurrency = is_concurrency  # Concurrency limit - retry with backoff
        self.is_rate_limit = is_rate_limit  # Generic rate limit - retry
        super().__init__(message)


class LLMRateLimitError(Exception):
    """Raised when LLM API rate limit is hit"""
    
    def __init__(self, message: str, provider: str = "unknown", retry_after: int = None):
        self.message = message
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(message)
