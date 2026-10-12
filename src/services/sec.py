# SEC EDGAR API Identityn# Required by SEC: Identify your application and provide contact emailn# See: https://www.sec.gov/os/accessing-edgar-datan
"""
SEC EDGAR Client Service for SEC Event Intelligence API
"""

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import settings
from src.models.schemas import SECFiling

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SECService:
    """SEC EDGAR service for fetching company and filing data."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.sec.timeout,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            headers={
                "User-Agent": settings.sec.user_agent,
                "Accept": "application/json, text/html, application/xml",
                "Accept-Encoding": "gzip, deflate",
            },
            follow_redirects=True,
        )
        self._last_request_time = 0
        self._request_lock = asyncio.Lock()
        self._min_interval = 0.2
        logger.info("SECService initialized")
    
    async def _rate_limit(self) -> None:
        async with self._request_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_interval:
                await asyncio.sleep(self._min_interval - time_since_last)
            self._last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError))
    )
    async def _make_request(self, url: str, params: Optional[Dict] = None) -> httpx.Response:
        await self._rate_limit()
        
        try:
            response = await self.client.get(url, params=params)
            
            if response.status_code == 503:
                logger.warning(f"Received 503 from SEC, waiting...")
                await asyncio.sleep(5)
                return await self._make_request(url, params)
            
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = float(retry_after) if retry_after else 10
                logger.warning(f"Rate limited (429), waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                return await self._make_request(url, params)
            
            response.raise_for_status()
            return response
            
        except Exception as e:
            logger.error(f"Request error for {url}: {str(e)}")
            raise
    
    async def search_company(self, query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        
        query = query.strip()
        
        if re.match(r"^\d{10}$", query):
            return {"name": query, "cik": query, "ticker": ""}
        
        if re.match(r"^[A-Za-z]{1,5}$", query):
            ticker = query.upper()
            companies = await self._search_by_ticker(ticker)
            if companies:
                return companies[0]
        
        companies = await self._search_by_name(query)
        if companies:
            return companies[0]
        
        return None
    
    async def _search_by_name(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            response = await self._make_request(url)
            data = response.json()
            
            results = []
            name_lower = name.lower()
            
            for company_data in data.values():
                company_name = company_data.get("title", "")
                ticker = company_data.get("ticker", "")
                cik = str(company_data.get("cik_str", "")).zfill(10)
                
                if name_lower in company_name.lower():
                    results.append({
                        "name": company_name,
                        "ticker": ticker,
                        "cik": cik,
                    })
                    if len(results) >= limit:
                        break
            
            return results
        except Exception as e:
            logger.error(f"Error searching companies by name: {str(e)}")
            return []
    
    async def _search_by_ticker(self, ticker: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            response = await self._make_request(url)
            data = response.json()
            
            results = []
            ticker_upper = ticker.upper()
            
            for company_data in data.values():
                company_ticker = company_data.get("ticker", "")
                if company_ticker == ticker_upper:
                    results.append({
                        "name": company_data.get("title", ""),
                        "ticker": company_ticker,
                        "cik": str(company_data.get("cik_str", "")).zfill(10),
                    })
                    if len(results) >= limit:
                        break
            
            return results
        except Exception as e:
            logger.error(f"Error searching companies by ticker: {str(e)}")
            return []
    
    async def search_companies(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        if re.match(r"^[A-Za-z]{1,5}$", query):
            results = await self._search_by_ticker(query.upper(), limit)
            if results:
                return results
        return await self._search_by_name(query, limit)
    
    async def get_filings(
        self,
        cik: str,
        form_type: Optional[str] = None,
        limit: int = 20
    ) -> List[SECFiling]:
        """Get filings for a company with parallel text fetching."""
        cik = cik.zfill(10) if cik else ""
        if not cik:
            return []
        
        try:
            sec_cik = cik.lstrip("0") or "0"
            
            url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                "action": "getcompany",
                "CIK": sec_cik,
                "type": form_type or "",
                "dateb": "",
                "owner": "exclude",
                "start": 0,
                "count": min(limit, 100),
                "output": "atom",
            }
            
            await asyncio.sleep(0.5)
            response = await self._make_request(url, params=params)
            
            filings = self._parse_atom_feed_bs4(response.text, cik)
            
            if form_type:
                filings = [f for f in filings if f.form_type == form_type]
            
            filings = filings[:limit]
            
            # PARALLEL FETCHING: Fetch all filing texts concurrently
            if filings:
                # Create tasks for each filing
                async def fetch_filing_text_with_fallbacks(filing):
                    try:
                        doc_url = str(filing.document_url) if filing.document_url else ""
                        if doc_url:
                            text = await self._get_filing_text_with_fallbacks(doc_url)
                            filing.source_text = text
                        else:
                            filing.source_text = ""
                    except Exception as e:
                        logger.warning(f"Could not fetch source text for {filing.accession_number}: {e}")
                        filing.source_text = ""
                    return filing
                
                # Run all fetches in parallel
                tasks = [fetch_filing_text_with_fallbacks(filing) for filing in filings]
                filings = await asyncio.gather(*tasks)
            
            logger.info(f"Found {len(filings)} filings for CIK {cik}")
            return filings
            
        except Exception as e:
            logger.error(f"Error getting filings for CIK {cik}: {str(e)}")
            return []
    
    async def _get_filing_text_with_fallbacks(self, base_url: str) -> str:
        """Try multiple URL patterns to get filing text."""
        if not base_url:
            return ""
        
        base_url_str = str(base_url)
        
        # Generate possible URL patterns
        url_patterns = [
            base_url_str,  # Original
            base_url_str.replace(".htm", ".html"),  # .html
            base_url_str.replace("-index.htm", ".htm"),  # Already doing this
            base_url_str.replace(".htm", ".txt"),  # .txt (sometimes available)
            base_url_str.replace("/data/", "/Archives/edgar/data/"),  # Full path
        ]
        
        # Remove duplicates
        url_patterns = list(dict.fromkeys(url_patterns))
        
        for url in url_patterns:
            try:
                logger.debug(f"Trying URL: {url}")
                text = await self._get_filing_text(url)
                if text and len(text) > 100:  # Valid text found
                    logger.info(f"Successfully fetched text from: {url}")
                    return text
            except Exception as e:
                logger.debug(f"Failed with {url}: {str(e)}")
                continue
        
        return ""
    
    async def _get_filing_text(self, document_url: str) -> str:
        if not document_url:
            return ""
        
        try:
            url_str = str(document_url)
            if not url_str:
                return ""
            
            response = await self._make_request(url_str)
            soup = BeautifulSoup(response.text, "html.parser")
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n\s*\n", "\n\n", text)
            text = re.sub(r"\s+", " ", text)
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error fetching filing text: {str(e)}")
            raise
    
    def _parse_atom_feed_bs4(self, xml_content: str, cik: str) -> List[SECFiling]:
        """Parse SEC Atom feed using BeautifulSoup."""
        filings = []
        
        try:
            soup = BeautifulSoup(xml_content, "xml")
            entries = soup.find_all("entry")
            logger.info(f"Found {len(entries)} entries in XML")
            
            company_name = "Unknown Company"
            company_info = soup.find("company-info")
            if company_info:
                conformed_name = company_info.find("conformed-name")
                if conformed_name:
                    company_name = conformed_name.text.strip()
            
            for entry in entries:
                try:
                    title_elem = entry.find("title")
                    title = title_elem.text.strip() if title_elem else ""
                    
                    updated_elem = entry.find("updated")
                    filing_date = datetime.now()
                    if updated_elem and updated_elem.text:
                        try:
                            date_str = updated_elem.text.replace("T", " ").split(".")[0]
                            filing_date = datetime.fromisoformat(date_str)
                        except:
                            pass
                    
                    content_elem = entry.find("content")
                    accession_number = ""
                    filing_type = ""
                    filing_url = ""
                    document_url = ""
                    
                    if content_elem:
                        content_text = str(content_elem)
                        
                        acc_match = re.search(r'<accession-number>(.*?)</accession-number>', content_text)
                        if acc_match:
                            accession_number = acc_match.group(1).strip()
                        
                        type_match = re.search(r'<filing-type>(.*?)</filing-type>', content_text)
                        if type_match:
                            filing_type = type_match.group(1).strip()
                        
                        href_match = re.search(r'<filing-href>(.*?)</filing-href>', content_text)
                        if href_match:
                            filing_url = href_match.group(1).strip()
                            # Try to find the actual document URL
                            # First try the primary document
                            document_url = filing_url.replace("-index.htm", ".txt")
                    
                    if not accession_number:
                        continue
                    
                    form_type = filing_type if filing_type else "8-K"
                    
                    # Map form types
                    form_type_map = {
                        "SD": "8-K",
                        "SCHEDULE13G": "SC 13G",
                        "SCHEDULE13G/A": "SC 13G",
                    }
                    form_type = form_type_map.get(form_type, form_type)
                    
                    description = title or f"{form_type} filing"
                    
                    filing = SECFiling(
                        accession_number=accession_number,
                        form_type=form_type,
                        filing_date=filing_date,
                        company_name=company_name,
                        company_cik=cik,
                        ticker=None,
                        filing_url=filing_url,
                        document_url=document_url,
                        description=description,
                    )
                    
                    filings.append(filing)
                    
                except Exception as e:
                    logger.warning(f"Error parsing entry: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing Atom feed: {str(e)}")
        
        logger.info(f"Parsed {len(filings)} filings from Atom feed")
        return filings


__all__ = ["SECService"]
