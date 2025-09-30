"""
메인 API 엔드포인트 (Archive.org fallback 지원)
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
    실시간으로 진행 상황을 전송하면서 크롤링하는 API

    이 API는 Server-Sent-Events (SSE) 방식 사용함
    SSE: 서버가 클라이언트에게 계속해서 메시지 보내는 방식

    Args:
        req: 사용자가 보낸 요청 데이터

    Returns:
        StreamingResponse: 실시간으로 진행 상황을 전송
    """
    async def generate():
        """
        진행 상황을 하나씩 생성하는 제너레이터 함수

        yield: 값을 하나씩 반환하는 키워드
        """
        try:
            # 1. 크롤링 시작 알림
            yield f"data: {json.dumps({'status': 'crawling', 'progress': 25, 'message': '크롤링 중...'}, ensure_ascii=False)}\n\n"

            # 2. HTML 가져옴
            html, from_archive = await fetch_html(str(req.url), timeout_s=15.0)

            # 아카이브에서 가져왔으면 사용자한테 알림
            if from_archive:
                yield f"data: {json.dumps({'status': 'archive_notice', 'progress': 40, 'message': '원본 사이트 차단됨. Archive.org 버전을 사용합니다.'}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'status': 'parsing', 'progress': 50, 'message': '추출 중...'}, ensure_ascii=False)}\n\n"

            # 3. 제목과 본문 추출
            title, content = await asyncio.get_event_loop().run_in_executor(
                None,
                multi_strategy_extract,
                html,
                str(req.url)
            )

            # 추출 실패 시 에러 처리
            if not content or len(content) < 100:
                raise Exception("콘텐츠 추출 실패. HTML 구조를 파싱할 수 없습니다.")

            # OpenAI 정제
            if _openai_client and len(content) > 200:
                yield f"data: {json.dumps({'status': 'ai_processing', 'progress': 75, 'message': 'AI 정제 중...'}, ensure_ascii=False)}\n\n"

                refined = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ai_refine(content)
                )
                if refined:
                    content = refined

            # 완료 (아카이브 사용 여부 포함)
            result_data = {
                'title': title,
                'content': content,
                'source_url': str(req.url),
                'from_archive': from_archive
            }

            yield f"data: {json.dumps({'status': 'done', 'progress': 100, 'message': '완료!', 'data': result_data}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_msg = str(e)
            # 사용자 친화적 에러 메시지
            if "archive" in error_msg.lower():
                error_msg = "원본 사이트와 Archive.org 모두 접근할 수 없습니다."
            yield f"data: {json.dumps({'status': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def ai_refine(content: str) -> str:
    """OpenAI로 노이즈만 제거"""
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
    Archive.org fallback 지원
    """
    try:
        # HTML 가져오기
        html, from_archive = await fetch_html(str(req.url), timeout_s=15.0)

        # 제목과 본문 추출
        title, content = await asyncio.get_event_loop().run_in_executor(
            None,
            multi_strategy_extract,
            html,
            str(req.url)
        )

        # 추출 실패 처리
        if not content or len(content) < 100:
            raise HTTPException(
                status_code=422,
                detail="콘텐츠를 추출할 수 없습니다. 페이지 구조를 파싱할 수 없습니다."
            )

        # OpenAI 정제
        if _openai_client and len(content) > 200:
            content = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ai_refine(content)
            )

        # 결과 반환
        resp = ExtractStructuredResp(
            title=title,
            content=content,
            lead_image_url=None,
            source_url=str(req.url)
        )

        # 아카이브 사용 시 document_type에 표시
        if from_archive:
            resp.document_type = "archived_version"

        return resp

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"페이지를 가져올 수 없습니다: {str(e)}"
        )