#!/usr/bin/env python3
"""
测试新数据源效果
比较 SEC EDGAR vs 原有的 Wikipedia + DuckDuckGo
"""

import sys
import time
import httpx
import yfinance
import os
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))

from sec_edgar import get_10k_relationships

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

def get_company_info(ticker: str):
    try:
        stock = yfinance.Ticker(ticker)
        info = stock.info
        return {
            "company_name": info.get('longName', ticker),
            "sector": info.get('sector', 'Unknown'),
            "industry": info.get('industry', 'Unknown'),
            "web_url": info.get('website', ''),
        }
    except Exception:
        return None

def get_wikipedia_summary(company_name: str):
    wiki_name = company_name
    ambiguous = {"apple": "Apple Inc.", "facebook": "Meta Platforms"}
    if company_name.lower() in ambiguous:
        wiki_name = ambiguous[company_name.lower()]
    
    try:
        headers = {"User-Agent": "StockKnowledgeGraph/1.0 (research tool)"}
        resp = httpx.get(f"{WIKIPEDIA_API}{wiki_name.replace(' ', '_')}", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "text": data.get('extract', '')[:1500],
                "url": f"https://en.wikipedia.org/wiki/{wiki_name.replace(' ', '_')}",
                "title": data.get('title', wiki_name)
            }
    except Exception as e:
        print(f"  Wiki error: {e}")
    return {"text": "", "url": "", "title": ""}

def simple_duckduckgo(query: str):
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            return [{"title": r.get('title', ''), "href": r.get('href', ''), "body": r.get('body', '')} for r in results]
    except Exception as e:
        print(f"  Search error: {e}")
        return []

TEST_TICKERS = ["NVDA", "AAPL", "TSLA", "AMD"]

def test_sec_edgar(ticker: str):
    print(f"\n{'='*60}")
    print(f"📊 SEC EDGAR: {ticker}")
    print('='*60)
    
    start = time.time()
    data = get_10k_relationships(ticker)
    elapsed = time.time() - start
    
    print(f"⏱️  耗时: {elapsed:.1f}s")
    print(f"📄 10-K日期: {data['filing_date']}")
    print(f"🔗 URL: {data['url']}")
    
    if data['suppliers']:
        print(f"\n✅ 提取到供应商 ({len(data['suppliers'])}):")
        for s in data['suppliers'][:5]:
            print(f"   - {s}")
    else:
        print("\n❌ 未提取到供应商")
    
    if data['raw_snippets']:
        print(f"\n📝 原始片段 ({len(data['raw_snippets'])}):")
        for s in data['raw_snippets'][:2]:
            print(f"   \"{s[:150]}...\"")
    
    return data

def test_original(ticker: str):
    print(f"\n{'='*60}")
    print(f"🔍 原有数据源: {ticker}")
    print('='*60)
    
    start = time.time()
    
    info = get_company_info(ticker)
    if not info:
        print("❌ 无法获取公司信息")
        return None
    
    print(f"公司: {info['company_name']}")
    print(f"行业: {info['sector']} / {info['industry']}")
    
    wiki = get_wikipedia_summary(info['company_name'])
    print(f"\n📖 Wikipedia:")
    print(f"   {wiki['text'][:200]}..." if wiki['text'] else "   ❌ 无数据")
    
    queries = [
        f"{info['company_name']} suppliers",
        f"{info['company_name']} customers",
    ]
    print(f"\n🔎 DuckDuckGo 搜索:")
    for q in queries:
        results = simple_duckduckgo(q)
        if results:
            print(f"   [{q}] {results[0].get('body', '')[:80]}...")
    
    elapsed = time.time() - start
    print(f"\n⏱️  耗时: {elapsed:.1f}s")
    
    return {'info': info, 'wiki': wiki}

def main():
    print("\n" + "="*60)
    print("🧪 数据源对比测试")
    print("="*60)
    
    for ticker in TEST_TICKERS:
        print(f"\n\n{'#'*60}")
        print(f"# {ticker}")
        print('#'*60)
        
        test_sec_edgar(ticker)
        time.sleep(1)
        
        test_original(ticker)
        time.sleep(1)
    
    print("\n\n" + "="*60)
    print("✅ 测试完成")
    print("="*60)

if __name__ == "__main__":
    main()
