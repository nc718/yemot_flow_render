"""
המחלקה הראשית YemotAI - ממשק פשוט לשימוש עם סוכני AI בימות המשיח.
"""

import logging
from typing import Optional, Union, Dict, Any
from .session_store import SessionStore, MemorySessionStore, JSONSessionStore
from .providers import AIProvider, CodexCLIProvider, MockAIProvider
from .gemini_provider import GeminiProvider


logger = logging.getLogger(__name__)


class AI:
    """
    המחלקה הראשית של yemot-ai.
    
    מספקת ממשק פשוט ונוח לשילוב סוכני AI עם מערכות IVR של ימות המשיח.
    מנהלת אוטומטית את הסשנים ומסתירה את הפרטים הטכניים של התקשורת עם ה-AI.
    
    דוגמת שימוש:
    ```python
    from yemot_ai import AI
    
    # יצירת מנהל AI עם Codex CLI
    ai = AI(provider_type="codex")
    
    # בתוך Handler של yemot-flow
    def ai_handler(call):
        call_id = call.params.get("ApiCallId")
        user_text = call.params.get("RecordingText")
        
        answer = ai.reply(call_id, user_text)
        call.play_message([("text", answer)])
    ```
    """

    def __init__(
        self,
        provider_type: str = "codex",
        provider: Optional[AIProvider] = None,
        session_store: Optional[SessionStore] = None,
        **provider_kwargs
    ):
        """
        יוצר מנהל AI חדש.
        
        Args:
            provider_type: סוג ספק ה-AI ("codex", "openai", "mock")
            provider: ספק AI מותאם אישית (אופציונלי)
            session_store: מנהל אחסון סשנים (אופציונלי)
            **provider_kwargs: פרמטרים נוספים לספק ה-AI
        """
        # יצירת SessionStore אם לא סופק
        if session_store is None:
            session_store = MemorySessionStore()
        
        self.session_store = session_store
        
        # יצירת ספק AI
        if provider is not None:
            self.provider = provider
        else:
            self.provider = self._create_provider(provider_type, **provider_kwargs)
        
        logger.info(f"יצירת AI עם ספק {type(self.provider).__name__}")

    def _create_provider(self, provider_type: str, **kwargs) -> AIProvider:
        """
        יוצר ספק AI לפי הסוג הנבחר.
        
        Args:
            provider_type: סוג הספק
            **kwargs: פרמטרים לספק
            
        Returns:
            ספק AI מתאים
            
        Raises:
            ValueError: אם סוג הספק לא נתמך
        """
        provider_type = provider_type.lower()
        
        if provider_type == "codex":
            return CodexCLIProvider(
                session_store=self.session_store,
                cli_command=kwargs.get("cli_command", "codex")
            )
        
        elif provider_type == "openai":
            api_key = kwargs.get("api_key")
            if not api_key:
                raise ValueError("עבור OpenAI חובה לספק api_key")
            
            try:
                from .providers import OpenAIProvider
                return OpenAIProvider(
                    session_store=self.session_store,
                    api_key=api_key,
                    model=kwargs.get("model", "gpt-3.5-turbo")
                )
            except ImportError:
                raise ImportError("להשתמש ב-OpenAI יש להתקין: pip install openai")
        
        elif provider_type == "mock":
            return MockAIProvider(
                session_store=self.session_store,
                responses=kwargs.get("responses", None)
            )
        
        elif provider_type == "gemini":
            api_key = kwargs.get("api_key")
            if not api_key:
                raise ValueError("עבור Gemini חובה לספק api_key")
            
            try:
                return GeminiProvider(
                    session_store=self.session_store,
                    api_key=api_key,
                    model=kwargs.get("model", "gemini-pro")
                )
            except ImportError:
                raise ImportError("להשתמש ב-Gemini יש להתקין: pip install google-generativeai")
        
        else:
            supported_types = ["codex", "openai", "mock", "gemini"]
            raise ValueError(f"סוג ספק לא נתמך: {provider_type}. נתמכים: {supported_types}")

    def reply(self, call_id: str, user_text: str) -> str:
        """
        מקבל הודעה מהמשתמש ומחזיר תשובה מ-AI.
        
        מנהל אוטומטית את הסשן:
        - אם זוהי ההודעה הראשונה (אין סשן קיים) - יוצר סשן חדש
        - אחרת - ממשיך את הסשן הקיים
        
        Args:
            call_id: מזהה השיחה הטלפונית (ApiCallId)
            user_text: הטקסט שהמשתמש אמר
            
        Returns:
            תשובת ה-AI
            
        Raises:
            RuntimeError: אם יש בעיה בתקשורת עם ה-AI
            ValueError: אם הפרמטרים לא תקינים
        """
        # בדיקת תקינות פרמטרים
        if not call_id:
            raise ValueError("call_id לא יכול להיות ריק")
        
        if not user_text or not user_text.strip():
            raise ValueError("user_text לא יכול להיות ריק")
        
        user_text = user_text.strip()
        
        try:
            # בדיקה האם יש סשן קיים
            if self.provider.has_active_session(call_id):
                logger.info(f"ממשיך סשן קיים עבור שיחה {call_id}")
                answer = self.provider.continue_session(call_id, user_text)
            else:
                logger.info(f"יוצר סשן חדש עבור שיחה {call_id}")
                answer = self.provider.start_session(call_id, user_text)
            
            if not answer or not answer.strip():
                logger.warning("AI החזיר תשובה ריקה")
                answer = "מצטער, לא הצלחתי לעבד את הבקשה. אנא נסה שוב."
            
            return answer.strip()
            
        except Exception as e:
            logger.error(f"שגיאה בתקשורת עם AI עבור שיחה {call_id}: {e}")
            
            # במקרה של שגיאה, ננסה להחזיר הודעה ידידותית
            if "timeout" in str(e).lower() or "זמן" in str(e):
                return "מצטער, התשובה לוקחת זמן רב מהרגיל. אנא נסה שוב."
            elif "network" in str(e).lower() or "connection" in str(e).lower():
                return "יש בעיה זמנית בחיבור. אנא נסה שוב בעוד מעט."
            else:
                return "מצטער, אירעה שגיאה טכנית. אנא נסה שוב או פנה לתמיכה."

    def end_conversation(self, call_id: str) -> None:
        """
        מסיים שיחה ומנקה את הסשן.
        
        קוראים לפונקציה זו כאשר המשתמש מנתק או בוחר לסיים את השיחה.
        
        Args:
            call_id: מזהה השיחה הטלפונית
        """
        if not call_id:
            return
        
        try:
            logger.info(f"מסיים שיחה ומנקה סשן עבור {call_id}")
            self.provider.cleanup_session(call_id)
        except Exception as e:
            logger.warning(f"שגיאה בניקוי סשן עבור {call_id}: {e}")

    def has_active_conversation(self, call_id: str) -> bool:
        """
        בודק האם יש שיחה פעילה עבור המזהה הנתון.
        
        Args:
            call_id: מזהה השיחה
            
        Returns:
            True אם יש שיחה פעילה, False אחרת
        """
        if not call_id:
            return False
        
        return self.provider.has_active_session(call_id)

    def get_session_info(self, call_id: str) -> Dict[str, Any]:
        """
        מחזיר מידע על הסשן (לצרכי debugging ומעקב).
        
        Args:
            call_id: מזהה השיחה
            
        Returns:
            מילון עם מידע על הסשן
        """
        return {
            "call_id": call_id,
            "has_active_session": self.has_active_conversation(call_id),
            "provider_type": type(self.provider).__name__,
            "session_store_type": type(self.session_store).__name__,
        }

    def clear_all_sessions(self) -> None:
        """
        מנקה את כל הסשנים (שימוש זהיר - לצרכי תחזוקה בלבד).
        """
        logger.warning("מנקה את כל הסשנים")
        self.session_store.clear_all()

    @classmethod
    def create_codex_ai(cls, cli_command: str = "codex", session_store: Optional[SessionStore] = None):
        """
        יוצר מנהל AI עם Codex CLI (קיצור נוח).
        
        Args:
            cli_command: פקודת ה-CLI (ברירת מחדל: "codex")
            session_store: מנהל אחסון סשנים (אופציונלי)
            
        Returns:
            מנהל AI מוכן לשימוש
        """
        return cls(
            provider_type="codex",
            cli_command=cli_command,
            session_store=session_store
        )

    @classmethod
    def create_openai_ai(
        cls, 
        api_key: str, 
        model: str = "gpt-3.5-turbo",
        session_store: Optional[SessionStore] = None
    ):
        """
        יוצר מנהל AI עם OpenAI API (קיצור נוח).
        
        Args:
            api_key: מפתח API של OpenAI
            model: שם המודל להשתמש בו
            session_store: מנהל אחסון סשנים (אופציונלי)
            
        Returns:
            מנהל AI מוכן לשימוש
        """
        return cls(
            provider_type="openai",
            api_key=api_key,
            model=model,
            session_store=session_store
        )

    @classmethod
    def create_mock_ai(cls, responses: Optional[list] = None, session_store: Optional[SessionStore] = None):
        """
        יוצר מנהל AI מדומה לבדיקות (קיצור נוח).
        
        Args:
            responses: רשימת תשובות מוכנות מראש
            session_store: מנהל אחסון סשנים (אופציונלי)
            
        Returns:
            מנהל AI מוכן לשימוש
        """
        return cls(
            provider_type="mock",
            responses=responses,
            session_store=session_store
        )

    @classmethod
    def create_gemini_ai(
        cls,
        api_key: str,
        model: str = "gemini-pro",
        session_store: Optional[SessionStore] = None
    ):
        """
        יוצר מנהל AI עם Gemini API (קיצור נוח).
        
        Args:
            api_key: מפתח API של Google AI
            model: שם המודל להשתמש בו
            session_store: מנהל אחסון סשנים (אופציונלי)
            
        Returns:
            מנהל AI מוכן לשימוש
        """
        return cls(
            provider_type="gemini",
            api_key=api_key,
            model=model,
            session_store=session_store
        )


# פונקציות עזר לשימוש מהיר
def create_ai_manager(provider_type: str = "codex", **kwargs) -> AI:
    """
    פונקציית עזר ליצירת מנהל AI.
    
    Args:
        provider_type: סוג ספק ה-AI
        **kwargs: פרמטרים נוספים
        
    Returns:
        מנהל AI מוכן לשימוש
    """
    return AI(provider_type=provider_type, **kwargs)


def handle_yemot_hangup(ai_manager: AI, params: Dict[str, Any]) -> None:
    """
    פונקציית עזר לטיפול בניתוק שיחה של ימות המשיח.
    
    קוראים לפונקציה זו לאחר עיבוד בקשת HTTP של yemot-flow
    כדי לנקות סשנים בסיום שיחות.
    
    Args:
        ai_manager: מנהל ה-AI
        params: פרמטרים מהבקשה (ממילון request.values)
    """
    if params.get("hangup") == "yes":
        call_id = params.get("ApiCallId")
        if call_id:
            ai_manager.end_conversation(call_id)