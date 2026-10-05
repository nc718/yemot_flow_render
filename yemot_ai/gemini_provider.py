"""
ספק AI המשתמש ב-Google Gemini API.

דורש התקנה של: pip install google-generativeai
"""

import logging
from typing import Dict, list
from .providers import AIProvider
from .session_store import SessionStore


logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """
    ספק AI המשתמש ב-Google Gemini API.
    
    דורש התקנה של: pip install google-generativeai
    """

    def __init__(self, session_store: SessionStore, api_key: str, model: str = "gemini-pro"):
        """
        Args:
            session_store: מנהל אחסון הסשנים
            api_key: מפתח API של Google AI
            model: שם המודל להשתמש בו
        """
        super().__init__(session_store)
        self.api_key = api_key
        self.model = model
        self.conversations: Dict[str, list] = {}  # אחסון היסטוריות שיחה
        
        try:
            import google.generativeai as genai
            self.genai = genai
            self.genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel(model)
        except ImportError:
            raise ImportError("להשתמש ב-GeminiProvider יש להתקין: pip install google-generativeai")

    def _get_conversation_history(self, call_id: str) -> list:
        """מחזיר את היסטוריית השיחה עבור call_id."""
        return self.conversations.get(call_id, [])

    def _save_conversation_history(self, call_id: str, history: list) -> None:
        """שומר היסטוריית שיחה."""
        self.conversations[call_id] = history

    def _call_gemini_api(self, messages: list) -> str:
        """מבצע קריאה ל-Gemini API."""
        try:
            # המרת היסטוריה לפורמט של Gemini
            chat = self.gemini_model.start_chat(history=[])
            
            # הוספת ההיסטוריה
            for msg in messages:
                if msg["role"] == "user":
                    chat.history.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    chat.history.append({"role": "model", "parts": [msg["content"]]})
            
            # קריאה ל-API עם ההודעה האחרונה
            last_message = messages[-1]["content"] if messages else ""
            response = chat.send_message(last_message)
            
            return response.text
        except Exception as e:
            logger.error(f"שגיאה בקריאה ל-Gemini API: {e}")
            raise RuntimeError(f"שגיאה בתקשורת עם Gemini: {e}")

    def start_session(self, call_id: str, user_text: str) -> str:
        """
        מתחיל סשן חדש עם Gemini API.
        """
        logger.info(f"מתחיל סשן Gemini עבור שיחה {call_id}")
        
        # יצירת היסטוריה התחלתית
        messages = [{"role": "user", "content": user_text}]
        
        # קריאה ל-API
        answer = self._call_gemini_api(messages)
        
        # שמירת ההיסטוריה
        messages.append({"role": "assistant", "content": answer})
        self._save_conversation_history(call_id, messages)
        
        # שמירת אינדיקטור שהסשן קיים
        self.session_store.set(call_id, "gemini_session")
        
        return answer

    def continue_session(self, call_id: str, user_text: str) -> str:
        """
        ממשיך סשן קיים עם Gemini API.
        """
        if not self.session_store.exists(call_id):
            logger.warning(f"לא נמצא סשן קיים עבור שיחה {call_id}, יוצר סשן חדש")
            return self.start_session(call_id, user_text)
        
        logger.info(f"ממשיך סשן Gemini עבור שיחה {call_id}")
        
        # קבלת היסטוריה קיימת
        messages = self._get_conversation_history(call_id)
        
        # הוספת הודעה חדשה
        messages.append({"role": "user", "content": user_text})
        
        # קריאה ל-API
        answer = self._call_gemini_api(messages)
        
        # עדכון ההיסטוריה
        messages.append({"role": "assistant", "content": answer})
        self._save_conversation_history(call_id, messages)
        
        return answer

    def cleanup_session(self, call_id: str) -> None:
        """
        מנקה את הסשן עבור השיחה.
        """
        if call_id in self.conversations:
            logger.info(f"מנקה היסטוריית שיחה עבור {call_id}")
            del self.conversations[call_id]
        
        super().cleanup_session(call_id)
