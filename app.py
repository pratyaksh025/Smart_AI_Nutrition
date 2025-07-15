from flask import Flask, render_template, session, redirect, url_for, request, jsonify
import os
import uuid
import csv
from datetime import datetime
import pandas as pd
import requests # For making requests to external APIs (like Gemini, or a real translation API)

from utils.gemini_api import ask_gemini
from utils.auth import auth_blueprint, USER_CSV # Import USER_CSV from auth
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GEMINI_API_KEY


app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY # Use the secret key from config.py

# --- Config ---
UPLOAD_FOLDER = 'static/uploads'
DATA_DIR = 'data'
FEEDBACK_DIR = os.path.join(DATA_DIR, 'feedback')
MEALS_DIR = os.path.join(DATA_DIR, 'meals')
FEEDBACK_CSV_FILE = os.path.join(FEEDBACK_DIR, 'user_feedback.csv')

# Ensure required directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FEEDBACK_DIR, exist_ok=True)
os.makedirs(MEALS_DIR, exist_ok=True)

# Register authentication blueprint
app.register_blueprint(auth_blueprint)

# Store recent bot responses (in-memory)
recent_bot_responses = {}

# --- Feedback Manager ---
class FeedbackManager:
    def __init__(self, csv_file_path):
        self.csv_file_path = csv_file_path
        self._initialize_csv()

    def _initialize_csv(self):
        if not os.path.exists(self.csv_file_path):
            with open(self.csv_file_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['timestamp', 'user_id', 'message_id', 'bot_response_content', 'feedback_type'])

    def load_user_feedback(self, user_id):
        feedback_data = []
        if os.path.exists(self.csv_file_path):
            with open(self.csv_file_path, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get('user_id') == str(user_id):
                        feedback_data.append(row)
        return feedback_data

    def store_feedback(self, user_id, message_id, feedback_type, message_content=''):
        try:
            self.ensure_feedback_file(user_id) # Ensure file exists before writing
            filename = self.get_feedback_filename(user_id) # Get user-specific feedback file

            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([datetime.now().isoformat(), user_id, message_id, message_content, feedback_type])
            return True
        except Exception as e:
            print(f"Error storing feedback: {e}")
            return False

    def analyze_feedback(self, user_id):
        feedback_history = self.load_user_feedback(user_id)
        preferences = {
            'liked_items': [],
            'disliked_items': [],
            'general_sentiment': {}
        }

        for entry in feedback_history:
            content = entry.get('bot_response_content', '').strip()
            feedback_type = entry.get('feedback_type')

            if content:
                if feedback_type == 'like':
                    preferences['liked_items'].append(content)
                elif feedback_type == 'dislike':
                    preferences['disliked_items'].append(content)

        preferences['liked_items'] = list(set(preferences['liked_items']))[:5] # Limit to 5 recent liked
        preferences['disliked_items'] = list(set(preferences['disliked_items']))[:5] # Limit to 5 recent disliked

        return preferences

# Instantiate feedback manager
feedback_manager = FeedbackManager(FEEDBACK_CSV_FILE)

# --- Simulated Translation Functions (PLACEHOLDERS) ---
# In a real application, you would integrate with a service like Google Cloud Translation API.
# Example: https://cloud.google.com/translate/docs/reference/rest/v2/translate
# You would need to install google-cloud-translate library and set up authentication.

def google_translate_text(text, target_language, source_language=None):
    """
    Simulates text translation using a placeholder.
    In a real app, this would call a translation API.
    """
    print(f"SIMULATING TRANSLATION: '{text}' from {source_language or 'auto'} to {target_language}")
    # This is where you'd integrate with Google Cloud Translation API
    # from google.cloud import translate_v2 as translate
    # client = translate.Client()
    # result = client.translate(text, target_language=target_language, source_language=source_language)
    # return result['translatedText']
    return text # For now, just return the original text

def google_detect_language(text):
    """
    Simulates language detection using a placeholder.
    In a real app, this would call a language detection API.
    """
    print(f"SIMULATING LANGUAGE DETECTION for: '{text}'")
    # This is where you'd integrate with Google Cloud Translation API for detection
    # from google.cloud import translate_v2 as translate
    # client = translate.Client()
    # result = client.detect_language(text)
    # return result['language']
    return 'en' # Default to English for placeholder

# --- Routes ---

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    df_users = pd.read_csv(USER_CSV)
    user_data = df_users[df_users['user_id'] == user_id].iloc[0].to_dict()
    
    # Pass preferred_language to the frontend
    preferred_language = user_data.get('preferred_language', 'en-US')
    
    return render_template('index.html', session=session, preferred_language=preferred_language)

@app.route('/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_text = request.form.get('user_text')
    image = request.files.get('food_image')
    target_language = request.form.get('target_language', 'en-US') # Get target language from frontend
    image_path = None

    if image and image.filename:
        filename = f"{uuid.uuid4()}.jpg"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)

    try:
        user_id = session['user_id']
        
      
        # Fetch user preferences
        user_preferences = feedback_manager.analyze_feedback(user_id)
        
        # Fetch full user profile data
        df_users = pd.read_csv(USER_CSV)
        user_profile_data = df_users[df_users['user_id'] == user_id].iloc[0].to_dict()

        # Combine user text, preferences, and profile for a richer prompt
        # The prompt itself is still constructed in English for the Gemini model
        full_prompt_context = f"User Query: {user_text}\n\n"
        full_prompt_context += f"User Profile: Name={user_profile_data.get('name')}, Age={user_profile_data.get('age')}, Gender={user_profile_data.get('gender')}, Diet={user_profile_data.get('diet')}, Goal={user_profile_data.get('goal')}, Height={user_profile_data.get('height_cm')}cm, Weight={user_profile_data.get('weight_kg')}kg, BMI={user_profile_data.get('bmi')}, Medical Conditions={user_profile_data.get('medical_conditions')}.\n"
        
        if user_preferences.get('liked_items'):
            full_prompt_context += f"User previously liked: {', '.join(user_preferences['liked_items'])}.\n"
        if user_preferences.get('disliked_items'):
            full_prompt_context += f"User previously disliked: {', '.join(user_preferences['disliked_items'])}. Please avoid recommending similar items.\n"

        # Pass the combined context to ask_gemini
        # Gemini will receive this English prompt
        bot_response_content_english = ask_gemini(user_text=full_prompt_context, image_path=image_path)
        
        # --- Translate Bot Response to Target Language ---
        bot_response_content = google_translate_text(bot_response_content_english, target_language)

        message_id = str(uuid.uuid4())
        recent_bot_responses[message_id] = bot_response_content # Store the translated content

        return jsonify({
            'response': bot_response_content,
            'message_id': message_id
        })
    except Exception as e:
        print(f"❌ Error in /chat: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

@app.route('/feedback', methods=['POST'])
def handle_feedback():
    data = request.get_json()
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    message_id = data.get('message_id')
    feedback_type = data.get('feedback')  # 'like' or 'dislike'
    bot_response_content = recent_bot_responses.get(message_id, "Content not found")

    if feedback_manager.store_feedback(user_id, message_id, feedback_type, bot_response_content):
        recent_bot_responses.pop(message_id, None)
        return jsonify({'status': 'success', 'message': 'Feedback stored.'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to store feedback'}), 500

@app.route('/api/user/preferences', methods=['GET'])
def get_user_preferences():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    df_users = pd.read_csv(USER_CSV)
    user_data = df_users[df_users['user_id'] == user_id].iloc[0].to_dict()
    
    preferences = feedback_manager.analyze_feedback(user_id)
    preferences['preferred_language'] = user_data.get('preferred_language', 'en-US') # Add language to preferences
    
    return jsonify({'status': 'success', 'preferences': preferences})

@app.route('/api/update_user_language_preference', methods=['POST'])
def update_user_language_preference():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401
    
    data = request.get_json()
    new_language = data.get('language')

    if not new_language:
        return jsonify({'status': 'error', 'message': 'No language provided'}), 400

    try:
        df_users = pd.read_csv(USER_CSV)
        if 'preferred_language' not in df_users.columns:
            df_users['preferred_language'] = 'en-US' # Add column if it doesn't exist
        
        df_users.loc[df_users['user_id'] == user_id, 'preferred_language'] = new_language
        df_users.to_csv(USER_CSV, index=False)
        return jsonify({'status': 'success', 'message': 'Language preference updated.'})
    except Exception as e:
        print(f"Error updating user language preference: {e}")
        return jsonify({'status': 'error', 'message': f'Failed to update language preference: {e}'}), 500


# --- Run the App ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

