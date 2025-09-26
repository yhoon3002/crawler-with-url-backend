"""
요청/응답 데이터 구조 정의(스키마)
FastAPI가 자동으로 검증하고 문서화 할 수 있도록 함
"""
from pydantic import BaseModel, HttpUrl

class ExtractReq(BaseModel):
    url: HttpUrl
    keep_images: bool | None = True

class ExtractResp(BaseModel):
    title: str
    html: str
    source_url: str

class ExtractStructuredReq(BaseModel):
    """
    추출 요청 데이터 구조
    프론트엔드에서 서버로 보내는 요청
    """
    url: HttpUrl                        # 추출할 웹페이지 URL (자동으로 URL 형식 검증함)
    keep_images: bool | None = True     # 이미지 포함 여부 (default: True)
    language: str | None = "ko"         # 언어 설정 (default: ko)

class ExtractStructuredResp(BaseModel):
    """
    추출 응답 데이터 구조
    서버에서 프론트엔드로 보내는 응답
    """
    title: str                          # 추출된 제목
    content: str                        # 추출된 본문
    lead_image_url: str | None          # 대표 이미지 URL(사용 안함)
    source_url: str                     # 원본 URL
    document_type: str | None = None    # 문서 타입(뉴스/블로그 등)
    keywords: list[str] | None = None   # 키워드 목록