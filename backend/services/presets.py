from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    url: str
    frequency: str  # 每日更新 / 動態網站 / 不定時更新 / 每月更新 / 每季更新
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
            id="taiwanlottery-bingo",
            name="台灣彩券 Bingo Bingo 開獎結果",
            url="https://www.taiwanlottery.com/lotto/result/bingo_bingo",
            frequency="動態網站",
            check_interval_minutes=30,
            watch_description="開獎結果區塊（期別、獎號、時間）",
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
            id="tw-etax-portal",
            name="財政部稅務入口網",
            url="https://www.etax.nat.gov.tw/",
            frequency="每日更新",
            check_interval_minutes=1440,
            watch_description="最新消息、法規新訊、解釋令函、報稅制度更新",
        ),
        Preset(
            id="tw-law-moj",
            name="全國法規資料庫",
            url="https://law.moj.gov.tw/",
            frequency="不定時更新",
            check_interval_minutes=360,
            watch_description="關注所得稅法、營業稅法、稅捐稽徵法、公司法、商業會計法修正",
        ),
        Preset(
            id="tw-dot",
            name="財政部賦稅署",
            url="https://www.dot.gov.tw/",
            frequency="每日更新",
            check_interval_minutes=1440,
            watch_description="賦稅政策、公告、新聞稿",
        ),
        Preset(
            id="tw-mof",
            name="財政部",
            url="https://www.mof.gov.tw/",
            frequency="每日更新",
            check_interval_minutes=1440,
            watch_description="新聞稿、政策說明、預告修法",
        ),
        Preset(
            id="tw-gazette",
            name="行政院公報資訊網",
            url="https://gazette.nat.gov.tw/egFront/",
            frequency="不定時更新",
            check_interval_minutes=360,
            watch_description="法規修正預告與施行日期",
        ),
        Preset(
            id="tw-mops",
            name="公開資訊觀測站 MOPS",
            url="https://mops.twse.com.tw/mops/web/index",
            frequency="每日更新",
            check_interval_minutes=1440,
            watch_description="公司公告、財報、重大訊息（偏公司揭露）",
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
            id="oecd-tax",
            name="OECD Tax",
            url="https://www.oecd.org/tax/",
            frequency="不定時更新",
            check_interval_minutes=360,
            watch_description="BEPS、Pillar Two（全球最低稅負）等國際稅務政策",
        ),
        Preset(
            id="ifrs-foundation",
            name="IFRS Foundation",
            url="https://www.ifrs.org/",
            frequency="不定時更新",
            check_interval_minutes=360,
            watch_description="IFRS 更新、Exposure Draft",
        ),
        Preset(
            id="iasb-news",
            name="IASB News",
            url="https://www.ifrs.org/news-and-events/news/",
            frequency="不定時更新",
            check_interval_minutes=360,
            watch_description="新準則進度、修正案發布",
        ),
        Preset(
            id="iasb-monthly-update",
            name="IASB Update（每月）",
            url="https://www.ifrs.org/news-and-events/updates/iasb/",
            frequency="每月更新",
            check_interval_minutes=43200,
            watch_description="每月 IASB update 摘要",
        ),
        Preset(
            id="issb-monthly-update",
            name="ISSB Update（每月）",
            url="https://www.ifrs.org/news-and-events/updates/issb/",
            frequency="每月更新",
            check_interval_minutes=43200,
            watch_description="每月 ISSB update 摘要",
        ),
        Preset(
            id="ifric-quarterly-podcast",
            name="IFRIC Podcast（每季）",
            url="https://www.ifrs.org/news-and-events/podcasts/",
            frequency="每季更新",
            check_interval_minutes=129600,
            watch_description="IFRIC 季度播客/摘要更新",
        ),
        Preset(
            id="issb-implementation-insights",
            name="ISSB Implementation Insights（每季）",
            url="https://www.ifrs.org/news-and-events/news/",
            frequency="每季更新",
            check_interval_minutes=129600,
            watch_description="Q1/Q2/Q3/Q4 implementation insights 與相關更新",
        ),
    ]

