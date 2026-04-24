import requests
import re
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
HEADERS = {'User-Agent': UA}
TIMEOUT = 12

def get_content(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        return r.text if r.status_code == 200 else None
    except:
        return None

def find_sitemap_urls(base_url):
    urls = set()
    sitemaps = ['/sitemap.xml', '/sitemap_index.xml']
    for sm in sitemaps:
        content = get_content(urljoin(base_url, sm))
        if content:
            # Simple regex to find <loc> tags
            locs = re.findall(r'<loc>(.*?)</loc>', content)
            for loc in locs:
                if 'labuanfsa.gov.my' in loc:
                    urls.add(loc)
        if len(urls) >= 80: break
    return list(urls)[:80]

def extract_candidates(url):
    candidates = set()
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        if r.status_code != 200: return candidates
        text = r.text
        
        # Link rel alternate
        links = re.findall(r'<link[^>]+rel=["'']alternate["''][^>]+>', text)
        for link in links:
            if 'rss' in link.lower() or 'atom' in link.lower() or 'xml' in link.lower():
                href = re.search(r'href=["''](.*?)["'']', link)
                if href: candidates.add(urljoin(url, href.group(1)))
        
        # A tags
        atags = re.findall(r'<a[^>]+href=["''](.*?)["''][^>]*>(.*?)</a>', text, re.I | re.S)
        for href, label in atags:
            if re.search(r'feed|rss|atom|xml', href + label, re.I):
                candidates.add(urljoin(url, href))
    except:
        pass
    return candidates

def validate_rss(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        content_type = r.headers.get('Content-Type', '').lower()
        is_rss = False
        if 'application/rss+xml' in content_type or 'application/atom+xml' in content_type or 'text/xml' in content_type:
            is_rss = True
        
        body = r.text.strip()
        if body.startswith('<?xml') or body.startswith('<rss') or body.startswith('<feed'):
            if '<rss' in body or '<feed' in body:
                is_rss = True
        return is_rss, r.status_code, content_type
    except:
        return False, 0, 'error'

def main():
    base = "https://www.labuanfsa.gov.my"
    seeds = [
        "https://www.labuanfsa.gov.my/",
        "https://www.labuanfsa.gov.my/news",
        "https://www.labuanfsa.gov.my/press-release",
        "https://www.labuanfsa.gov.my/media-centre",
        "https://www.labuanfsa.gov.my/regulations/legislation/act"
    ]
    
    print("Probing sitemaps...")
    sitemap_urls = find_sitemap_urls(base)
    all_pages = list(set(seeds + sitemap_urls))[:120]
    
    print(f"Scanning {len(all_pages)} pages for RSS candidates...")
    candidates = set()
    for p in all_pages:
        candidates.update(extract_candidates(p))
    
    valid_rss = []
    suspicious = []
    invalid = []
    
    print(f"Validating {len(candidates)} candidates...")
    for c in list(candidates):
        # Filter for same domain or obvious RSS
        if 'labuanfsa.gov.my' not in c and not any(x in c.lower() for x in ['rss', 'feed']):
            continue
            
        is_rss, status, ctype = validate_rss(c)
        if is_rss:
            valid_rss.append(c)
        elif status == 200:
            suspicious.append(c)
        else:
            invalid.append(c)
            
    print("\n--- Summary ---")
    print(f"可用RSS (validated true): {len(valid_rss)}")
    for v in valid_rss: print(f"  - {v}")
    
    print(f"可疑但未驗證: {len(suspicious)}")
    print(f"無效候選: {len(invalid)}")
    
    if valid_rss:
        print("結論: 有RSS")
    elif suspicious:
        print("結論: 可能有但需人工確認")
    else:
        print("結論: 未發現RSS")

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
