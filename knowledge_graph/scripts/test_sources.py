#!/usr/bin/env python3
"""改进版测试数据源 - 使用正确的字段名"""

import json
import time

def test_wikipedia(company_name: str):
    """测试 Wikipedia REST API"""
    print(f"\n{'='*50}")
    print(f"Wikipedia: {company_name}")
    print(f"{'='*50}")

    import httpx

    # 使用带 User-Agent 的请求
    headers = {"User-Agent": "StockKnowledgeGraph/1.0 (research tool)"}
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{company_name.replace(' ', '_')}"

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Title: {data.get('title')}")
            print(f"URL: https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}")
            print(f"Extract: {data.get('extract', '')[:200]}...")
            return data
    except Exception as e:
        print(f"Error: {e}")
    return None

def test_ddgs(company: str):
    """测试 ddgs - 使用正确的字段"""
    print(f"\n{'='*50}")
    print(f"DuckDuckGo: {company}")
    print(f"{'='*50}")

    from ddgs import DDGS

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{company} major suppliers customers competitors", max_results=5))

            print(f"Results: {len(results)}")
            for i, r in enumerate(results, 1):
                print(f"\n[{i}]")
                print(f"  Title: {r.get('title', 'N/A')}")
                print(f"  href: {r.get('href', 'N/A')}")  # 正确字段是 href
                print(f"  body: {r.get('body', '')[:100]}...")
            return results
    except Exception as e:
        print(f"Error: {e}")
        return []

def test_yfinance_info(ticker: str):
    """测试 yfinance info"""
    print(f"\n{'='*50}")
    print(f"yfinance: {ticker}")
    print(f"{'='*50}")

    try:
        import yfinance
        stock = yfinance.Ticker(ticker)
        info = stock.info
        print(f"Company: {info.get('longName', ticker)}")
        print(f"Sector: {info.get('sector', 'N/A')}")
        print(f"Industry: {info.get('industry', 'N/A')}")
        return info
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_full_wiki_page(company: str):
    """获取完整 Wikipedia 页面内容"""
    print(f"\n{'='*50}")
    print(f"Wikipedia Full: {company}")
    print(f"{'='*50}")

    import httpx
    from bs4 import BeautifulSoup

    url = f"https://en.wikipedia.org/wiki/{company.replace(' ', '_')}"
    headers = {"User-Agent": "StockKnowledgeGraph/1.0"}

    try:
        resp = httpx.get(url, headers=headers, timeout=15)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 找主要段落
            paragraphs = soup.select('p')
            for p in paragraphs[:5]:
                text = p.get_text()[:200]
                if text.strip():
                    print(f"\n{text}...")
                    break
    except Exception as e:
        print(f"Error: {e}")

def test_direct_answer(question: str):
    """测试获取直接答案"""
    print(f"\n{'='*50}")
    print(f"Direct Answer: {question}")
    print(f"{'='*50}")

    from ddgs import DDGS

    try:
        with DDGS() as ddgs:
            # 使用 who/what/where/when/how 等问题格式
            results = list(ddgs.text(question, max_results=3))
            for i, r in enumerate(results, 1):
                print(f"[{i}] {r.get('title')}: {r.get('body', '')[:150]}...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    companies = ["NVIDIA", "Apple", "Tesla"]

    for company in companies:
        ticker_map = {"NVIDIA": "NVDA", "Apple": "AAPL", "Tesla": "TSLA"}
        ticker = ticker_map.get(company, company[:4].upper())

        print(f"\n\n{'#'*60}")
        print(f"# 公司: {company} ({ticker})")
        print(f"{'#'*60}")

        test_yfinance_info(ticker)
        test_wikipedia(company)
        test_ddgs(company)
        test_direct_answer(f"Who are {company}'s main suppliers")
        test_direct_answer(f"Who are {company}'s main competitors")

        time.sleep(0.3)

    print("\n" + "="*50)
    print("测试完成!")
    print("="*50)
