import requests
import re
from urllib.parse import urljoin

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
HEADERS = {'User-Agent': UA}
TIMEOUT = 12

def check(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        print(f"Check {url} -> {r.status_code}")
        return r.text if r.status_code == 200 else None
    except Exception as e:
        print(f"Error {url}: {e}")
        return None

def main():
    root = "https://www.labuanfsa.gov.my"
    # Try more paths
    paths = ["/robots.txt", "/sitemap.xml", "/feeds", "/rss", "/feed", "/announcements", "/media-centre/news"]
    for p in paths:
        content = check(root + p)
        if content and p == "/robots.txt":
            # Just print first lines of robots.txt
            print("Robots.txt snippet:")
            print("\n".join(content.splitlines()[:5]))
    
    # Check news page specifically for links
    news_html = check(root + "/media-centre/news")
    if news_html:
        links = re.findall(r'href=["''](.*?)["'']', news_html)
        rss_links = [l for l in links if 'rss' in l.lower() or 'xml' in l.lower()]
        print(f"Found RSS/XML links: {rss_links}")

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
