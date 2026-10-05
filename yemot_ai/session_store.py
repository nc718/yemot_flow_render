"""
מודול לניהול סשנים (Session Store) - מיפוי בין ApiCallId לבין Session ID של AI.
תומך במספר סוגי אחסון: זיכרון, JSON מקומי, ועוד.
"""

import json
import os
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict


class SessionStore(ABC):
    """
    ממשק בסיסי לאחסון וניהול סשנים.
    מיפוי בין מזהה שיחה (call_id) למזהה סשן AI (session_id).
    """

    @abstractmethod
    def get(self, call_id: str) -> Optional[str]:
        """
        מחזיר את session_id עבור call_id נתון.
        מחזיר None אם לא קיים סשן.
        """
        pass

    @abstractmethod
    def set(self, call_id: str, session_id: str) -> None:
        """
        שומר מיפוי בין call_id ל-session_id.
        """
        pass

    @abstractmethod
    def clear(self, call_id: str) -> None:
        """
        מוחק מיפוי עבור call_id נתון.
        """
        pass

    @abstractmethod
    def clear_all(self) -> None:
        """
        מוחק את כל המיפויים.
        """
        pass

    def exists(self, call_id: str) -> bool:
        """
        בדיקה האם קיים סשן עבור call_id נתון.
        """
        return self.get(call_id) is not None


class MemorySessionStore(SessionStore):
    """
    אחסון סשנים בזיכרון בלבד.
    מתאים לסביבות פיתוח או יישומים בתהליך יחיד.
    """

    def __init__(self):
        self._sessions: Dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, call_id: str) -> Optional[str]:
        """מחזיר session_id מהזיכרון."""
        with self._lock:
            return self._sessions.get(call_id)

    def set(self, call_id: str, session_id: str) -> None:
        """שומר session_id בזיכרון."""
        with self._lock:
            self._sessions[call_id] = session_id

    def clear(self, call_id: str) -> None:
        """מוחק session מהזיכרון."""
        with self._lock:
            self._sessions.pop(call_id, None)

    def clear_all(self) -> None:
        """מוחק את כל הסשנים מהזיכרון."""
        with self._lock:
            self._sessions.clear()

    def get_all_sessions(self) -> Dict[str, str]:
        """מחזיר עותק של כל הסשנים (לצרכי debugging)."""
        with self._lock:
            return self._sessions.copy()


class JSONSessionStore(SessionStore):
    """
    אחסון סשנים בקובץ JSON מקומי.
    מתאים ליישומים שצריכים השרדות בין הפעלות.
    """

    def __init__(self, file_path: str = "yemot_ai_sessions.json"):
        self.file_path = file_path
        self._lock = threading.Lock()

    def _load_data(self) -> Dict[str, str]:
        """טוען נתונים מקובץ JSON."""
        if not os.path.exists(self.file_path):
            return {}
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # אם הקובץ פגום או לא נגיש, מחזירים מילון ריק
            return {}

    def _save_data(self, data: Dict[str, str]) -> None:
        """שומר נתונים לקובץ JSON."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            raise RuntimeError(f"שגיאה בשמירת קובץ סשנים: {e}")

    def get(self, call_id: str) -> Optional[str]:
        """מחזיר session_id מקובץ JSON."""
        with self._lock:
            data = self._load_data()
            return data.get(call_id)

    def set(self, call_id: str, session_id: str) -> None:
        """שומר session_id לקובץ JSON."""
        with self._lock:
            data = self._load_data()
            data[call_id] = session_id
            self._save_data(data)

    def clear(self, call_id: str) -> None:
        """מוחק session מקובץ JSON."""
        with self._lock:
            data = self._load_data()
            if call_id in data:
                del data[call_id]
                self._save_data(data)

    def clear_all(self) -> None:
        """מוחק את כל הסשנים מקובץ JSON."""
        with self._lock:
            self._save_data({})

    def get_all_sessions(self) -> Dict[str, str]:
        """מחזיר עותק של כל הסשנים (לצרכי debugging)."""
        with self._lock:
            return self._load_data()


class RedisSessionStore(SessionStore):
    """
    אחסון סשנים ב-Redis.
    מתאים ליישומים מבוזרים עם מספר workers.
    
    דורש התקנה של: pip install redis
    """

    def __init__(self, redis_client=None, prefix: str = "yemot_ai:session:"):
        try:
            import redis
        except ImportError:
            raise ImportError("להשתמש ב-RedisSessionStore יש להתקין: pip install redis")
        
        if redis_client is None:
            redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        self.redis = redis_client
        self.prefix = prefix

    def _get_key(self, call_id: str) -> str:
        """מחזיר מפתח Redis עם prefix."""
        return f"{self.prefix}{call_id}"

    def get(self, call_id: str) -> Optional[str]:
        """מחזיר session_id מ-Redis."""
        try:
            return self.redis.get(self._get_key(call_id))
        except Exception:
            return None

    def set(self, call_id: str, session_id: str, ttl_seconds: int = 3600) -> None:
        """
        שומר session_id ב-Redis.
        
        Args:
            call_id: מזהה שיחה
            session_id: מזהה סשן AI
            ttl_seconds: זמן תוקף בשניות (ברירת מחדל: שעה)
        """
        try:
            self.redis.setex(self._get_key(call_id), ttl_seconds, session_id)
        except Exception as e:
            raise RuntimeError(f"שגיאה בשמירה ל-Redis: {e}")

    def clear(self, call_id: str) -> None:
        """מוחק session מ-Redis."""
        try:
            self.redis.delete(self._get_key(call_id))
        except Exception:
            pass  # אם המחיקה נכשלת, לא נזרוק שגיאה

    def clear_all(self) -> None:
        """מוחק את כל הסשנים עם ה-prefix."""
        try:
            keys = self.redis.keys(f"{self.prefix}*")
            if keys:
                self.redis.delete(*keys)
        except Exception:
            pass

    def set_ttl(self, call_id: str, ttl_seconds: int) -> bool:
        """
        עדכון זמן תוקף עבור סשן קיים.
        
        Returns:
            True אם העדכון הצליח, False אחרת
        """
        try:
            return bool(self.redis.expire(self._get_key(call_id), ttl_seconds))
        except Exception:
            return False