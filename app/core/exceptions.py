"""Custom exception definitions."""


class FinancialAssistantException(Exception):
    """Base exception class for application errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class UserNotFoundException(FinancialAssistantException):
    """Raised when requested user is not found."""
    pass


class AgentExecutionException(FinancialAssistantException):
    """Raised when LangGraph agent fails execution."""
    pass


class DataFetchException(FinancialAssistantException):
    """Raised when external financial data API fails."""
    pass


class DocumentParseException(FinancialAssistantException):
    """Raised when document ingestion or parsing fails."""
    pass
