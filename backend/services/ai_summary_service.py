"""AI 差異摘要服務（Google AI Studio / Gemini）。"""
import os

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def generate_diff_summary(
    *,
    site_name: str,
    url: str,
    source_type: str,
    raw_diff_summary: str,
    api_key: str | None = None,
    model_name: str | None = None,
) -> str | None:
    """
    產生 AI 差異摘要。失敗回傳 None（由呼叫端 fallback）。
    """
    if not _env_bool("AI_SUMMARY_ENABLED", False):
        return None

    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key or not genai:
        return None

    model_name = model_name or os.environ.get("AI_SUMMARY_MODEL") or "gemini-1.5-flash"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = f"""你是網站變更摘要助手。請根據給定差異，輸出「精簡、可讀」的繁體中文摘要。

【網站名稱】
{site_name}

【網址】
{url}

【資料來源】
{source_type.upper()}

【原始差異摘要】
{raw_diff_summary}

請遵守：
1) 只根據提供內容，不可臆測。
2) 最多 3 點，每點 1 句。
3) 盡量指出「新增／移除／影響」。
4) 純文字輸出，不要加 Markdown 標題。
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 280},
        )
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            return None
        return text[:1000]
    except Exception:
        return None
