import asyncio
import re
from bs4 import BeautifulSoup
import httpx

async def test_extract():
    client = httpx.AsyncClient(
        headers={"User-Agent": "YASEN-ALPHA-SEC-API/1.0 (emmayasenchak@gmail.com)"}
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
    
    soup = BeautifulSoup(xml_content, "xml")
    entries = soup.find_all("entry")
    print(f"Found {len(entries)} entries")
    
    for i, entry in enumerate(entries[:3]):
        print(f"\n--- Entry {i+1} ---")
        
        title = entry.find("title")
        print(f"Title: {title.text if title else 'None'}")
        
        content = entry.find("content")
        if content:
            content_str = str(content)
            print(f"Content length: {len(content_str)}")
            
            # Extract accession number
            acc_match = re.search(r'<accession-number>(.*?)</accession-number>', content_str)
            if acc_match:
                print(f"Accession number: {acc_match.group(1)}")
            else:
                print("No accession number found")
            
            # Extract filing type
            type_match = re.search(r'<filing-type>(.*?)</filing-type>', content_str)
            if type_match:
                print(f"Filing type: {type_match.group(1)}")
            else:
                print("No filing type found")
            
            # Extract filing href
            href_match = re.search(r'<filing-href>(.*?)</filing-href>', content_str)
            if href_match:
                print(f"Filing href: {href_match.group(1)}")
            else:
                print("No filing href found")
        else:
            print("No content element")
    
    await client.aclose()

asyncio.run(test_extract())
