import os, json, re, socket
from typing import Dict, Any
from langdetect import detect, DetectorFactory

# === Deep Translator setup ===
try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None
    print("⚠️ Deep Translator not installed correctly. Run: pip install deep-translator")

def safe_translate(text, target="en"):
    try:
        translator = GoogleTranslator(source="auto", target=target)
        return translator.translate(text)
    except Exception as e:
        print(f"⚠️ Translation error: {e}")
        return text   # fallback without error

# === Gemini setup ===
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    print("⚠️ Gemini module not found. Run: pip install google-generativeai")

# Consistent language detection
DetectorFactory.seed = 0

# === Gemini setup ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAS_GEMINI = False

if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        HAS_GEMINI = True
    except Exception as e:
        print("⚠️ Gemini import failed:", e)
        HAS_GEMINI = False

# === Load Knowledge Base ===
KB_PATH = os.path.join(os.path.dirname(__file__), "kb.json")

def load_kb():
    if not os.path.exists(KB_PATH):
        return {}
    with open(KB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    out = {}
    if isinstance(data, list):
        for entry in data:
            keys = entry.get("keywords") or []
            if isinstance(keys, str):
                keys = [k.strip() for k in keys.split(",") if k.strip()]
            for k in keys:
                out[k.lower()] = {
                    "en": entry.get("answer_en", ""),
                    "hi": entry.get("answer_hi", ""),
                    "ta": entry.get("answer_ta", ""),
                    "ml": entry.get("answer_ml", ""),   # 🟢 ADDED
                    "te": entry.get("answer_te", "")    # 🟢 ADDED
                }
    return out

KB = load_kb()

# === Utility functions ===
def is_online() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

def detect_language(text: str) -> str:
    """Detect language using Unicode-based heuristics."""
    try:
        if re.search(r'[\u0900-\u097F]', text): return 'hi'  # Hindi
        if re.search(r'[\u0B80-\u0BFF]', text): return 'ta'  # Tamil
        if re.search(r'[\u0D00-\u0D7F]', text): return 'ml'  # Malayalam 🟢 ADDED
        if re.search(r'[\u0C00-\u0C7F]', text): return 'te'  # Telugu 🟢 ADDED
        return detect(text)
    except:
        return "en"

def translate_text(text: str, dest: str) -> str:
    try:
        return GoogleTranslator(source='auto', target=dest).translate(text)
    except Exception as e:
        print("⚠️ Translation error:", e)
        return text

# === KB Search ===
def find_in_kb(message: str):
    m = message.lower()
    for k, v in KB.items():
        if k in m:
            return v
    tokens = re.findall(r"\w+", m)
    for k, v in KB.items():
        ktoks = re.findall(r"\w+", k)
        if any(t in ktoks for t in tokens if len(t) > 3):
            return v
    return None

# === Gemini Fallback ===
def gemini_fallback(user_profile: Dict[str, Any], message_text: str, target_lang: str = "en") -> str:
    if not HAS_GEMINI:
        return ""

    try:
        prompt = (
            f"You are an expert agronomist chatbot.\n"
            f"User profile: {user_profile}\n"
            f"Question: {message_text}\n"
            f"Reply fluently in {target_lang}. "
            f"If the question is in Hindi, Tamil, Malayalam, or Telugu then respond in that language."  # 🟢 UPDATED
        )
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else ""
    except Exception as e:
        print("⚠️ Gemini error:", e)
        return ""

# === Main message processor ===
def process_message(user_profile: Dict[str, Any], message_text: str) -> str:
    if not message_text or not message_text.strip():
        return "Please ask a question about crops, soil, or pests."

    online_status = is_online()
    print("✅ Debug Info → Internet:", online_status, "| Gemini:", HAS_GEMINI)

    # 1️⃣ Detect user language
    user_lang = detect_language(message_text)

    # 2️⃣ Translate to English for KB search
    text_for_kb = message_text if user_lang == "en" else translate_text(message_text, "en")

    # 3️⃣ Try KB
    kb_item = find_in_kb(text_for_kb)
    if kb_item:
        ans = kb_item.get(user_lang) or kb_item.get("en") or ""
        if ans and user_lang != "en":
            ans = translate_text(ans, user_lang)
        return ans

    # 4️⃣ Use Gemini if online
    if HAS_GEMINI and online_status:
        resp = gemini_fallback(user_profile, message_text, target_lang=user_lang)
        if resp:
            return resp

    return "I’m currently offline. Please ask something simpler or try again later."
