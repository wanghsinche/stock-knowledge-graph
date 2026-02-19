import os
from dotenv import load_dotenv
import httpx
import re
import json
from typing import Dict, List, Optional
from pathlib import Path
from openai import OpenAI
import time

load_dotenv()

SEC_HEADERS = {
    "User-Agent": "StockKnowledgeGraph/1.0 (personal use, research.tool@example.com)",
    "Accept": "text/html,application/xhtml+xml",
}

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
if not NVIDIA_API_KEY:
    raise ValueError("NVIDIA_API_KEY not found")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)

CIK_CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "cik_cache.json"

def load_cik_cache() -> Dict[str, str]:
    if CIK_CACHE_FILE.exists():
        with open(CIK_CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cik_cache(cache: Dict[str, str]):
    CIK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CIK_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def get_cik_from_ticker(ticker: str) -> Optional[str]:
    cache = load_cik_cache()
    ticker_upper = ticker.upper()
    if ticker_upper in cache:
        return cache[ticker_upper]
    
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        resp = httpx.get(url, headers=SEC_HEADERS, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for entry in data.values():
                if entry.get('ticker', '').upper() == ticker_upper:
                    cik = str(entry.get('cik_str', '')).zfill(10)
                    cache[ticker_upper] = cik
                    save_cik_cache(cache)
                    return cik
    except Exception as e:
        print(f"  CIK lookup error: {e}")
    return None

def get_latest_10k_info(cik: str) -> Optional[Dict]:
    try:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = httpx.get(url, headers=SEC_HEADERS, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            filings = data.get('filings', {}).get('recent', {})
            forms = filings.get('form', [])
            accession_numbers = filings.get('accessionNumber', [])
            primary_documents = filings.get('primaryDocument', [])
            filing_dates = filings.get('filingDate', [])
            
            for i, form in enumerate(forms):
                if form == '10-K':
                    accession = accession_numbers[i].replace('-', '')
                    primary = primary_documents[i]
                    filing_date = filing_dates[i]
                    return {
                        'url': f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{primary}",
                        'filing_date': filing_date,
                    }
    except Exception as e:
        print(f"  10-K lookup error: {e}")
    return None

def extract_10k_text(html_content: str, max_chars: int = 15000) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    keywords = ['supplier', 'vendor', 'source', 'manufactur', 'customer', 'client', 
                'partner', 'supply chain', 'raw material', 'component']
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    relevant = []
    for s in sentences:
        s = s.strip()
        if len(s) < 100 or len(s) > 1000:
            continue
        lower = s.lower()
        if any(k in lower for k in keywords):
            relevant.append(s)
    
    result = ' '.join(relevant[:100])
    return result[:max_chars]

def llm_extract_relationships(ticker: str, company_name: str, text: str) -> Dict:
    prompt = f"""从以下 {ticker} ({company_name}) 的 10-K 文件中，提取供应链和客户关系信息。

只提取明确提及的公司名称，不要提取 "The Company"、"Americas" 等泛指。

## 文本片段
{text}

## 输出格式 (JSON)
{{
    "suppliers": ["供应商1", "供应商2"],
    "customers": ["客户1", "客户2"],
    "confidence": "high/medium/low"
}}
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are a financial analyst. Extract supply chain relationships from SEC 10-K. Only return valid JSON, no other text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        content = ""
        if response.choices and response.choices[0].message:
            content = response.choices[0].message.content or ""
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = content.strip('`')
        return {
            'data': json.loads(content),
            'raw': content
        }
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return {'data': {'suppliers': [], 'customers': [], 'confidence': 'low'}, 'raw': str(e)}
    except Exception as e:
        print(f"  LLM extraction error: {e}")
        return {'data': {'suppliers': [], 'customers': [], 'confidence': 'low'}, 'raw': str(e)}

def get_10k_relationships(ticker: str) -> Dict:
    result = {
        'source': 'SEC EDGAR 10-K + LLM',
        'filing_date': None,
        'suppliers': [],
        'customers': [],
        'confidence': 'low',
        'raw_snippets': [],
    }
    
    cik = get_cik_from_ticker(ticker)
    if not cik:
        print(f"  No CIK found for {ticker}")
        return result
    print(f"  CIK: {cik}")
    
    time.sleep(0.2)
    filing_info = get_latest_10k_info(cik)
    if not filing_info:
        print(f"  No 10-K found")
        return result
    
    result['filing_date'] = filing_info['filing_date']
    print(f"  10-K date: {filing_info['filing_date']}")
    time.sleep(0.2)
    
    try:
        resp = httpx.get(filing_info['url'], headers=SEC_HEADERS, timeout=60, follow_redirects=True)
        if resp.status_code == 200:
            text = extract_10k_text(resp.text)
            print(f"  Text length: {len(text)} chars")
            
            if len(text) < 500:
                print(f"  Insufficient relevant text")
                return result
            
            info = get_company_info_yfinance(ticker)
            company_name = info['company_name'] if info else ticker
            
            llm_result = llm_extract_relationships(ticker, company_name, text)
            result['suppliers'] = llm_result['data'].get('suppliers', [])[:8]
            result['customers'] = llm_result['data'].get('customers', [])[:8]
            result['confidence'] = llm_result['data'].get('confidence', 'low')
            result['raw_snippets'] = [text[:500]] if text else []
            
            print(f"  Suppliers: {result['suppliers'][:3]}")
            print(f"  Customers: {result['customers'][:3]}")
    except Exception as e:
        print(f"  Error: {e}")
    
    return result

def get_company_info_yfinance(ticker: str) -> Optional[Dict]:
    try:
        import yfinance
        stock = yfinance.Ticker(ticker)
        info = stock.info
        return {"company_name": info.get('longName', ticker)}
    except:
        return None


if __name__ == "__main__":
    import json
    test_tickers = ["NVDA", "AAPL"]
    for ticker in test_tickers:
        print(f"\n{'='*50}")
        print(f"Testing {ticker}")
        print('='*50)
        data = get_10k_relationships(ticker)
        print(f"\nResult: {json.dumps(data, indent=2, ensure_ascii=False)}")
        time.sleep(2)
