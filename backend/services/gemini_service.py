"""使用 Google AI Studio (Gemini) 依使用者描述從網頁中擷取「要觀看的區塊」。"""
import os

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def extract_watch_content(
    html: str,
    full_text: str,
    watch_description: str,
    api_key: str | None = None,
) -> str | None:
    """
    請 Gemini 根據使用者的 watch_description，從網頁內容中擷取「需要關注是否有更新」的區塊文字。
    回傳擷取出的文字，失敗回傳 None。
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key or not genai:
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""你是一個網頁內容擷取助手。使用者想監測某個網頁「是否有更新」，並特別關注以下部分：

【使用者想觀看的區塊描述】
{watch_description}

【網頁純文字內容（前幾段）】
{full_text[:30000]}

請從上述內容中，只擷取與「使用者想觀看的區塊」直接相關的文字。若找不到明確對應區塊，則擷取最相關的段落。
輸出時：只輸出擷取出的文字內容，不要加標題、不要加「根據您的描述……」等說明。若完全無關，輸出「無對應內容」。
"""

    try:
        response = model.generate_content(prompt)
        if response and response.text:
            text = response.text.strip()
            if "無對應內容" in text:
                return full_text[:15000]  # fallback 前段全文
            return text
    except Exception:
        pass
    return None
