def is_food_related(text):
    keywords = ["nutrition", "vitamin", "calories", "food", "fruit", "meal", "protein", "diet", "carbs", "sugar"]
    return any(word in text.lower() for word in keywords)
