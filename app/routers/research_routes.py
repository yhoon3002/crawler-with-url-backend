"""
메인 API 엔드포인트
웹페이지 추출 요청을 처리하고 결과를 반환함
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json
from app.schemas.extract import ExtractStructuredReq, ExtractStructuredResp
from app.services.fetcher import fetch_html
from app.services.extractor import multi_strategy_extract
from app.settings import settings

_openai_client = None
if settings.OPENAI_API_KEY:
    from openai import OpenAI

    _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

router = APIRouter()


@router.post("/extract_structured_stream")
async def extract_structured_stream(req: ExtractStructuredReq):
    """
    실시간 진행 상황을 전송하는 추출 API (Server-Sent Events 방식)

    클라이언트는 이벤트 스트림을 받아서 진행률을 표시할 수 있음

    Args:
         req: 추출 요청(URL 포함)

    Returns:
        StreamingResponse: 실시간 이벤트 스트림
    """
    async def generate():
        """
        이벤트 생성 함수
        """
        try:
            # 1. 크롤링 시작
            yield f"data: {json.dumps({'status': 'crawling', 'progress': 25, 'message': '크롤링 중...'}, ensure_ascii=False)}\n\n"

            # HTML 가져오기
            html = await fetch_html(str(req.url), timeout_s=10.0)

            # 2. 추출 시작
            yield f"data: {json.dumps({'status': 'parsing', 'progress': 50, 'message': '추출 중...'}, ensure_ascii=False)}\n\n"

            # 제목과 본문 추출 (백그라운드 스레드에서 실행함)
            title, content = await asyncio.get_event_loop().run_in_executor(
                None,               # 기본 executor
                multi_strategy_extract,     # 실행할 함수
                html,               # 함수의 첫 번째 인자
                str(req.url)            # 함수의 두 번째 인자
            )

            # OpenAI 정제
            if _openai_client and len(content) > 200:
                yield f"data: {json.dumps({'status': 'ai_processing', 'progress': 75, 'message': 'AI 정제 중...'}, ensure_ascii=False)}\n\n"

                refined = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ai_refine(content)
                )
                if refined:
                    content = refined

            # 3. 완료
            yield f"data: {json.dumps({'status': 'done', 'progress': 100, 'message': '완료!', 'data': {'title': title, 'content': content, 'source_url': str(req.url)}}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    # Server-Sent Events 형식으로 응답함
    return StreamingResponse(generate(), media_type="text/event-stream")


def ai_refine(content: str) -> str:
    """
    openAI로 노이즈만 제거
    """
    if not _openai_client or len(content) < 200:
        return content

    try:
        resp = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"다음 텍스트에서 광고, 댓글, 관련기사만 제거하세요. 본문은 그대로 유지:\n\n{content[:6000]}"
            }],
            temperature=0,
            max_tokens=8000,
            timeout=20
        )

        return resp.choices[0].message.content.strip()
    except:
        return content


@router.post("/extract_structured", response_model=ExtractStructuredResp)
async def extract_structured(req: ExtractStructuredReq):
    """
    일반 추출 API (진행 상황 없음)

    한 번에 결과를 받환하는 방식

    Args:
         req: 추출 요청

     Returns:
         ExtractStructuredResp: 추출 결과
    """
    # HTML 가져오기
    html = await fetch_html(str(req.url))
    # 제목과 본문 추출
    title, content = multi_strategy_extract(html, str(req.url))

    if _openai_client:
        content = await asyncio.get_event_loop().run_in_executor(
            None, lambda: ai_refine(content)
        )

    # 결과 반환
    return ExtractStructuredResp(
        title=title,
        content=content,
        lead_image_url=None,
        source_url=str(req.url)
    )