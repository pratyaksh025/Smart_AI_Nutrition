from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
import bcrypt # For password hashing
import smtplib # For sending emails
import ssl # For secure email connection
from email.message import EmailMessage # For creating email messages
import random # For OTP generation
import time # For OTP expiry
from datetime import datetime, timedelta # For OTP expiry
from config import EMAIL_ADDRESS, EMAIL_PASSWORD # Import email credentials
import uuid # Import the uuid module

auth_blueprint = Blueprint("auth", __name__, template_folder="../templates")
USER_CSV = "data/users.csv"
OTP_STORAGE = {} # In-memory storage for OTPs: {email: {otp: "...", expiry: datetime}}

# Define the expected columns for the users.csv file
# Added 'height_cm', 'weight_kg', 'bmi', 'medical_conditions', and 'preferred_language'
EXPECTED_COLUMNS = ["user_id", "name", "email", "hashed_password", "age", "gender", "diet", "goal", 
                    "height_cm", "weight_kg", "bmi", "medical_conditions", "preferred_language"]

# Ensure CSV file exists and has the correct columns
if not os.path.exists(USER_CSV):
    # If the file does not exist, create it with the expected columns
    df = pd.DataFrame(columns=EXPECTED_COLUMNS)
    df.to_csv(USER_CSV, index=False)
else:
    # If the file exists, read it and check its columns
    df = pd.read_csv(USER_CSV)
    
    # Check if the existing columns match the expected columns
    # Convert to sets for order-independent comparison
    if set(df.columns) != set(EXPECTED_COLUMNS) or len(df.columns) != len(EXPECTED_COLUMNS):
        print(f"⚠️ Warning: {USER_CSV} has unexpected columns. Recreating with correct schema.")
        # Recreate the DataFrame with the correct columns and copy existing data if possible
        new_df = pd.DataFrame(columns=EXPECTED_COLUMNS)
        for col in EXPECTED_COLUMNS:
            if col in df.columns:
                new_df[col] = df[col]
            else:
                new_df[col] = None # Add missing columns as None
        new_df.to_csv(USER_CSV, index=False)
        df = new_df # Update df to the new DataFrame
    else:
        # Ensure all new columns exist for older CSVs
        for col in ["height_cm", "weight_kg", "bmi", "medical_conditions", "preferred_language"]:
            if col not in df.columns:
                df[col] = None
        df.to_csv(USER_CSV, index=False)


def send_email(receiver_email, subject, body):
    """Sends an email using Gmail SMTP."""
    em = EmailMessage()
    em['From'] = EMAIL_ADDRESS
    em['To'] = receiver_email
    em['Subject'] = subject
    em.set_content(body)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(em)
        return True
    except Exception as e:
        print(f"❌ Error sending email to {receiver_email}: {e}")
        flash(f"❌ Failed to send email: {e}", "danger")
        return False

def generate_otp():
    """Generates a 6-digit OTP."""
    return str(random.randint(100000, 999999))

def calculate_bmi(weight_kg, height_cm):
    """Calculates BMI given weight in kg and height in cm."""
    if height_cm is None or height_cm <= 0:
        return None
    height_m = height_cm / 100
    bmi_val = weight_kg / (height_m ** 2)
    return round(bmi_val, 2)

@auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        df = pd.read_csv(USER_CSV)
        user = df[df['email'] == email]

        if not user.empty:
            stored_hashed_password = user.iloc[0]['hashed_password']
            if stored_hashed_password and bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password.encode('utf-8')):
                session['user_id'] = user.iloc[0]['user_id']
                session['name'] = user.iloc[0]['name']
                flash("Login successful!", "success")
                return redirect(url_for('home'))
            else:
                flash("❌ Invalid email or password.", "danger")
                return render_template("login.html", error=True)
        else:
            flash("❌ Invalid email or password.", "danger")
            return render_template("login.html", error=True)

    return render_template("login.html", error=False)

