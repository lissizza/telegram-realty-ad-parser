"""
Custom exceptions for the application
"""


class LLMQuotaExceededError(Exception):
    """Raised when LLM API quota is exceeded"""
    
    def __init__(self, message: str, provider: str = "unknown", original_error: Exception = None):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


class LLMRateLimitError(Exception):
    """Raised when LLM API rate limit is hit"""
    
    def __init__(self, message: str, provider: str = "unknown", retry_after: int = None):
        self.message = message
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(message)
