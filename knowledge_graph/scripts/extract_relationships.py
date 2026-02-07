import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from dotenv import load_dotenv
from pydantic import BaseModel
from openai import OpenAI
import yfinance
from ddgs import DDGS
import yaml
import httpx
from bs4 import BeautifulSoup

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
if not NVIDIA_API_KEY:
    raise ValueError("NVIDIA_API_KEY not found in environment variables")

BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"
DATA_DIR = BASE_DIR / "data"
JSON_DIR = DATA_DIR / "json"
MARKDOWN_DIR = DATA_DIR / "markdown"

for d in [DATA_DIR, JSON_DIR, MARKDOWN_DIR]:
    d.mkdir(parents=True, exist_ok=True)

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

TICKER_CACHE = {}

class StockRelationships(BaseModel):
    ticker: str
    company_name: str
    sector: str
    industry: str
    upstream: List[str]
    downstream: List[str]
    competitors: List[str]
    key_products: List[str]
    extracted_at: str
    sources: List[Dict]

class Config(BaseModel):
    mode: str = "BOTH"
    watchlist: List[str] = []
    active_limit: int = 10
    watchlist_limit: int = 20
    exclude: List[str] = []

def load_config() -> Config:
    if not CONFIG_FILE.exists():
        return Config()

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f) or {}
        return Config(
            mode=raw.get("MODE", "BOTH"),
            watchlist=raw.get("WATCHLIST", []),
            active_limit=raw.get("ACTIVE_LIMIT", 20),
            watchlist_limit=raw.get("WATCHLIST_LIMIT", 20),
            exclude=raw.get("EXCLUDE", []),
        )
    except Exception as e:
        print(f"Config load error: {e}")
        return Config()

def get_ticker_for_company(company_name: str) -> Optional[str]:
    if company_name in TICKER_CACHE:
        return TICKER_CACHE[company_name]

    common_names = {
        "apple": "AAPL", "apple inc": "AAPL", "microsoft": "MSFT", "microsoft corporation": "MSFT",
        "nvidia": "NVDA", "nvidia corporation": "NVDA", "google": "GOOGL", "alphabet": "GOOGL",
        "amazon": "AMZN", "amazon.com": "AMZN", "meta": "META", "meta platforms": "META",
        "tesla": "TSLA", "amd": "AMD", "advanced micro devices": "AMD",
        "intel": "INTC", "intel corporation": "INTC", "broadcom": "AVGO",
        "qualcomm": "QCOM", "micron": "MU", "netflix": "NFLX", "cisco": "CSCO",
        "oracle": "ORCL", "adobe": "ADBE", "salesforce": "CRM",
        "tsmc": "TSM", "taiwan semiconductor": "TSM",
        "samsung": "005930.KS", "samsung electronics": "005930.KS",
        "applied materials": "AMAT", "asml": "ASML", "lam research": "LRCX",
        "sony": "SONY", "dell": "DELL", "hp": "HPQ", "hewlett packard": "HPQ",
        "ibm": "IBM", "international business machines": "IBM",
        "texas instruments": "TXN", "analog devices": "ADI",
        "cisco systems": "CSCO", "juniper networks": "JNPR",
        "arista networks": "ANET", "ubiquiti": "UI",
        "skyworks": "SWKS", "qorvo": "QRVO", "marvell": "MRVL",
        "western digital": "WDC", "seagate": "STX",
        "cat": "CAT", "deere": "DE"
    }

    name_lower = company_name.lower().strip()
    for key, ticker in common_names.items():
        if key in name_lower or name_lower in key:
            TICKER_CACHE[company_name] = ticker
            return ticker

    return None

def company_to_ticker(company_name: str) -> str:
    ticker = get_ticker_for_company(company_name)
    return ticker if ticker else company_name

def convert_companies_to_tickers(companies: List[str]) -> List[str]:
    result = []
    for c in companies:
        ticker = company_to_ticker(c)
        if ticker and ticker != c:
            result.append(ticker)
        else:
            result.append(c)
    return result

def get_active_tickers(limit: int = 50) -> List[str]:
    url = 'https://www.tradingview.com/markets/stocks-usa/market-movers-active/'
    try:
        response = httpx.get(url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        tickers = [option['data-rowkey'] for option in soup.select('tr.listRow')]
        tickers = [ticker.split(':')[1] for ticker in tickers]
        return tickers[:limit]
    except Exception as e:
        print(f"Error getting active tickers: {e}")
        return ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "AMD", "AVGO", "GOOGL", "INTC",
                "QCOM", "MU", "NFLX", "CRM", "ORCL", "ADBE", "CSCO"]

