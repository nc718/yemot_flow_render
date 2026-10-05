"""
yemot-ai: חבילת Python לחיבור סוכני AI למערכות ימות המשיח

חבילה זו מספקת שכבת אינטגרציה בין yemot-flow לבין סוכני AI,
ומאפשרת לנהל שיחות רציפות עם AI דרך מערכת IVR של ימות המשיח.
"""

__version__ = "0.1.0"
__author__ = "davidTheDeveloper"
__email__ = "dev@code-chai.com"

from .core import AI
from .session_store import SessionStore, MemorySessionStore, JSONSessionStore
from .providers import AIProvider, CodexCLIProvider, MockAIProvider
from .gemini_provider import GeminiProvider

__all__ = [
    "AI",
    "SessionStore", 
    "MemorySessionStore",
    "JSONSessionStore",
    "AIProvider",
    "CodexCLIProvider",
    "MockAIProvider",
    "GeminiProvider",
]
