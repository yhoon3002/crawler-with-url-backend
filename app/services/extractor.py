"""
HTML에서 제목과 본문 추출하기
"""
import trafilatura  # 웹 페이지 본문 추출 전문 라이브러리
from newspaper import Article   # 뉴스 기사 추출 전문 라이브러리
from readability import Document    # 가독성 높은 본문 추출 라이브러리
from bs4 import BeautifulSoup   # HTML 파싱 라이브러리


def multi_strategy_extract(html: str, url: str) -> tuple[str, str]:
    """
    여러 라이브러리 사용해서 순서대로 시도후 제목과 본문을 추출하는 함수

    시도 순서
    1. Trafilatura : 파이썬에서 웹 페이지의 본문 내용을 효과적으로 추출할 수 있는 라이브러리 / 웹 스크랩핑과 데이터 마이닝에 특화됨
    2. Newwspaper3k : 뉴스 특화됨
    3. Readability : 범용적으로 사용함
    4. BeautifulSoup : 직접 HTNL 태그 찾기

    Args:
        html: HTML 문자열
        url: 원본 URL

    Returns:
        tuple[제목, 본문]: (str, str)
    """

    # 1순위인 Trafilatura 사용함
    title, content = extract_with_trafilatura(html, url)
    if content and len(content) > 100:
        return title, content

    # 2순위인 Newspaper3k 사용함
    title, content = extract_with_newspaper(url)
    if content and len(content) > 100:
        return title, content

    # 3순위인 Readability 사용함
    title, content = extract_with_readability(html)
    if content and len(content) > 100:
        return title, content

    # 4순위인 BeautifulSoup를 사용해서 직접 추출함
    title, content = extract_with_beautifulsoup(html)
    if content and len(content) > 100:
        return title, content

    # 위의 모든 방법 실패 시 원본 텍스트 반환함
    print("모든 추출 실패")
    soup = BeautifulSoup(html, "lxml")
    return "제목 추출 실패", soup.get_text("\n", strip=True)


def extract_with_trafilatura(html: str, url: str) -> tuple[str, str]:
    """
    Trafilatura 라이브러리로 추출

    광고, 메뉴, 푸터 등을 자동으로 제거하고 본문만 추출함
    """
    try:
        # 본문 추출
        extracted = trafilatura.extract(
            html,
            include_comments=False, # 댓글 제외
            include_tables=True,    # 표 포함
            no_fallback=False,      # False: 실패 시 다른 방법도 시도함
        )

        # 메타데이터에서 제목 추출함
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata else ""

        # 본문이 100자 이상이면 성공 판정
        if extracted and len(extracted) > 100:
            print(f"Trafilatura: {len(extracted)}자")
            return title, extracted
    except Exception as e:
        print(f"Trafilatura 실패: {e}")

    return "", ""


def extract_with_newspaper(url: str) -> tuple[str, str]:
    """
    Newspaper3k로 추출

    Args:
        url: 원본 URL

    Returns:
        tuple[제목, 본문]: (str, str)
    """
    try:
        # Article 객체 생성함
        article = Article(url, language='ko')   # 한국어 설정
        article.download()  # HTML 다운로드함
        article.parse()     # HTML 파싱함

        # 본문이 100자 이상이면 성공 판정
        if article.text and len(article.text) > 100:
            print(f"Newspaper3k: {len(article.text)}자")
            return article.title or "", article.text
    except:
        pass

    return "", ""


def extract_with_readability(html: str) -> tuple[str, str]:
    """
    Readability로 추출함

    읽기 모드처럼 가독성 높은 부분만 추출함

    Args:
        html: HTML 문자열

    Returns:
        tuple[제목, 본문]: (str, str)
    """
    try:
        # Document 객체로 본문 추출함
        doc = Document(html)
        title = doc.short_title()       # 짧은 제목
        content_html = doc.summary()    # 본문 HTML

        # HTML을 텍스트로 변환함
        soup = BeautifulSoup(content_html, "lxml")
        text = soup.get_text("\n", strip=True)  # 줄바꿈으로 구분, 공백 제거

        # 본문이 100자 이상이면 성공 판정
        if text and len(text) > 100:
            print(f"Readability: {len(text)}자")
            return title, text
    except:
        pass

    return "", ""


def extract_with_beautifulsoup(html: str) -> tuple[str, str]:
    """
    BeautifulSoup로 직접 파싱함

    최후의 수단

    Args:
        html: HTML 문자열

    Returns:
        tuple[제목, 본문]: (str, str)
    """
    try:
        soup = BeautifulSoup(html, "lxml")

        # 제목 찾기
        # <h1> 태그 / <title> 태그에서 찾음
        title = ""
        for sel in ["h1", "title"]:
            elem = soup.find(sel)
            if elem:
                title = elem.get_text(strip=True)
                break

        # 본문 찾기
        # 일반적으로 본문이 들어있는 태그들을 순서대로 시도함
        content = ""
        for sel in ["article", "main", "[role='main']", ".post-content", ".entry-content"]:
            elem = soup.select_one(sel)
            if elem:
                content = elem.get_text("\n", strip=True)
                if len(content) > 200:
                    print(f"BeautifulSoup ({sel}): {len(content)}자")
                    break

        return title, content
    except:
        pass

    return "", ""