def get_target_tickers(config: Config) -> List[str]:
    exclude_set = set(config.exclude)
    result = []

    if config.mode in ["ACTIVE", "BOTH"]:
        active = get_active_tickers(config.active_limit)
        result.extend([t for t in active if t not in exclude_set])

    if config.mode in ["WATCHLIST", "BOTH"]:
        watchlist = config.watchlist[:config.watchlist_limit]
        result.extend([t for t in watchlist if t not in exclude_set])

    return list(dict.fromkeys(result))

def get_company_info(ticker: str) -> Optional[dict]:
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

def get_wikipedia_summary(company_name: str) -> Dict:
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

def duckduckgo_search(query: str, max_results: int = 3) -> List[Dict]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [{"title": r.get('title', ''), "href": r.get('href', ''), "body": r.get('body', '')} for r in results]
    except Exception as e:
        print(f"  Search error: {e}")
        return []

def search_relationships(company_name: str) -> Dict:
    results = {"sources": []}

    queries = [
        f"{company_name} suppliers manufacturers",
        f"{company_name} major customers clients",
        f"{company_name} competitors alternatives",
        f"{company_name} products services offerings"
    ]

    for query in queries:
        search_results = duckduckgo_search(query)
        for r in search_results[:2]:
            results["sources"].append({
                "query": query,
                "snippet": r.get('body', '')[:150],
                "url": r.get('href', ''),
                "title": r.get('title', '')
            })
        time.sleep(0.3)

    return results

def extract_relationships(ticker: str, company_info: dict) -> StockRelationships:

    wiki = get_wikipedia_summary(company_info['company_name'])
    search_results = search_relationships(company_info['company_name'])

    sources = [{"source": "Wikipedia", "url": wiki["url"], "title": wiki["title"], "snippet": wiki["text"][:200]}]
    sources.extend([{"source": "DuckDuckGo", "url": s["url"], "query": s["query"], "snippet": s["snippet"]}
                   for s in search_results["sources"]])

    context = f"""
公司: {company_info['company_name']} ({ticker})
行业: {company_info['sector']} / {company_info['industry']}

Wikipedia:
{wiki['text'][:800] if wiki['text'] else '无数据'}

搜索结果:
{chr(10).join([f"- {s['query']}: {s['snippet'][:80]}..." for s in search_results['sources'][:4]])}
"""

    system_prompt = """You are a financial analyst. Extract industry chain relationships.

Return ONLY valid JSON:

{
    "ticker": "SYMBOL",
    "company_name": "Full Name",
    "sector": "Sector",
    "industry": "Industry",
    "upstream": ["Suppliers"],
    "downstream": ["Major customers"],
    "competitors": ["Direct competitors"],
    "key_products": ["Main products"],
    "extracted_at": "YYYY-MM-DD HH:MM:SS"
}

Rules:
- Extract from Wikipedia and search results
- Maximum 5 items per category
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        content = response.choices[0].message.content.strip()
        content = content.strip('`').replace('json', '').strip()
        data_dict = json.loads(content)
        data_dict['ticker'] = ticker
        data_dict['extracted_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data_dict['upstream'] = convert_companies_to_tickers(data_dict.get('upstream', []))
        data_dict['downstream'] = convert_companies_to_tickers(data_dict.get('downstream', []))
        data_dict['competitors'] = convert_companies_to_tickers(data_dict.get('competitors', []))
        data_dict['key_products'] = data_dict.get('key_products', [])
        data_dict['sources'] = sources[:5]

        data = StockRelationships(**data_dict)
        return data
    except json.JSONDecodeError as e:
        print(f"  JSON error: {e}")
        return StockRelationships(
            ticker=ticker,
            company_name=company_info['company_name'],
            sector=company_info['sector'],
            industry=company_info['industry'],
            upstream=[],
            downstream=[],
            competitors=[],
            key_products=[],
            extracted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            sources=sources[:3]
        )
    except Exception as e:
        print(f"  AI error: {e}")
        return StockRelationships(
            ticker=ticker,
            company_name=company_info['company_name'],
            sector=company_info['sector'],
            industry=company_info['industry'],
            upstream=[],
            downstream=[],
            competitors=[],
            key_products=[],
            extracted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            sources=sources[:3]
        )

def save_json(data: StockRelationships, ticker: str):
    filepath = JSON_DIR / f"{ticker}.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data.model_dump(), f, indent=2, ensure_ascii=False)

def save_markdown(data: StockRelationships, ticker: str):
    filepath = MARKDOWN_DIR / f"{ticker}.md"

    sources_md = ""
    for s in data.sources[:5]:
        url = s.get("url", "")
        title = s.get('title', s.get('query', 'Source'))
        if url:
            sources_md += f"- [{title}]({url})\n"
        else:
            sources_md += f"- {title}\n"

    md = f"""---
