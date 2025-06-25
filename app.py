from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv
import mysql.connector
import os
import pickle
import time
import re
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'tagwizard_secret'

# Database connection
print("\n=== Starting Application ===\n")
print("Initializing database connection...")
try:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "password"),
        database=os.getenv("DB_NAME", "tagwizard")
    )
    cursor = conn.cursor(dictionary=True)
    
    # Verify users table exists
    cursor.execute("SHOW TABLES LIKE 'users'")
    if not cursor.fetchone():
        print("⚠ Database table 'users' does not exist")
        # Create users table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        """)
        conn.commit()
        print("✓ Created users table")
    print("✓ Database connection verified")
except Exception as e:
    print(f"⚠ Database connection failed: {str(e)}")
    print("⚠ Authentication functionality will be disabled")
    conn = None
    cursor = None

# Load models
model = None
tokenizer = None
multilabel = None

def load_models():
    global model, tokenizer, multilabel
    try:
        model_id = "distilbert-finetuned-stackexchange-multi-label"
        print(f"Loading model from: {model_id}")
        model = AutoModelForSequenceClassification.from_pretrained(model_id)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        
        print("Loading multi-label binarizer...")
        with open("multi-label-binarizer.pkl", "rb") as f:
            multilabel = pickle.load(f)

        print("All models loaded successfully.")
    except Exception as e:
        print(f"Error loading models: {str(e)}")
        raise

# Initial load
try:
    load_models()
    print("✓ Models loaded successfully")
except Exception as e:
    print(f"⚠ Model loading failed: {str(e)}")
    print("⚠ Tag prediction functionality will be disabled")
    model = None
    tokenizer = None
    multilabel = None

print("\n=== Application Ready ===\n")

@app.route('/get_tags', methods=['POST'])
def get_tags():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        if model is None or tokenizer is None:
            raise Exception("Model not loaded - check server startup logs")

        data = request.get_json(force=True)
        question = data.get('question', '').strip()
        print(f"Received question: {question}")

        if not question:
            return jsonify({'error': 'No question provided'}), 400

        print("Tokenizing input...")
        inputs = tokenizer(question, return_tensors="pt", padding=True, truncation=True)
        
        print("Running model prediction...")
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probs = torch.sigmoid(logits)
            print(f"Raw probabilities: {probs}")

            # Get top 5 indices with highest probabilities
            top_indices = torch.topk(probs, 5, dim=1).indices[0].tolist()
            print(f"Top indices: {top_indices}")

            # Map indices to tag names
            predicted_tags = [multilabel.classes_[i] for i in top_indices]
            print(f"Predicted tags: {predicted_tags}")

        return jsonify({
            'tags': predicted_tags,
            'model': 'distilbert-finetuned-stackexchange-multi-label',
            'status': 'success'
        })

    except Exception as e:
        error_msg = f"Error in /get_tags: {str(e)}"
        print(error_msg)
        return jsonify({
            'error': error_msg,
            'model_status': 'loaded' if model else 'not loaded',
            'tokenizer_status': 'loaded' if tokenizer else 'not loaded'
        }), 500


@app.route('/authenticate', methods=['POST'])
def authenticate():
    email = request.form['email']
    password = request.form['password']
    cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
    user = cursor.fetchone()
    if user:
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        return redirect(url_for('dashboard'))
    return render_template('login.html', error='Invalid email or password')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirm_password']
    
    if password != confirm_password:
        return render_template('signup.html', error='Passwords do not match')
        
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        return render_template('signup.html', error='Email already registered')
        
    cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", 
                  (name, email, password))
    conn.commit()
    return redirect(url_for('login'))

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', name=session['user_name'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
