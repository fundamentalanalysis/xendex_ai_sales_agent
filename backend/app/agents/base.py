"""Base agent class for all research agents."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import structlog

from app.integrations.openai_client import OpenAIClient


class BaseAgent(ABC):
    """Base class for all agents in the research pipeline."""
    
    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        self.logger = structlog.get_logger(agent=self.__class__.__name__)
        self.openai_client = openai_client or OpenAIClient()
    
    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Execute the agent's main task."""
        pass
    
    def _log_start(self, **context):
        """Log agent start."""
        self.logger.info("Agent started", **context)
    
    def _log_complete(self, **context):
        """Log agent completion."""
        self.logger.info("Agent completed", **context)
    
    def _log_error(self, error: Exception, **context):
        """Log agent error."""
        self.logger.error("Agent failed", error=str(error), **context)


class AgentResult:
    """Wrapper for agent results with success/failure tracking."""
    
    def __init__(
        self, 
        success: bool, 
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.data = data or {}
        self.error = error
    
    @classmethod
    def ok(cls, data: Dict[str, Any]) -> "AgentResult":
        """Create successful result."""
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str) -> "AgentResult":
        """Create failed result."""
        return cls(success=False, error=error)