ticker: {ticker}
company: {data.company_name}
sector: {data.sector}
industry: {data.industry}
extracted_at: {data.extracted_at}
last_updated: {datetime.now().strftime('%Y-%m-%d')}
---

# {ticker} - {data.company_name}

## 基本信息

- **所属行业**: {data.sector} / {data.industry}
- **提取时间**: {data.extracted_at}

## 产业链关系

### 上游供应商
{format_list(data.upstream)}

### 下游客户
{format_list(data.downstream)}

### 竞争对手
{format_list(data.competitors)}

### 核心产品
{format_list(data.key_products)}

## 数据来源

{sources_md}
## 元数据

- **更新日期**: {datetime.now().strftime('%Y-%m-%d')}
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md)

def format_list(items: List[str]) -> str:
    return '\n'.join(f"- [[{item.strip()}]]" for item in items) if items else "_暂无数据_"

def update_overview(all_data: List[StockRelationships], config: Config):
    overview = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": config.mode,
        "total_stocks": len(all_data),
        "stocks": {d.ticker: {
            "company_name": d.company_name,
            "sector": d.sector,
            "industry": d.industry,
        } for d in all_data}
    }
    with open(DATA_DIR / "overview.json", 'w', encoding='utf-8') as f:
        json.dump(overview, f, indent=2, ensure_ascii=False)

def generate_index(all_data: List[StockRelationships], config: Config):
    mode_desc = {"ACTIVE": "活跃股票", "WATCHLIST": "关注列表", "BOTH": "活跃股票 + 关注列表"}

    content = f"""---
title: 股票知识图谱索引
last_updated: {datetime.now().strftime('%Y-%m-%d')}
---

# 股票知识图谱索引

> 由 GitHub Actions 自动更新

## 概览

- **更新模式**: {mode_desc.get(config.mode, config.mode)}
- **跟踪股票数**: {len(all_data)}
- **最后更新**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 股票列表

| 股票代码 | 公司名称 | 行业 | 关系数 |
|---------|---------|------|--------|
"""
    for d in all_data:
        rel_count = len(d.upstream) + len(d.downstream) + len(d.competitors)
        content += f"| {d.ticker} | {d.company_name} | {d.industry} | {rel_count} |\n"
    content += "\n---\n\n**数据来源**:\n- DuckDuckGo Search API\n- Wikipedia API\n\n请查看 data/json/ 目录获取详细数据。\n"
    with open(MARKDOWN_DIR / "index.md", 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    print(f"\n{'='*50}")
    print("🚀 股票知识图谱生成器")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    config = load_config()
    tickers = get_target_tickers(config)

    mode_desc = {"ACTIVE": "活跃股票", "WATCHLIST": "关注列表", "BOTH": "活跃 + 关注"}
    print(f"📊 模式: {mode_desc.get(config.mode, config.mode)}")
    print(f"📈 目标股票 ({len(tickers)}只): {', '.join(tickers[:15])}\n")

    all_data = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker}", end=" ")

        info = get_company_info(ticker)
        if not info:
            print("❌ (无信息)")
            continue

        print(f"({info['company_name'][:15]})", end=" ")

        data = extract_relationships(ticker, info)
        save_json(data, ticker)
        save_markdown(data, ticker)
        all_data.append(data)

        rel_count = len(data.upstream) + len(data.downstream) + len(data.competitors)
        print(f"✅ ({rel_count} 关系)")

    if all_data:
        update_overview(all_data, config)
        generate_index(all_data, config)
        print(f"\n🎉 完成! {len(all_data)} 只股票")
    else:
        print("\n❌ 无股票处理成功")

if __name__ == "__main__":
    main()
