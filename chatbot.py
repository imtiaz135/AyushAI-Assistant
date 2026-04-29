from google import genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# -------------------------------
# Gemini AI function
# -------------------------------
def ask_gemini(user_input: str) -> str:
    prompt = f"""
You are a smart AI assistant like ChatGPT.

- Answer any question clearly in simple English
- Keep answers concise (5–10 lines)
- Be helpful and accurate
- Do not repeat unnecessarily

User: {user_input}
Assistant:
"""

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        if hasattr(response, "text") and response.text:
            return response.text.strip()
    except Exception as e:
        print("Gemini primary failed:", e)

    # Fallback model
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        if hasattr(response, "text") and response.text:
            return response.text.strip()
    except Exception as e:
        print("Gemini fallback failed:", e)

    return ""


# -------------------------------
# Main chatbot function
# -------------------------------
def chatbot_response(query: str) -> str:
    # 🔥 Step 1: Try Gemini first
    gemini_reply = ask_gemini(query)
    if gemini_reply:
        return gemini_reply

    # 🔽 Step 2: fallback to your rule-based chatbot
    message = (query or "").lower().strip()

    knowledge_base = [
        (
            ["history of ayurveda", "ayurveda history", "origin of ayurveda"],
            "Ayurveda started in ancient India over 3,000 years ago. Its ideas were preserved in texts such as Charaka Samhita and Sushruta Samhita, which describe prevention, diagnosis, diet, herbs, and surgery in simple practical ways.",
        ),
        (
            ["what is ayurveda", "define ayurveda", "ayurveda meaning"],
            "Ayurveda is a traditional Indian system of medicine that focuses on healthy daily routine, food, sleep, herbs, and prevention.",
        ),
        (
            ["authentic", "real", "genuine"],
            "Authentic medical text usually uses balanced wording like 'may support', mentions context, and avoids absolute cure claims.",
        ),
        (
            ["fake", "exaggerated", "miracle", "100%"],
            "Fake or exaggerated claims often promise instant cure, guaranteed results, or treatment for every disease without evidence.",
        ),
        (
            ["aswagandha", "ashwagandha"],
            "Ashwagandha is traditionally used to support stress management and overall vitality.",
        ),
        (
            ["turmeric", "haldi", "curcumin"],
            "Turmeric contains curcumin and is commonly discussed for inflammation support.",
        ),
        (
            ["score", "authenticity score", "how score works"],
            "The analyzer combines rule-based checks and ML prediction, then produces a final authenticity score from 0 to 100.",
        ),
        (
            ["ocr", "text extraction"],
            "OCR reads text from the uploaded image before authenticity analysis starts.",
        ),
    ]

    for keywords, answer in knowledge_base:
        if any(keyword in message for keyword in keywords):
            return answer

    # fallback response
    return "I'm having trouble answering right now. Please try again."