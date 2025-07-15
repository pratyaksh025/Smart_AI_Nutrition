# feedback_manager.py
import csv
import os
from datetime import datetime
from flask import jsonify, session

class FeedbackManager:
    def __init__(self, feedback_dir='feedback_data'):
        self.FEEDBACK_DIR = feedback_dir
        if not os.path.exists(self.FEEDBACK_DIR):
            os.makedirs(self.FEEDBACK_DIR)

    def get_feedback_filename(self, user_id):
        """Generate filename for user's feedback CSV"""
        return os.path.join(self.FEEDBACK_DIR, f'user_{user_id}_feedback.csv')

    def ensure_feedback_file(self, user_id):
        """Create CSV file with headers if it doesn't exist"""
        filename = self.get_feedback_filename(user_id)
        if not os.path.exists(filename):
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['timestamp', 'message_id', 'message_content', 'feedback_type'])

    def store_feedback(self, user_id, message_id, feedback_type, message_content=''):
        """Store feedback in user's CSV file"""
        try:
            self.ensure_feedback_file(user_id)
            filename = self.get_feedback_filename(user_id)
            
            with open(filename, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    datetime.now().isoformat(),
                    message_id,
                    message_content[:500],  # Limit content length
                    feedback_type
                ])
            return True
        except Exception as e:
            print(f"Error storing feedback: {e}")
            return False

    def get_user_feedback(self, user_id):
        """Read all feedback for a user"""
        filename = self.get_feedback_filename(user_id)
        if not os.path.exists(filename):
            return []
        
        feedback = []
        with open(filename, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                feedback.append(dict(row))
        return feedback

    def analyze_feedback(self, user_id):
        """Analyze feedback to determine user preferences"""
        feedback = self.get_user_feedback(user_id)
        if not feedback:
            return {}
        
        analysis = {
            'total_likes': 0,
            'total_dislikes': 0,
            'liked_items': [],
            'disliked_items': [],
            'preferred_keywords': [],
            'avoided_keywords': []
        }
        
        # Simple analysis - can be enhanced
        for item in feedback:
            if item['feedback_type'] == 'like':
                analysis['total_likes'] += 1
                analysis['liked_items'].append(item['message_content'])
            else:
                analysis['total_dislikes'] += 1
                analysis['disliked_items'].append(item['message_content'])
        
        # Add basic keyword analysis (very simple implementation)
        all_liked = ' '.join(analysis['liked_items']).lower()
        all_disliked = ' '.join(analysis['disliked_items']).lower()
        
        # Example keyword checks - expand based on your needs
        for keyword in ['protein', 'carbs', 'vegetarian', 'vegan', 'low-calorie']:
            if keyword in all_liked:
                analysis['preferred_keywords'].append(keyword)
            if keyword in all_disliked:
                analysis['avoided_keywords'].append(keyword)
        
        return analysis