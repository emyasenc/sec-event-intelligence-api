import asyncio
from src.services.sec import SECService
from src.services.classifier import EventClassifier

async def test():
    sec = SECService()
    classifier = EventClassifier()
    
    # Get filings
    print("Getting filings...")
    filings = await sec.get_filings("0000320193", "8-K", 3)
    
    print(f"Found {len(filings)} filings")
    
    for filing in filings:
        print(f"\n--- {filing.form_type} ---")
        print(f"Accession: {filing.accession_number}")
        print(f"Source text length: {len(filing.source_text or '')}")
        print(f"Source text preview: {filing.source_text[:200] if filing.source_text else 'No source text'}...")
        
        # Classify
        events = classifier.classify_filing(filing)
        print(f"Events found: {len(events)}")
        for event in events:
            print(f"  - {event.event_type}: {event.description[:50]}...")

asyncio.run(test())