@auth_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        # Read the CSV again to ensure the latest schema is used, especially after recreation
        df = pd.read_csv(USER_CSV) 

        email = data['email'].strip()
        password = data['password'].strip()
        otp_input = data.get('otp_input') # OTP entered by user
        action = data.get('action') # 'send_otp' or 'register'

        if email in df['email'].values:
            flash("⚠️ Email already registered!", "warning")
            return render_template("register.html") # Stay on register page

        if action == 'send_otp':
            otp = generate_otp()
            expiry_time = datetime.now() + timedelta(minutes=5) # OTP valid for 5 minutes
            OTP_STORAGE[email] = {'otp': otp, 'expiry': expiry_time}

            subject = "Nutrition Assistant: Your Registration OTP"
            body = f"Your One-Time Password (OTP) for Nutrition Assistant registration is: {otp}\n\nThis OTP is valid for 5 minutes."
            
            if send_email(email, subject, body):
                flash("✅ OTP sent to your email. Please check your inbox and spam folder.", "success")
                return render_template("register.html", email_sent=True, user_email=email, form_data=data)
            else:
                flash("❌ Failed to send OTP. Please try again.", "danger")
                return render_template("register.html", form_data=data)

        elif action == 'register':
            stored_otp_info = OTP_STORAGE.get(email)

            if not stored_otp_info or stored_otp_info['otp'] != otp_input or datetime.now() > stored_otp_info['expiry']:
                flash("❌ Invalid or expired OTP. Please request a new one.", "danger")
                return render_template("register.html", email_sent=True, user_email=email, form_data=data)
            
            # OTP is valid, proceed with registration
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            user_id = f"user_{len(df)+1}"
            
            # Get height and weight, calculate BMI
            height_cm = float(data['height_cm']) if data.get('height_cm') else None
            weight_kg = float(data['weight_kg']) if data.get('weight_kg') else None
            bmi = calculate_bmi(weight_kg, height_cm) if height_cm is not None and weight_kg is not None else None
            medical_conditions = data.get('medical_conditions', 'None') # Get medical conditions
            preferred_language = data.get('preferred_language', 'en-US') # Get preferred language

            new_row = pd.DataFrame([[user_id, data['name'], email, hashed_password,
                                     data['age'], data['gender'], data['diet'], data['goal'],
                                     height_cm, weight_kg, bmi, medical_conditions, preferred_language]],
                                   columns=EXPECTED_COLUMNS) # Use EXPECTED_COLUMNS here

            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(USER_CSV, index=False)
            
            # Clear OTP from storage after successful registration
            OTP_STORAGE.pop(email, None)

            flash("✅ Registered successfully! You can now log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("register.html", email_sent=False)

@auth_blueprint.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

@auth_blueprint.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()
        action = request.form.get('action') # 'send_otp' or 'verify_otp' or 'reset_password'

        df = pd.read_csv(USER_CSV)
        user = df[df['email'] == email]

        if user.empty:
            flash("❌ Email not found.", "danger")
            return render_template("forgot_password.html")

        if action == 'send_otp':
            otp = generate_otp()
            expiry_time = datetime.now() + timedelta(minutes=5)
            OTP_STORAGE[email] = {'otp': otp, 'expiry': expiry_time, 'reset_token': str(uuid.uuid4())} # Add reset token

            subject = "Nutrition Assistant: Password Reset OTP"
            body = f"Your One-Time Password (OTP) for password reset is: {otp}\n\nThis OTP is valid for 5 minutes."
            
            if send_email(email, subject, body):
                flash("✅ OTP sent to your email. Please check your inbox and spam folder.", "success")
                return render_template("forgot_password.html", email_sent=True, user_email=email)
            else:
                flash("❌ Failed to send OTP. Please try again.", "danger")
                return render_template("forgot_password.html")

        elif action == 'verify_otp':
            otp_input = request.form['otp_input'].strip()
            stored_otp_info = OTP_STORAGE.get(email)

            if not stored_otp_info or stored_otp_info['otp'] != otp_input or datetime.now() > stored_otp_info['expiry']:
                flash("❌ Invalid or expired OTP. Please try again.", "danger")
                return render_template("forgot_password.html", email_sent=True, user_email=email)
            
            # OTP valid, allow password reset
            flash("✅ OTP verified. You can now reset your password.", "success")
            return render_template("forgot_password.html", otp_verified=True, user_email=email, reset_token=stored_otp_info['reset_token'])
        
        elif action == 'reset_password':
            new_password = request.form['new_password'].strip()
            reset_token = request.form['reset_token'].strip()
            stored_otp_info = OTP_STORAGE.get(email)

            if not stored_otp_info or stored_otp_info['reset_token'] != reset_token:
                flash("❌ Invalid reset token. Please restart the forgot password process.", "danger")
                return render_template("forgot_password.html")

            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Update password in CSV
            df.loc[df['email'] == email, 'hashed_password'] = hashed_password
            df.to_csv(USER_CSV, index=False)
            
            # Clear OTP and reset token from storage
            OTP_STORAGE.pop(email, None)

            flash("✅ Your password has been reset successfully. You can now log in.", "success")
            return redirect(url_for('auth.login'))

    return render_template("forgot_password.html")

@auth_blueprint.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        flash("Please log in to edit your profile.", "warning")
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    df = pd.read_csv(USER_CSV)
    user_data = df[df['user_id'] == user_id].iloc[0].to_dict()

    if request.method == 'POST':
        # Update user data from form
        user_data['name'] = request.form['name'].strip()
        user_data['age'] = int(request.form['age'])
        user_data['gender'] = request.form['gender']
        user_data['diet'] = request.form['diet']
        user_data['goal'] = request.form['goal']
        
        # Update height, weight, medical conditions, and recalculate BMI
        user_data['height_cm'] = float(request.form['height_cm']) if request.form.get('height_cm') else None
        user_data['weight_kg'] = float(request.form['weight_kg']) if request.form.get('weight_kg') else None
        user_data['medical_conditions'] = request.form.get('medical_conditions', 'None')
        user_data['preferred_language'] = request.form.get('preferred_language', 'en-US') # Update preferred language

        user_data['bmi'] = calculate_bmi(user_data['weight_kg'], user_data['height_cm']) if user_data['height_cm'] is not None and user_data['weight_kg'] is not None else None

        # Update the DataFrame
        for col in EXPECTED_COLUMNS: # Use EXPECTED_COLUMNS to iterate through all fields
            if col in user_data: # Ensure the key exists in user_data
                df.loc[df['user_id'] == user_id, col] = user_data[col]
        
        df.to_csv(USER_CSV, index=False)
        session['name'] = user_data['name'] # Update session name if changed

        flash("✅ Profile updated successfully!", "success")
        return redirect(url_for('home')) # Redirect to home or back to profile page

    return render_template('edit_profile.html', user=user_data)
