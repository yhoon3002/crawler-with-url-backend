"""
웹페이지 HTML 가져오기 (Archive.org 포함)
"""
import httpx    # HTTP 요청 보내는 라이브러리 = 웹페이지 다운로드용
from playwright.async_api import async_playwright   # 실제 브라우저를 자동으로 조작하는 라이브러리
import asyncio  # 비동기 처리
import random   # 랜덤 값 생성(봇처럼 안보이게 하려고 사용)
from typing import Tuple


# 실제 브라우저처럼 보이는 User-Agent 목록
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def get_realistic_headers() -> dict:
    """
    진짜 브라우저가 보내는 것처럼 HTTP 헤더를 만드는 함수

    Returns:
        dict: HTTP 요청에 포함할 헤더 정보
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


async def fetch_html(url: str, timeout_s: float = 15.0, use_archive: bool = False) -> Tuple[str, bool]:
    """
    웹페이지의 HTML을 가져오는 메인 함수
    차단되면 자동으로 Archive.org에서 가져옴

    동작 순서:
    1. 일반적인 HTTP 요청으로 시도함
    2. 막히면 Playwright로 실제 브라우저 사용함
    3. 막히면 Archive.org에서 가져오기

    Args:
        url: 가져올 웹페이지 주소
        timeout_s: 타임아웃 시간(초)
        use_archive: True시 바로 아카이브 사용

    Returns:
        Tuple[str, bool]: (HTML 문자열, 아카이브 사용했는지 여부)
    """

    # use_archive가 True면 바로 아카이브에서 가져옴
    if use_archive:
        print(f"Archive.org에서 가져옴: {url}")
        html = await fetch_from_archive(url, timeout_s)
        return html, True

    # 일반 HTTP 요청으로 시도함
    try:
        # httpx.AsynClient: 비동기로 HTTP 요청을 보내는 클라이언트
        async with httpx.AsyncClient(
            timeout=timeout_s,  # timeout_s초 안에 응답 안오면 포기함
            follow_redirects=True,  # 리다이렉션 자동으로 따라감
            headers=get_realistic_headers()
        ) as client:
            resp = await client.get(url)    # GET 요청 보냄
            html = resp.text    # 응답을 텍스트(HTML)로 받음

            # 차단됐는지 확인
            if is_blocked(html, resp.status_code):
                print(f"정적 크롤링 차단됨 -> 브라우저로 재시도")
                html, blocked = await fetch_with_playwright(url, timeout_s)

                # 브라우저도 안되면 아카이브 시도
                if blocked:
                    print(f"🚫 브라우저도 차단됨 -> Archive.org 시도")
                    html = await fetch_from_archive(url, timeout_s)
                    return html, True   # 아카이브 사용

                return html, False  # 브라우저로 성공

            # HTML이 충분히 길면 성공
            if len(html) > 1000:
                print(f"정적 크롤링: {len(html)}자")
                return html, False

    except Exception as e:
        print(f"정적 크롤링 실패: {e}")

    # 2단계: Playwright로 브라우저 렌더링
    print(f"🎭 Playwright 실행: {url}")
    html, blocked = await fetch_with_playwright(url, timeout_s)

    # 브라우저도 차단되면 아카이브 시도
    if blocked:
        print(f"브라우저도 차단됨 -> Archive.org 시도")
        html = await fetch_from_archive(url, timeout_s)
        return html, True

    return html, False


def is_blocked(html: str, status_code: int) -> bool:
    """
    웹사이트가 우리를 차단햇는지 판단하는 함수

    차단 판단 기준:
    1. HTTP 상태 코드가 403(Forbidden, 금지됨)/429(Too Many Requests, 너무 많은 요청)/503(service temporarily unavailable, 서비스 불가)
    2. HTML이 너무 짧음 (500자 미만)    ->  추후 변경해야됨
    3. "Access Denied", "Cloudflare", "captcha" 같은 차단 관련 단어가 있음

    Args:
        html: 받은 HTML 문자열
        status_code: HTTP 상태 코드

    Returns:
        bool: 차단 -> True / 차단 X -> False
    """
    if status_code in [403, 429, 503]:
        return True

    # HTML 길이가 500자 미만이면 정상적이지 않다고 판단   ->  추후 수정 필요할듯 ?
    if len(html) < 500:
        return True

    # 차단 관련 키워드 목록들
    block_keywords = [
        "Access Denied",
        "403 Forbidden",
        "Attention Required",
        "Cloudflare",
        "Security Check",
        "Please verify you are a human",
        "captcha",
        "blocked",
    ]

    html_lower = html.lower()
    for keyword in block_keywords:
        if keyword.lower() in html_lower:
            return True

    return False


async def fetch_with_playwright(url: str, timeout_s: float) -> Tuple[str, bool]:
    """
    Playwright를 사용해 실제 브라우저로 웹페이지 열고 HTML을 가져오는 함수

    일반 HTTP 요청으로 안될 때 사용함
    실제 Chrome 브라우저를 자동으로 켜서 사람처럼 보이게 함

    Args:
        url: 가져올 웹페이지 주소
        timeout_s: 최대 기다릴 시간

    Returns:
        Tuple[str, bool]: [HTML 문자열, 차단되었는지 여부]
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,  # True면 백그라운드로 실행함
                args=[
                    '--disable-blink-features=AutomationControlled',    # 자동화라는 표시 숨기기
                    '--disable-dev-shm-usage',  # 메모리 최적화
                    '--no-sandbox', # 샌드박스 비활성화
                ]
            )

            # 브라우저 컨텍스트 생성
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},   # 화면 크기
                user_agent=random.choice(USER_AGENTS),  # 랜덤 User-Agent
                locale='ko-KR', # 한국어 설정
                timezone_id='Asia/Seoul',   # 서울 시간대
            )

            # 자동화 탐지 방지 스크립트 추가
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
            """)

            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))

                # 1~2초 정도 랜덤 시간으로 기다려서 사람처럼 안보이게
                await asyncio.sleep(random.uniform(1.0, 2.0))

                html = await page.content()

                # 차단됐는지 확인
                blocked = is_blocked(html, 200)

                if not blocked:
                    print(f"Playwright: {len(html)}자")

                return html, blocked

            finally:
                await context.close()
                await browser.close()

    except Exception as e:
        print(f"Playwright 실패: {e}")
        return "", True


async def fetch_from_archive(url: str, timeout_s: float = 20.0) -> str:
    """
    Archive.org에서 HTML을 가져오는 함수
    원본 사이트 막힐 때 사용

    Args:
        url: 원본 웹페이지 주소
        timeout_s: 최대 기다릴 시간

    Returns:
        str: 아카이브된 HTML

    Raises:
        Exception: 아카이브에 해당 URL이 없거나 접근 실패 시
    """
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            # 아카이브에 URL이 저장되어 있는지 확인함
            availability_url = f"https://archive.org/wayback/available?url={url}"
            resp = await client.get(availability_url)
            data = resp.json()

            # 아카이브가 있는지 확인
            if not data.get("archived_snapshots"):
                raise Exception("아카이브에 해당 URL이 없음!!!")

            # 가장 최근 저장된 버전 찾아옴
            closest = data["archived_snapshots"].get("closest")
            if not closest or not closest.get("available"):
                raise Exception("사용 가능한 아카이브가 없음!!!")

            # 아카이브 URL과 저장 시점
            archive_url = closest["url"]
            timestamp = closest.get("timestamp", "알 수 없음")

            print(f"Archive.org에서 찾음: {timestamp} 버전")

            # 아카이브된 페이지 가져옴
            # id_ 플래그 추가하면 아카이브의 UI 없이 원본 컨텐츠만 받을 수 있음
            if "web.archive.org/web/" in archive_url:
                # URL 재구성 및 id_ 플래그 추가
                parts = archive_url.split("/web/")
                if len(parts) == 2:
                    archive_url = f"{parts[0]}/web/{parts[1].split('/')[0]}id_/{'/'.join(parts[1].split('/')[1:])}"

            # 아카이브 페이지 다운로드
            resp = await client.get(archive_url, headers=get_realistic_headers())
            html = resp.text

            print(f"Archive.org: {len(html)}자 (아카이브 버전)")
            return html

    except Exception as e:
        print(f"Archive.org 실패: {e}")
        raise Exception(f"원본 사이트 및 아카이브 모두 접근 실패: {str(e)}")