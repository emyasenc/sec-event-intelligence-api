import asyncio
import xml.etree.ElementTree as ET
import re

async def test_parse():
    import httpx
    
    client = httpx.AsyncClient(
        headers={
            "User-Agent": "YASEN-ALPHA-SEC-API/1.0 (emmayasenchak@gmail.com)"
        }
    )
    
    url = "https://www.sec.gov/cgi-bin/browse-edgar"
    params = {
        "action": "getcompany",
        "CIK": "0000320193",
        "type": "",
        "dateb": "",
        "owner": "exclude",
        "start": 0,
        "count": 5,
        "output": "atom",
    }
    
    response = await client.get(url, params=params)
    xml_content = response.text
    
    # Save XML to file for inspection
    with open("debug_feed.xml", "w") as f:
        f.write(xml_content)
    print(f"✅ Saved XML to debug_feed.xml ({len(xml_content)} bytes)")
    
    # Try to parse
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_content)
    
    # Find all entries
    entries = root.findall(".//atom:entry", ns)
    print(f"Found {len(entries)} entries in XML")
    
    # Print first entry if exists
    if entries:
        entry = entries[0]
        title = entry.find("atom:title", ns)
        print(f"Title: {title.text if title is not None else 'None'}")
        
        content = entry.find("atom:content", ns)
        if content is not None:
            print(f"Content length: {len(content.text or '')}")
            # Look for accession number
            match = re.search(r'<accession-number>(.*?)</accession-number>', content.text or '')
            if match:
                print(f"Accession number: {match.group(1)}")
            else:
                print("No accession number found")
    
    await client.aclose()

asyncio.run(test_parse())
