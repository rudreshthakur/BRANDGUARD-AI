class DomainError(Exception):
    """A user-facing, safe-to-display error with an HTTP status code."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
