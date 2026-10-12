import asyncio
from src.services.sec import SECService

async def test():
    sec = SECService()
    
    # Get filings for Apple
    print("Getting filings for Apple...")
    filings = await sec.get_filings("0000320193", limit=5)
    
    print(f"Found {len(filings)} filings")
    for f in filings:
        print(f"  - {f.form_type}: {f.accession_number} - {f.filing_date}")
        print(f"    URL: {f.document_url[:80]}...")

asyncio.run(test())
