import asyncio
from src.services.sec import SECService
from src.services.classifier import EventClassifier

async def test():
    sec = SECService()
    classifier = EventClassifier()
    
    print("Getting filings for AAPL...")
    filings = await sec.get_filings("0000320193", "8-K", 2)
    
    print(f"Found {len(filings)} filings")
    
    for i, filing in enumerate(filings):
        print(f"\n--- Filing {i+1}: {filing.form_type} ---")
        print(f"Accession: {filing.accession_number}")
        print(f"Source text length: {len(filing.source_text or '')}")
        
        if filing.source_text:
            print(f"Source text preview: {filing.source_text[:300]}...")
            
            # Try to classify
            events = classifier.classify_filing(filing)
            print(f"Events found: {len(events)}")
            for event in events:
                print(f"  - {event.event_type}: {event.description[:50]}...")
        else:
            print("❌ No source text available!")

asyncio.run(test())
