from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

# PostgreSQL connection
conn = psycopg2.connect(
    dbname="tagwizard",
    user="postgres",
    password="password",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

@app.route('/api/login', methods=['POST'])
def login_or_register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        if user[2] == password:
            return jsonify({'success': True, 'message': 'Login successful'}), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid password'}), 401
    else:
        cursor.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, password))
        conn.commit()
        return jsonify({'success': True, 'message': 'Account created'}), 201

if __name__ == '__main__':
    app.run(debug=True)
