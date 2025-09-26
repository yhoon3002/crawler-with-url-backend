"""
환경 변수 설정 관리
.env 파일에서 설정값을 읽어서 애플리케이션에서 사용
"""
import os
from dotenv import load_dotenv

load_dotenv()

def _split_csv(val: str | None) -> list[str]:
    """
    쉼표로 구분된 문자열을 리스트로 반환
    """
    if not val:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]

class Settings:
    """
    애플리케이션 설정값을 관리하는 클래스
    """
    DEBUG: bool = (os.getenv("DEBUG", "false").lower() == "true")
    ALLOW_ORIGINS: list[str] = _split_csv(os.getenv("ALLOW_ORIGINS"))
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # 성능 최적화
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", "8000"))

settings = Settings()