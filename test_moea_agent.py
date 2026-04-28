import unittest

from backend.services.change_agent import generate_change_report
from backend.services.site_profiles import extract_known_section_snapshot


MOEA_URL = "https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=1&menu_id=40"
MOEA_CLARIFICATION_URL = "https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=9&menu_id=22333"


SAMPLE_HTML = """
<html>
  <body>
    <h2>本部新聞</h2>
    <table id="holderContent_grdNews">
      <tr>
        <td>
          <span class="begin-date-mm">4月</span>
          <span class="begin-date-dd">28</span>
          <span class="begin-date-yy">2026</span>
        </td>
        <td>
          <a id="holderContent_grdNews_lnkTitle_0" href="News_Content.aspx?n=abcd&s=1001">法規公告送達測試新聞</a>
          <span class="org-name">法制處</span>
          <span class="begin-date-time">09:30</span>
        </td>
      </tr>
      <tr>
        <td>
          <span class="begin-date-mm">4月</span>
          <span class="begin-date-dd">27</span>
          <span class="begin-date-yy">2026</span>
        </td>
        <td>
          <a id="holderContent_grdNews_lnkTitle_1" href="News_Content.aspx?n=abcd&s=1000">一般新聞測試</a>
          <span class="org-name">產業技術司</span>
          <span class="begin-date-time">14:15</span>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


SAMPLE_TEXT = "目前總共有 621 筆資料"


class MoeaAgentTests(unittest.TestCase):
    def test_extract_known_section_snapshot_for_moea_news(self):
        snapshot = extract_known_section_snapshot(
            url=MOEA_URL,
            html=SAMPLE_HTML,
            full_text=SAMPLE_TEXT,
            watch_description="追蹤本部新聞與公告送達",
        )

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.site_name, "經濟部")
        self.assertEqual(snapshot.section_name, "新聞與公告 > 本部新聞")
        self.assertIn("[總筆數] 621", snapshot.text)
        self.assertIn("[2026-04-28] 法規公告送達測試新聞（法制處 09:30）", snapshot.text)

    def test_generate_change_report_prioritizes_focus_keywords(self):
        previous_snapshot = "\n".join([
            "[站點] 經濟部",
            "[區塊] 新聞與公告 > 本部新聞",
            "[新聞列表]",
            "  [2026-04-27] 一般新聞測試（產業技術司 14:15） | https://example.com/1000",
        ])
        current_snapshot = "\n".join([
            "[站點] 經濟部",
            "[區塊] 新聞與公告 > 本部新聞",
            "[新聞列表]",
            "  [2026-04-28] 法規公告送達測試新聞（法制處 09:30） | https://example.com/1001",
            "  [2026-04-27] 一般新聞測試（產業技術司 14:15） | https://example.com/1000",
        ])

        report = generate_change_report(
            url=MOEA_URL,
            site_name="經濟部",
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            watch_description="關注法規、公告送達與本部新聞更新",
        )

        self.assertIn("關注條件命中", report)
        self.assertIn("關注重點新增", report)
        self.assertIn("法規公告送達測試新聞", report)

    def test_extract_known_section_snapshot_for_moea_clarification(self):
        clarification_html = SAMPLE_HTML.replace("<h2>本部新聞</h2>", "<h2>即時新聞澄清</h2>")
        snapshot = extract_known_section_snapshot(
            url=MOEA_CLARIFICATION_URL,
            html=clarification_html,
            full_text=SAMPLE_TEXT,
            watch_description="只監測即時新聞澄清",
        )

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.section_name, "新聞與公告 > 即時新聞澄清")


if __name__ == "__main__":
    unittest.main()
