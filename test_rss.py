import sys
import os

# Add relevant paths to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    # Based on findings, these are in backend.services.scraper
    from backend.services.scraper import detect_rss_feeds, validate_rss_feed
    
    # 1. Test detect_rss_feeds
    html_sample = '''
    <html>
    <head>
    <link rel="alternate" type="application/rss+xml" title="Latest Posts" href="https://example.com/feed.xml">
    </head>
    <body>Test</body>
    </html>
    '''
    print("--- 测试 detect_rss_feeds ---")
    detected = detect_rss_feeds(html_sample, "https://example.com")
    print(f"检测到的 RSS 订阅源: {detected}")
    
    # 2. Test validate_rss_feed
    print("\n--- 测试 validate_rss_feed ---")
    # Using a generally stable RSS feed (BBC News)
    rss_url = "https://feeds.bbci.co.uk/news/rss.xml"
    print(f"验证 URL: {rss_url}")
    result = validate_rss_feed(rss_url)
    
    # Note: Checking the structure of 'result' based on common patterns
    # The output from previous step showed validate_rss_feed returns dict.
    if result.get('is_valid') or (result.get('title') and not result.get('error')):
        print(f"是否有效: 是")
        print(f"订阅源标题: {result.get('title')}")
        print(f"订阅源描述: {result.get('description', '无描述')}")
    else:
        print(f"是否有效: 否")
        print(f"结果/错误: {result}")

except ImportError as e:
    print(f"导入错误: {e}")
except Exception as e:
    print(f"运行出错: {e}")
