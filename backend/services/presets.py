from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    url: str
    frequency: str  # 每日更新 / 動態網站 / 不定時更新 / 每月更新 / 每季更新 / 業師提供
    check_interval_minutes: int
    watch_description: str | None = None


def get_presets() -> list[Preset]:
    """
    常用追蹤清單（可擴充）。

    頻率建議：
    - 每日更新：1440 分
    - 動態網站：30~120 分
    - 不定時更新：360 分
    - 每月更新：43200 分（30 天）
    - 每季更新：129600 分（90 天）
    """
    return [
        Preset(
            id="twse-foreign-bfi82u",
            name="TWSE 三大法人買賣金額統計表",
            url="https://www.twse.com.tw/zh/trading/foreign/bfi82u.html",
            frequency="每日更新",
            check_interval_minutes=1440,
            watch_description="表格內容（今日三大法人買賣金額/日期更新）",
        ),
        Preset(
            id="twse-mi-index",
            name="TWSE 每日收盤行情",
            url="https://www.twse.com.tw/zh/trading/historical/mi-index.html",
            frequency="每日更新",
            check_interval_minutes=1440,
            watch_description="收盤行情與表格更新（日期、指數、成交資訊）",
        ),
        Preset(
            id="mops-t100sb02-1",
            name="MOPS 法人說明會一覽表（互動頁）",
            url="https://mops.twse.com.tw/mops/web/t100sb02_1",
            frequency="動態網站",
            check_interval_minutes=360,
            watch_description="提醒：此頁需選月份與按查詢才會顯示結果；目前以頁面文字變動為主，建議搭配「立即檢查」。",
        ),
        Preset(
            id="cnyes-headline",
            name="鉅亨網 即時頭條",
            url="https://m.cnyes.com/news/cat/headline",
            frequency="動態網站",
            check_interval_minutes=30,
            watch_description="頭條列表（最新標題/時間）",
        ),
        Preset(
            id="cme-fedwatch",
            name="CME FedWatch Tool",
            url="https://www.cmegroup.com/cn-t/markets/interest-rates/cme-fedwatch-tool.html",
            frequency="動態網站",
            check_interval_minutes=360,
            watch_description="FedWatch 主要機率/表格（利率路徑機率）。注意：此站常對程式抓取回覆 403，本系統僅能簡單 HTTP 抓取；若一直失敗需改用瀏覽器外掛（如 Playwright）或改追蹤別的新聞/數據來源。",
        ),
        Preset(
            id="tw-gazette",
            name="行政院公報資訊網",
            url="https://gazette.nat.gov.tw/egFront/browseVolume.do?action=doGroupQuery&chapter=4&log=filter&filterId=114",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="追蹤最新「卷期瀏覽」，查詢條件鎖定「財政經濟篇」，並確認是否為最新期公報。",
        ),
        Preset(
            id="tw-mops",
            name="公開資訊觀測站 MOPS",
            url="https://mops.twse.com.tw/mops/web/t05sr01_1",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="追蹤最新「即時重大資訊」，可篩選上市、上櫃或興櫃公司的重大訊息與財報公告日期。",
        ),
        Preset(
            id="tw-ardf",
            name="會計研究發展基金會 ARDF",
            url="https://www.ardf.org.tw/",
            frequency="不定時更新",
            check_interval_minutes=360,
            watch_description="IFRS/TIFRS 準則更新、解釋、教育資源",
        ),
        Preset(
            id="tw-ardf-iasb",
            name="ARDF IFRS動態（最新消息）",
            url="https://www.ardf.org.tw/iasb.html",
            frequency="不定時更新",
            check_interval_minutes=360,
            watch_description="IFRS動態頁面的日期、標題與內容摘要更新",
        ),
        Preset(
            id="tw-fsc",
            name="金融監督管理委員會 FSC",
            url="https://www.fsc.gov.tw/",
            frequency="每日更新",
            check_interval_minutes=1440,
            watch_description="金融監理規範、財報揭露要求、函令",
        ),
        Preset(
            id="mentor-mof-news",
            name="財政部－本部新聞",
            url="https://www.mof.gov.tw/multiplehtml/384fb3077bb349ea973e7fc6f13b6974",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="追蹤最新新聞資訊，特別是「本部新聞」類別下關於稅務、電子發票及軟體申報的公告。",
        ),
        Preset(
            id="mentor-ntbna-news",
            name="財政部－北區國稅局",
            url="https://www.ntbna.gov.tw/htmlList/b6749b429a3b4ca7828e366d6fde8bcc",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="追蹤最新「新聞稿」與「本週新聞」，留意遺產稅、營利事業所得稅及 AI 輔助查核等資訊。",
        ),
        Preset(
            id="mentor-moea-news",
            name="經濟部－本部新聞",
            url="https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=1&menu_id=40",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="只監測「首頁 > 新聞與公告 > 本部新聞」列表。Agent 1 請穩定擷取新聞列表中的日期、標題、發布單位與時間；Agent 2 僅整理新增或移除中與法規、公告、政策發布、公告送達相關的項目，忽略一般宣傳性新聞。",
        ),
        Preset(
            id="mentor-moea-clarification",
            name="經濟部－即時新聞澄清",
            url="https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=9&menu_id=22333",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="只監測「首頁 > 新聞與公告 > 即時新聞澄清」列表。Agent 1 請穩定擷取澄清新聞列表中的日期、標題、發布單位與時間；Agent 2 優先整理新增或移除的澄清、說明、更正與公告送達資訊，不要提供其他無關新聞。",
        ),
        Preset(
            id="mentor-ida-news",
            name="經濟部產業發展署－新聞發布",
            url="https://www.ida.gov.tw/ctlr?PRO=news.NewsList",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="追蹤最新「新聞發布」，重點在於產業政策（如淨零碳排、AI 發展）及最新公告事項。",
        ),
        Preset(
            id="mentor-ida-rss",
            name="經濟部產業發展署－新聞 RSS",
            url="https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="RSS 格式，包含產業政策新聞、重大宣布及發展成果。比網頁版更及時（每 6 小時檢查），自動比對差異並推送通知。",
        ),
        Preset(
            id="mentor-labuan-legislation",
            name="Labuan Legislation",
            url="https://www.labuanfsa.gov.my/regulations/legislation/act",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="檢測是否有新法案（Acts），並進一步確認各法案子項目是否有更新（如 2025 年修正案）。",
        ),
        Preset(
            id="mentor-labuan-media",
            name="Labuan Media",
            url="https://www.labuanibfc.com/resources-events/media/press-releases",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="追蹤最新新聞資訊，包含新聞稿（Press Releases）以及重要演講稿（Speeches）。",
        ),
        Preset(
            id="mentor-oecd-beps",
            name="OECD Base erosion and profit shifting (BEPS)",
            url="https://www.oecd.org/en/topics/beps.html",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="追蹤最新新聞與洞察（Latest insights），關注移轉定價、有害稅收實踐及統計報告。",
        ),
        Preset(
            id="mentor-oecd-global-minimum-tax",
            name="OECD Global Minimum Tax",
            url="https://www.oecd.org/en/topics/global-minimum-tax.html",
            frequency="業師提供",
            check_interval_minutes=30,
            watch_description="追蹤全球最低稅負制最新進展，包含 Pillar Two、XML 數據交換格式及相關申報指南。",
        ),
    ]

