"""
ספקי AI (AI Providers) - מימושים שונים לחיבור עם סוכני AI.
כולל תמיכה ב-Codex CLI, OpenAI API, ועוד.
"""

import json
import subprocess
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from .session_store import SessionStore


logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """
    ממשק בסיסי לספק AI.
    מגדיר את המתודות הנדרשות לכל מימוש ספציפי.
    """

    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    @abstractmethod
    def start_session(self, call_id: str, user_text: str) -> str:
        """
        מתחיל סשן חדש עם ה-AI.
        
        Args:
            call_id: מזהה השיחה הטלפונית
            user_text: טקסט ההודעה הראשונה מהמשתמש
            
        Returns:
            תשובת ה-AI
            
        Raises:
            RuntimeError: אם לא ניתן ליצור סשן חדש
        """
        pass

    @abstractmethod
    def continue_session(self, call_id: str, user_text: str) -> str:
        """
        ממשיך סשן קיים עם ה-AI.
        
        Args:
            call_id: מזהה השיחה הטלפונית
            user_text: טקסט ההודעה החדשה מהמשתמש
            
        Returns:
            תשובת ה-AI
            
        Raises:
            RuntimeError: אם לא ניתן להמשיך את הסשן
        """
        pass

    def cleanup_session(self, call_id: str) -> None:
        """
        מנקה משאבים של סשן (קריאה אופציונלית בסיום שיחה).
        מימוש ברירת מחדל מוחק רק מה-SessionStore.
        """
        self.session_store.clear(call_id)

    def has_active_session(self, call_id: str) -> bool:
        """
        בדיקה האם יש סשן פעיל עבור השיחה.
        """
        return self.session_store.exists(call_id)


