"""Test script to verify MOPS Agent implementation."""
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.services.mops_monitor_agent import extract_mops_structured, mops_snapshot_text
from backend.services.mops_diff_agent import generate_mops_diff_report, _extract_items


def test_mops_monitoring():
    """Test MOPS monitoring agent with sample data."""
    print("=" * 60)
    print("MOPS Agent Testing")
    print("=" * 60)
    
    # Sample snapshot 1 - Initial state
    snapshot_1 = """[站點] 公開資訊觀測站 MOPS
[區塊] 首頁 > 即時重大資訊
[來源] https://mops.twse.com.tw/mops/web/t05sr01_1
[筆數] 5
[即時資訊列表]
[2330] | 台積電 | 2026/04/28 14:30 | 董事長異動公告 | https://mops.twse.com.tw/...
[1101] | 台泥 | 2026/04/28 14:25 | 財務報告公告 | https://mops.twse.com.tw/...
[2884] | 玉山金 | 2026/04/28 14:20 | 股務公告 | https://mops.twse.com.tw/...
[3008] | 大立光 | 2026/04/28 14:15 | 重大訊息 | https://mops.twse.com.tw/...
[6005] | 群益證 | 2026/04/28 14:10 | 公司消息 | https://mops.twse.com.tw/...
"""
    
    # Sample snapshot 2 - With updates (新增2筆，移除1筆)
    snapshot_2 = """[站點] 公開資訊觀測站 MOPS
[區塊] 首頁 > 即時重大資訊
[來源] https://mops.twse.com.tw/mops/web/t05sr01_1
[筆數] 6
[即時資訊列表]
[2330] | 台積電 | 2026/04/28 14:35 | 重大資產收購公告 | https://mops.twse.com.tw/...
[2330] | 台積電 | 2026/04/28 14:30 | 董事長異動公告 | https://mops.twse.com.tw/...
[1101] | 台泥 | 2026/04/28 14:25 | 財務報告公告 | https://mops.twse.com.tw/...
[2884] | 玉山金 | 2026/04/28 14:20 | 股務公告 | https://mops.twse.com.tw/...
[3008] | 大立光 | 2026/04/28 14:15 | 重大訊息 | https://mops.twse.com.tw/...
[2412] | 中華電 | 2026/04/28 14:12 | 股東常會開催 | https://mops.twse.com.tw/...
"""
    
    print("\n📊 Test 1: Extract items from Snapshot 1")
    print("-" * 60)
    items_1 = _extract_items(snapshot_1)
    print(f"Extracted {len(items_1)} items from snapshot 1")
    for item in items_1:
        print(f"  - {item}")
    
    print("\n📊 Test 2: Extract items from Snapshot 2")
    print("-" * 60)
    items_2 = _extract_items(snapshot_2)
    print(f"Extracted {len(items_2)} items from snapshot 2")
    for item in items_2:
        print(f"  - {item}")
    
    print("\n📊 Test 3: Generate MOPS Diff Report (Snapshot 1 → Snapshot 2)")
    print("-" * 60)
    
    report = generate_mops_diff_report(
        previous_snapshot=snapshot_1,
        current_snapshot=snapshot_2,
        api_key=None,  # Test without API (basic mode)
    )
    
    if report:
        print(report)
    else:
        print("❌ Failed to generate report")
    
    print("\n✅ Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_mops_monitoring()
