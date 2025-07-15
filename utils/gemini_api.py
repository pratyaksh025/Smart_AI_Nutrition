import requests
import base64
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from secrets_config import GEMINI_API_KEY


if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in config.py. Please provide a valid API key.")

FLASH_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

def encode_image(image_path):
    """Encodes an image to base64 for multimodal queries."""
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def ask_gemini_flash(user_text, image_path=None, target_language='en-US'):
    """
    Uses Gemini 1.5 Flash 2.0 for both text-only and multimodal (image + text) nutrition queries.
    The user_text now includes comprehensive context (original query, profile, feedback).
    The response will be generated in the specified target_language.
    """
    prompt_parts = []

    system_prompt = f"""
You are a helpful and knowledgeable AI Nutrition Assistant. Your goal is to provide personalized, accurate, and actionable nutrition advice, meal suggestions, and food analysis based on the user's query, their profile, and their past feedback.

When providing information, adhere strictly to these formatting guidelines:

1.  If it's a meal request (e.g., "Suggest breakfast options," "meal plan"):
    - Provide exactly 3 distinct meal options.
    - For each meal option, include:
        - A concise Description of the meal.
        - A detailed Nutritional Info section with:
            - Protein: Xg
            - Carbohydrates: Xg
            - Fats: Xg
            - Fiber: Xg
            - Calories: X kcal

2.  If it's a single food item query (e.g., "nutritional info for apple"):
    - Provide a detailed nutritional breakdown for that specific item.

3.  If it's a general nutrition question (e.g., "benefits of protein"):
    - Give a clear, comprehensive, and detailed answer.

IMPORTANT:
- Personalization: Tailor your responses based on the user's provided profile (age, gender, diet, goal, height, weight, BMI, medical conditions) and their feedback (liked/disliked items).
- Avoid Disliked Items: Explicitly avoid recommending or including ingredients/concepts that the user has previously disliked.
- Clarity: Ensure all nutritional values are clearly stated with units.
- Tone: Maintain a helpful, encouraging, and professional tone.
- Language: Respond entirely in the language corresponding to the BCP-47 language tag: {target_language}.

"""
    prompt_parts.append({"text": system_prompt.strip()})
    prompt_parts.append({"text": f"\n---\n{user_text}\n---\n"})

    if image_path:
        encoded_image = encode_image(image_path)
        if encoded_image:
            prompt_parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": encoded_image
                }
            })

    payload = {
        "contents": [
            {"role": "user", "parts": prompt_parts}
        ]
    }

    try:
        response = requests.post(FLASH_URL, json=payload)
        response.raise_for_status()

        response_json = response.json()

        if response_json and 'candidates' in response_json and \
           len(response_json['candidates']) > 0 and \
           'content' in response_json['candidates'][0] and \
           'parts' in response_json['candidates'][0]['content'] and \
           len(response_json['candidates'][0]['content'].get('parts', [])) > 0:
            return response_json['candidates'][0]['content']['parts'][0]['text'].replace('*', '')
        else:
            return "Sorry, I couldn't generate a response. The AI provided an empty or unexpected reply. Please try again."
    except requests.exceptions.HTTPError as http_err:
        return f"Sorry, an HTTP error occurred with the AI. ({http_err.response.status_code}) Please check your API key or try again later."
    except requests.exceptions.ConnectionError as conn_err:
        return "Sorry, a network connection error occurred while reaching the AI. Please check your internet connection."
    except requests.exceptions.Timeout as timeout_err:
        return "Sorry, the AI request timed out. Please try again later."
    except requests.exceptions.RequestException as req_err:
        return "Sorry, an unknown error occurred with the AI request. Please try again later."
    except Exception as e:
        return f"Sorry, an unexpected error occurred with the AI. Please try again later. (Error: {e})"

def ask_gemini(user_text, image_path=None, target_language='en-US'):
    """
    Unified function to ask Gemini models.
    Always uses Gemini 1.5 Flash for both text and multimodal inputs.
    Passes target_language to the underlying ask_gemini_flash function.
    """
    return ask_gemini_flash(user_text, image_path, target_language)
