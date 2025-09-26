"""
웹페이지 HTML 가져오기
정적 사이트는 빠르게 / 동적(Javascript) 사이트는 PlayWright으로 렌더링
"""
import httpx
from playwright.async_api import async_playwright
import asyncio


async def fetch_html(url: str, timeout_s: float = 10.0) -> str:
    """
    웹페이지의 HTML을 가져오는 메인 함수

    동작 방식
    1. 먼저 빠른 정적 요청 시도(httpx)
    2. 실패하거나 콘텐츠가 부족하면 Playwright로 Javascript 렌더링

    Args:
        url: 가져올 웹페이지 주소
        timeout_s: 타임아웃 시간(초 단위)

    Returns:
        str: HTML 문자열
    """

    # 1. 빠른 정적 크롤링 시도
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            # HTTP 요청 (브라우저인 척 User-Agent 설정함)
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            html = resp.text

            # HTML이 충분히 길면 성공으로 간주함(10,000자 이상으로 설정해놓음)
            if len(html) > 10000:
                print(f"✅ 정적 크롤링: {len(html)}자")
                return html
    except:
        pass

    # 2. Playwright로 Javascript 렌더링
    print(f"🎭 Playwright 실행: {url}")
    return await fetch_with_playwright(url, timeout_s)


async def fetch_with_playwright(url: str, timeout_s: float) -> str:
    """
    Playwright로 Javascript 실행해서 HTML 가져오기
    React, Vue 등 JS 프레임워크로 만든 사이트에 필요함

    Args:
        url: 가져올 웹페이지 주소
        timeout_s: 타임아웃 시간

    Returns:
         str: 렌더링된 HTML
    """
    async with async_playwright() as p:
        # 브라우저 실행 (화면 없는 headless 모드임)
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # 페이지 로드 (네트워크 요청이 끝날 때까지 대기함)
            await page.goto(url, wait_until="networkidle", timeout=int(timeout_s * 1000))
            # Javascript 실행이 끝날 때까지 추가 대기함
            await asyncio.sleep(1)

            # 렌더링된 HTML 가져옴
            html = await page.content()
            print(f"✅ Playwright: {len(html)}자")
            return html
        finally:
            # 브라우저 종료 (메모리 절약하기 위함)
            await browser.close()