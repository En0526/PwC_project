import requests
import re
from urllib.parse import urljoin, urlparse

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
HEADERS = {'User-Agent': UA}
TIMEOUT = 12

def get_content(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        return r.text if r.status_code == 200 else None
    except: return None

def main():
    base = "https://www.labuanfsa.gov.my"
    sitemap_url = "https://www.labuanfsa.gov.my/XTOPIA_sitemap.ashx"
    
    print(f"Fetching sitemap from {sitemap_url}...")
    content = get_content(sitemap_url)
    urls = []
    if content:
        urls = re.findall(r'<loc>(.*?)</loc>', content)
        print(f"Found {len(urls)} URLs in sitemap.")
    
    seeds = [
        "https://www.labuanfsa.gov.my/",
        "https://www.labuanfsa.gov.my/announcement",
        "https://www.labuanfsa.gov.my/media-centre/news-and-events",
        "https://www.labuanfsa.gov.my/media-centre/press-releases"
    ]
    all_pages = list(set(seeds + urls))[:100]
    
    candidates = set()
    print(f"Scanning {len(all_pages)} pages for RSS...")
    for p in all_pages:
        html = get_content(p)
        if not html: continue
        
        # Link rel alternate
        links = re.findall(r'<link[^>]+rel=["'']alternate["''][^>]+>', html)
        for link in links:
            if any(x in link.lower() for x in ['rss', 'atom', 'xml']):
                href = re.search(r'href=["''](.*?)["'']', link)
                if href: candidates.add(urljoin(p, href.group(1)))
        
        # A tags with label/href containing news/rss/feed/press
        atags = re.findall(r'<a[^>]+href=["''](.*?)["''][^>]*>(.*?)</a>', html, re.I | re.S)
        for href, label in atags:
            combined = (href + label).lower()
            if 'rss' in combined or 'feed' in combined:
                 candidates.add(urljoin(p, href))

    valid_rss = []
    print(f"Validating {len(candidates)} candidates...")
    for c in candidates:
        try:
            r = requests.get(c, headers=HEADERS, timeout=TIMEOUT, verify=False)
            body = r.text.strip().lower()
            if r.status_code == 200 and ('<rss' in body or '<feed' in body or '<?xml' in body):
                 valid_rss.append(c)
        except: pass

    print("\n--- Summary ---")
    print(f"可用RSS (validated true): {len(valid_rss)}")
    for v in valid_rss: print(f"  - {v}")
    print(f"結論: {'有RSS' if valid_rss else '未發現RSS'}")

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