class CodexCLIProvider(AIProvider):
    """
    ספק AI המשתמש ב-Codex CLI.
    
    דורש התקנה של Codex CLI ונגישות דרך PATH.
    """

    def __init__(self, session_store: SessionStore, cli_command: str = "codex"):
        """
        Args:
            session_store: מנהל אחסון הסשנים
            cli_command: שם פקודת ה-CLI (ברירת מחדל: "codex")
        """
        super().__init__(session_store)
        self.cli_command = cli_command

    def _run_codex_command(self, args: list, timeout: int = 60) -> subprocess.CompletedProcess:
        """
        מריץ פקודת Codex ומחזיר את התוצאה.
        
        Args:
            args: רשימת ארגומנטים לפקודה
            timeout: זמן המתנה מקסימלי בשניות
            
        Returns:
            תוצאת הפקודה
            
        Raises:
            RuntimeError: אם הפקודה נכשלת או לא נמצאה
        """
        try:
            full_command = [self.cli_command] + args
            logger.debug(f"מריץ פקודת Codex: {' '.join(full_command)}")
            
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            
            logger.debug(f"Codex החזיר: {result.stdout[:200]}...")
            return result
            
        except subprocess.CalledProcessError as e:
            error_msg = f"פקודת Codex נכשלה (קוד יציאה {e.returncode}): {e.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        except subprocess.TimeoutExpired:
            error_msg = f"פקודת Codex חרגה מזמן המתנה ({timeout} שניות)"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        except FileNotFoundError:
            error_msg = f"לא נמצא Codex CLI ({self.cli_command}). יש לוודא שהוא מותקן ונגיש ב-PATH"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def _parse_json_events(self, json_output: str) -> Tuple[Optional[str], Optional[str]]:
        """
        מנתח פלט JSON של Codex ומחלץ session_id ותשובת AI.
        
        Args:
            json_output: פלט ה-JSONL מ-Codex
            
        Returns:
            tuple של (session_id, answer)
        """
        session_id = None
        answer = None
        
        for line in json_output.strip().splitlines():
            try:
                event = json.loads(line)
                
                # חיפוש אחר session/thread ID
                if event.get("type") in {"thread.started", "session.started"}:
                    session_id = (
                        event.get("thread_id") or 
                        event.get("session_id") or
                        event.get("id")
                    )
                    logger.debug(f"נמצא session ID: {session_id}")
                
                # חיפוש אחר תשובת ה-AI
                if (
                    event.get("type") in {"item.completed", "message.completed", "response.done"}
                    and event.get("item", {}).get("type") in {"agent_message", "assistant_message", "message"}
                ):
                    answer = (
                        event.get("item", {}).get("text") or
                        event.get("item", {}).get("content") or
                        event.get("message", {}).get("text") or
                        event.get("message", {}).get("content") or
                        event.get("text") or
                        event.get("content")
                    )
                    logger.debug(f"נמצאה תשובה: {answer[:100]}...")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"לא ניתן לפרסר שורת JSON: {line[:100]} - {e}")
                continue
        
        return session_id, answer

    def start_session(self, call_id: str, user_text: str) -> str:
        """
        מתחיל סשן חדש עם Codex CLI.
        """
        logger.info(f"מתחיל סשן חדש עם Codex עבור שיחה {call_id}")
        
        # הרצת codex exec --json
        result = self._run_codex_command(["exec", "--json", user_text])
        
        # ניתוח התוצאה
        session_id, answer = self._parse_json_events(result.stdout)
        
        if not session_id:
            raise RuntimeError("לא הצלחתי לקבל session ID מ-Codex")
        
        if not answer:
            logger.warning("לא נמצאה תשובה מפורשת מ-Codex, משתמש בפלט גולמי")
            answer = result.stdout.strip() or "מצטער, לא הצלחתי לעבד את הבקשה."
        
        # שמירת ה-session ID
        self.session_store.set(call_id, session_id)
        logger.info(f"סשן {session_id} נשמר עבור שיחה {call_id}")
        
        return answer

    def continue_session(self, call_id: str, user_text: str) -> str:
        """
        ממשיך סשן קיים עם Codex CLI.
        """
        # קבלת ה-session ID
        session_id = self.session_store.get(call_id)
        if not session_id:
            logger.warning(f"לא נמצא סשן קיים עבור שיחה {call_id}, יוצר סשן חדש")
            return self.start_session(call_id, user_text)
        
        logger.info(f"ממשיך סשן {session_id} עבור שיחה {call_id}")
        
        # הרצת codex exec resume
        result = self._run_codex_command(["exec", "resume", session_id, user_text])
        
        # בפקודת resume, התשובה מגיעה בדרך כלל ישירות ב-stdout
        answer = result.stdout.strip()
        
        if not answer:
            logger.warning("לא נתקבלה תשובה מ-Codex resume")
            answer = "מצטער, לא הצלחתי לעבד את הבקשה."
        
        logger.debug(f"תשובת Codex: {answer[:100]}...")
        return answer

    def cleanup_session(self, call_id: str) -> None:
        """
        מנקה את הסשן עבור השיחה.
        בשלב זה רק מוחק מה-SessionStore, בעתיד ניתן להוסיף ניקוי מ-Codex.
        """
        session_id = self.session_store.get(call_id)
        if session_id:
            logger.info(f"מנקה סשן {session_id} עבור שיחה {call_id}")
            # TODO: בעתיד ניתן להוסיף קריאה ל-Codex לסגירת הסשן
            
        super().cleanup_session(call_id)


