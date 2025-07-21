#!/usr/bin/env python3
"""
A simple Flask web application for managing user accounts and tasks.
This application contains several intentional bugs for demonstration purposes.
"""

import sqlite3
import hashlib
import time
import secrets
from flask import Flask, request, jsonify, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Bug #1: Hardcoded database path and no proper connection management
DATABASE = 'users.db'

def get_db_connection():
    """Get database connection - with performance issue"""
    # Bug #2: Opening new connection every time without connection pooling
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with tables"""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT FALSE,
            priority INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def home():
    """Home page with basic user interface"""
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Task Manager</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .form-group { margin: 15px 0; }
            input[type="text"], input[type="email"], input[type="password"] { 
                width: 300px; padding: 8px; 
            }
            button { padding: 10px 20px; background: #007cba; color: white; border: none; }
            .task { border: 1px solid #ddd; padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>Task Manager</h1>
        
        <h2>Register User</h2>
        <form action="/register" method="post">
            <div class="form-group">
                <input type="text" name="username" placeholder="Username" required>
            </div>
            <div class="form-group">
                <input type="email" name="email" placeholder="Email" required>
            </div>
            <div class="form-group">
                <input type="password" name="password" placeholder="Password" required>
            </div>
            <button type="submit">Register</button>
        </form>
        
        <h2>Login</h2>
        <form action="/login" method="post">
            <div class="form-group">
                <input type="text" name="username" placeholder="Username" required>
            </div>
            <div class="form-group">
                <input type="password" name="password" placeholder="Password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        
        <h2>Search Users</h2>
        <form action="/search" method="get">
            <div class="form-group">
                <input type="text" name="query" placeholder="Search username">
            </div>
            <button type="submit">Search</button>
        </form>
    </body>
    </html>
    '''
    return render_template_string(html_template)

@app.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not username or not email or not password:
        return jsonify({'error': 'All fields are required'}), 400
    
    # Fixed: Use secure password hashing with salt
    password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        conn.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 400
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    """Login user"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ?',
        (username,)
    ).fetchone()
    conn.close()
    
    # Fixed: Use secure password verification
    if user and check_password_hash(user['password_hash'], password):
        return jsonify({'message': f'Welcome back, {user["username"]}!', 'user_id': user['id']})
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/search')
def search_users():
    """Search users by username - Fixed SQL injection vulnerability"""
    query = request.args.get('query', '')
    
    if not query:
        return jsonify({'users': []})
    
    # Input validation and sanitization
    if len(query) > 100:  # Prevent extremely long queries
        return jsonify({'error': 'Query too long'}), 400
    
    conn = get_db_connection()
    
    # Fixed: Use parameterized queries to prevent SQL injection
    try:
        cursor = conn.execute(
            "SELECT id, username, email FROM users WHERE username LIKE ?", 
            (f'%{query}%',)
        )
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'users': users})
    except Exception as e:
        conn.close()
        return jsonify({'error': 'Search failed'}), 500

@app.route('/users/<int:user_id>/tasks')
def get_user_tasks(user_id):
    """Get tasks for a specific user"""
    conn = get_db_connection()
    
    # Bug #2: Inefficient query - no indexes and potentially slow
    # This could be slow with many tasks
    tasks = conn.execute('''
        SELECT t.*, u.username 
        FROM tasks t 
        JOIN users u ON t.user_id = u.id 
        WHERE t.user_id = ?
        ORDER BY t.priority DESC, t.created_at DESC
    ''', (user_id,)).fetchall()
    
    # Fixed: Efficient processing without unnecessary delays
    processed_tasks = []
    for task in tasks:
        task_dict = dict(task)
        # Fixed: Correct priority level assignment
        if task_dict['priority'] > 5:
            task_dict['priority_level'] = 'High'     # High numbers = High priority
        elif task_dict['priority'] > 2:
            task_dict['priority_level'] = 'Medium'
        else:
            task_dict['priority_level'] = 'Low'      # Low numbers = Low priority
            
        processed_tasks.append(task_dict)
    
    conn.close()
    return jsonify({'tasks': processed_tasks})

@app.route('/users/<int:user_id>/tasks', methods=['POST'])
def create_task(user_id):
    """Create a new task for user"""
    title = request.json.get('title')
    description = request.json.get('description', '')
    priority = request.json.get('priority', 1)
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    # Fixed: Add input validation for priority
    try:
        priority = int(priority)
        if priority < 1 or priority > 10:
            return jsonify({'error': 'Priority must be between 1 and 10'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Priority must be a valid integer'}), 400
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO tasks (user_id, title, description, priority) VALUES (?, ?, ?, ?)',
        (user_id, title, description, priority)
    )
    conn.commit()
    task_id = conn.lastrowid
    conn.close()
    
    return jsonify({'message': 'Task created', 'task_id': task_id}), 201

if __name__ == '__main__':
    init_db()
    # Bug #6: Running in debug mode in production (security risk)
    app.run(debug=True, host='0.0.0.0', port=5000)