import requests
from bs4 import BeautifulSoup
import urllib3
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET_URL = "https://www.labuanfsa.gov.my/regulations/legislation/act"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def check_content_for_rss(content):
    if not content:
        return False
    content_str = content.decode('utf-8', errors='ignore').lower()
    return any(tag in content_str for tag in ["<rss", "<feed", "<channel", "xmlns=\"http://www.w3.org/2005/atom\""])

def get_candidates():
    print(f"--- Requesting {TARGET_URL} ---")
    try:
        response = requests.get(TARGET_URL, headers=HEADERS, timeout=15, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        print("\n--- Phase 1: <link rel='alternate'> entries ---")
        links = soup.find_all('link', rel='alternate')
        found_p1 = False
        for link in links:
            t = link.get('type', '').lower()
            if any(x in t for x in ['rss', 'atom', 'xml']):
                print(f"Found: {link.get('href')} (type: {t})")
                found_p1 = True
        if not found_p1: print("None found.")

        print("\n--- Phase 2: <a href> link candidates ---")
        found_p2 = False
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if any(x in href for x in ['feed', 'rss', 'atom', 'xml']):
                full_url = urljoin(TARGET_URL, a['href'])
                print(f"Candidate: {full_url}")
                found_p2 = True
        if not found_p2: print("None found.")

    except Exception as e:
        print(f"Error fetching base URL: {e}")

def test_endpoints():
    print("\n--- Phase 3: Testing common endpoints ---")
    endpoints = ["/feed", "/rss", "/atom", "/feeds", "/feed.xml", "/rss.xml", "/atom.xml"]
    base_domain = "https://www.labuanfsa.gov.my"
    found_any = False
    
    for ep in endpoints:
        url = base_domain + ep
        try:
            r = requests.get(url, headers=HEADERS, timeout=10, verify=False)
            ct = r.headers.get('Content-Type', '').lower()
            is_rss = check_content_for_rss(r.content)
            print(f"URL: {url} | Status: {r.status_code} | Type: {ct} | Potential RSS: {is_rss}")
            if r.status_code == 200 and (is_rss or 'xml' in ct):
                found_any = True
        except:
            print(f"URL: {url} | Failed")
    return found_any

if __name__ == "__main__":
    get_candidates()
    any_found = test_endpoints()
    
    print("\n--- VERDICT ---")
    if any_found:
        print(" verdict: 有RSS")
    else:
        print(" verdict: 未發現RSS")