class OpenAIProvider(AIProvider):
    """
    ספק AI המשתמש ב-OpenAI API.
    
    דורש התקנה של: pip install openai
    """

    def __init__(self, session_store: SessionStore, api_key: str, model: str = "gpt-3.5-turbo"):
        """
        Args:
            session_store: מנהל אחסון הסשנים
            api_key: מפתח API של OpenAI
            model: שם המודל להשתמש בו
        """
        super().__init__(session_store)
        self.api_key = api_key
        self.model = model
        self.conversations: Dict[str, list] = {}  # אחסון היסטוריות שיחה
        
        try:
            import openai
            self.openai = openai
            self.openai.api_key = api_key
        except ImportError:
            raise ImportError("להשתמש ב-OpenAIProvider יש להתקין: pip install openai")

    def _get_conversation_history(self, call_id: str) -> list:
        """מחזיר את היסטוריית השיחה עבור call_id."""
        return self.conversations.get(call_id, [])

    def _save_conversation_history(self, call_id: str, history: list) -> None:
        """שומר היסטוריית שיחה."""
        self.conversations[call_id] = history

    def _call_openai_api(self, messages: list) -> str:
        """מבצע קריאה ל-OpenAI API."""
        try:
            response = self.openai.ChatCompletion.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"שגיאה בקריאה ל-OpenAI API: {e}")
            raise RuntimeError(f"שגיאה בתקשורת עם OpenAI: {e}")

    def start_session(self, call_id: str, user_text: str) -> str:
        """
        מתחיל סשן חדש עם OpenAI API.
        """
        logger.info(f"מתחיל סשן OpenAI עבור שיחה {call_id}")
        
        # יצירת היסטוריה התחלתית
        messages = [{"role": "user", "content": user_text}]
        
        # קריאה ל-API
        answer = self._call_openai_api(messages)
        
        # שמירת ההיסטוריה
        messages.append({"role": "assistant", "content": answer})
        self._save_conversation_history(call_id, messages)
        
        # שמירת אינדיקטור שהסשן קיים
        self.session_store.set(call_id, "openai_session")
        
        return answer

    def continue_session(self, call_id: str, user_text: str) -> str:
        """
        ממשיך סשן קיים עם OpenAI API.
        """
        if not self.session_store.exists(call_id):
            logger.warning(f"לא נמצא סשן קיים עבור שיחה {call_id}, יוצר סשן חדש")
            return self.start_session(call_id, user_text)
        
        logger.info(f"ממשיך סשן OpenAI עבור שיחה {call_id}")
        
        # קבלת היסטוריה קיימת
        messages = self._get_conversation_history(call_id)
        
        # הוספת הודעה חדשה
        messages.append({"role": "user", "content": user_text})
        
        # קריאה ל-API
        answer = self._call_openai_api(messages)
        
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


class MockAIProvider(AIProvider):
    """
    ספק AI מדומה לצרכי בדיקות ופיתוח.
    """

    def __init__(self, session_store: SessionStore, responses: list = None):
        """
        Args:
            session_store: מנהל אחסון הסשנים
            responses: רשימת תשובות מוכנות מראש (מחזורית)
        """
        super().__init__(session_store)
        self.responses = responses or [
            "שלום! אני כאן כדי לעזור לך.",
            "זה מעניין, ספר לי עוד על זה.",
            "אני מבין את השאלה שלך.",
            "יש לי עוד רעיונות בנושא הזה.",
            "האם זה עוזר לך?"
        ]
        self.response_index = {}  # אינדקס תשובה לכל call_id

    def start_session(self, call_id: str, user_text: str) -> str:
        """מתחיל סשן מדומה."""
        self.session_store.set(call_id, "mock_session")
        self.response_index[call_id] = 0
        return self._get_next_response(call_id)

    def continue_session(self, call_id: str, user_text: str) -> str:
        """ממשיך סשן מדומה."""
        if not self.session_store.exists(call_id):
            return self.start_session(call_id, user_text)
        return self._get_next_response(call_id)

    def _get_next_response(self, call_id: str) -> str:
        """מחזיר את התשובה הבאה ברשימה המחזורית."""
        idx = self.response_index.get(call_id, 0)
        response = self.responses[idx % len(self.responses)]
        self.response_index[call_id] = idx + 1
        return response

    def cleanup_session(self, call_id: str) -> None:
        """מנקה את הסשן המדומה."""
        self.response_index.pop(call_id, None)
        super().cleanup_session(call_id)