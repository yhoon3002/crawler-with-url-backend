"""
HTML에서 제목과 본문 추출하기
여러 라이브러리를 순서대로 시도해서 가장 정확한 결과를 반환함
"""
import trafilatura
from newspaper import Article
from readability import Document
from bs4 import BeautifulSoup


def multi_strategy_extract(html: str, url: str) -> tuple[str, str]:
    """
    다층 전략으로 제목과 본문 추출함

    시도 순서
    1. Trafilatura      (파이썬에서 웹 페이지의 본문 내용을 효과적으로 추출할 수 있는 라이브러리 / 웹 스크랩핑과 데이터 마이닝에 특화됨)
    2. Newwspaper3k     (뉴스 특화됨)
    3. Readability      (범용적 사용)
    4. BeautifulSoup    (직접 파싱함)

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
    print("⚠️ 모든 추출 실패")
    soup = BeautifulSoup(html, "lxml")
    return "제목 추출 실패", soup.get_text("\n", strip=True)


def extract_with_trafilatura(html: str, url: str) -> tuple[str, str]:
    """
    Trafilatura 라이브러리로 추출
    """
    try:
        # 본문 추출
        extracted = trafilatura.extract(
            html,
            include_comments=False, # 댓글 제외
            include_tables=True,    # 표 포함
            no_fallback=False,      # 폴백 허용
        )

        # 메타데이터에서 제목 추출함
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata else ""

        if extracted and len(extracted) > 100:
            print(f"✅ Trafilatura: {len(extracted)}자")
            return title, extracted
    except Exception as e:
        print(f"Trafilatura 실패: {e}")

    return "", ""


def extract_with_newspaper(url: str) -> tuple[str, str]:
    """
    Newspaper3k로 추출
    :param url:
    :return:
    """
    try:
        # Article 객체 생성함
        article = Article(url, language='ko')
        article.download()  # HTML 다운로드함
        article.parse()     # 파싱함

        if article.text and len(article.text) > 100:
            print(f"✅ Newspaper3k: {len(article.text)}자")
            return article.title or "", article.text
    except:
        pass

    return "", ""


def extract_with_readability(html: str) -> tuple[str, str]:
    """
    Readability로 추출함
    """
    try:
        # Document 객체로 본문 추출함
        doc = Document(html)
        title = doc.short_title()       # 짧은 제목
        content_html = doc.summary()    # 본문 HTML

        # HTML을 텍스트로 변환함
        soup = BeautifulSoup(content_html, "lxml")
        text = soup.get_text("\n", strip=True)

        if text and len(text) > 100:
            print(f"✅ Readability: {len(text)}자")
            return title, text
    except:
        pass

    return "", ""


def extract_with_beautifulsoup(html: str) -> tuple[str, str]:
    """
    BeautifulSoup로 직접 파싱함
    """
    try:
        soup = BeautifulSoup(html, "lxml")

        # 제목 찾기(h1 또는 title tag)
        title = ""
        for sel in ["h1", "title"]:
            elem = soup.find(sel)
            if elem:
                title = elem.get_text(strip=True)
                break

        # 본문 찾기 (article, main 등 우선 사용)
        content = ""
        for sel in ["article", "main", "[role='main']", ".post-content", ".entry-content"]:
            elem = soup.select_one(sel)
            if elem:
                content = elem.get_text("\n", strip=True)
                if len(content) > 200:
                    print(f"✅ BeautifulSoup ({sel}): {len(content)}자")
                    break

        return title, content
    except:
        pass

    return "", ""