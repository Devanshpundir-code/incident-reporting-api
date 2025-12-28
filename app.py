from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, session
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
import math

# ========================
# FLASK APP CONFIGURATION
# ========================
app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = 'emergency-app-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ========================
# DATABASE INITIALIZATION
# ========================
def init_db():
    """Builds the entire MySQL schema inside SQLite for Render compatibility"""
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100), phone VARCHAR(15), 
            email VARCHAR(100), role TEXT DEFAULT 'user', latitude DECIMAL(9,6), 
            longitude DECIMAL(9,6), siren_opt_in BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, type VARCHAR(50), description TEXT, 
            latitude DECIMAL(9,6), longitude DECIMAL(9,6), severity_color TEXT DEFAULT 'green', 
            ai_suggested_severity TEXT, status TEXT DEFAULT 'unverified', created_by INT, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP NULL,
            responder_priority TEXT DEFAULT NULL, claimed_by INT DEFAULT NULL, 
            claimed_at DATETIME DEFAULT NULL, responder_note TEXT NULL, responder_eta VARCHAR(50),
            FOREIGN KEY (created_by) REFERENCES users(id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS incident_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id INT, reporter_id INT, 
            description TEXT, media_path VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id), FOREIGN KEY (reporter_id) REFERENCES users(id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id INT, user_id INT, 
            response TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id), FOREIGN KEY (user_id) REFERENCES users(id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS responders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100), 
            role TEXT, proof_path VARCHAR(255), status TEXT DEFAULT 'pending', 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS incident_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id INT NOT NULL, 
            sender_type TEXT NOT NULL, sender_id INT NULL, message TEXT NOT NULL, 
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        # Demo User seeding
        cursor.execute("SELECT id FROM users WHERE id = 1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Demo User')")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

# ========================
# DATABASE CONNECTION
# ========================
def get_db_connection():
    """SQLite connection used by all routes to replace MySQL"""
    conn = sqlite3.connect('database.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

# ========================
# HELPER FUNCTIONS
# ========================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula for distance"""
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def ai_suggest_severity(description, incident_type):
    """Rule-based AI for severity detection"""
    d = description.lower()
    if any(k in d for k in ['fire', 'gun', 'explosion', 'bleeding', 'unconscious']): return 'critical'
    if any(k in d for k in ['accident', 'crash', 'broken bone', 'robbery']): return 'serious'
    return {'medical': 'serious', 'fire': 'critical', 'crime': 'serious'}.get(incident_type, 'minor')

def get_severity_color(severity):
    return {'critical': 'red', 'serious': 'orange', 'medium': 'yellow', 'minor': 'green'}.get(severity, 'green')

def get_time_ago(ts):
    if not ts: return "Just now"
    if isinstance(ts, str): ts = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
    diff = datetime.now() - ts
    if diff.days > 0: return f"{diff.days}d ago"
    if diff.seconds > 3600: return f"{diff.seconds // 3600}h ago"
    return f"{diff.seconds // 60}m ago"

# ========================
# USER ROUTES
# ========================

@app.route("/")
def index(): return render_template("index.html")

@app.route('/report', methods=['POST'])
def report_incident():
    try:
        i_type, desc = request.form.get('type'), request.form.get('description')
        lat, lon = float(request.form.get('latitude')), float(request.form.get('longitude'))
        media = save_uploaded_file(request.files.get('media'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check duplicate (within 15 mins)
        cursor.execute("SELECT id, latitude, longitude FROM incidents WHERE type = ? AND status NOT IN ('resolved', 'false') AND created_at >= datetime('now', '-15 minutes')", (i_type,))
        dupes = cursor.fetchall()
        dup_id = next((d['id'] for d in dupes if calculate_distance(lat, lon, d['latitude'], d['longitude']) <= 200), None)
        
        if dup_id:
            cursor.execute("INSERT INTO incident_reports (incident_id, reporter_id, description, media_path) VALUES (?, 1, ?, ?)", (dup_id, desc, media))
            res_id = dup_id
        else:
            ai_sev = ai_suggest_severity(desc, i_type)
            cursor.execute("INSERT INTO incidents (type, description, latitude, longitude, severity_color, ai_suggested_severity, status, created_by) VALUES (?, ?, ?, ?, ?, ?, 'unverified', 1)", (i_type, desc, lat, lon, get_severity_color(ai_sev), ai_sev))
            res_id = cursor.lastrowid
            cursor.execute("INSERT INTO incident_reports (incident_id, reporter_id, description, media_path) VALUES (?, 1, ?, ?)", (res_id, desc, media))
        
        conn.commit()
        return jsonify({'success': True, 'incident_id': res_id}), 201
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/incidents/nearby')
def nearby():
    lat, lng = float(request.args.get('lat', 0)), float(request.args.get('lng', 0))
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM incidents WHERE status != 'resolved'").fetchall()
    return jsonify({'incidents': [dict(r) for r in rows if calculate_distance(lat, lng, r['latitude'], r['longitude']) <= 500]})

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    conn = get_db_connection()
    conn.execute("INSERT INTO verifications (incident_id, user_id, response) VALUES (?, 1, ?)", (data['incident_id'], data['response']))
    conn.commit()
    return jsonify({'success': True})

@app.route('/incident/<int:id>/user-status')
def u_status(id):
    conn = get_db_connection()
    row = conn.execute("SELECT i.status, r.name FROM incidents i LEFT JOIN responders r ON i.claimed_by = r.id WHERE i.id = ?", (id,)).fetchone()
    return jsonify({"status": row[0], "responder": row[1]}) if row else jsonify({'error': '404'}), 404

# ========================
# RESPONDER ROUTES
# ========================

@app.route('/responder/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET': return render_template('responder_register.html')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO responders (name, role, status) VALUES (?, ?, 'approved')", (request.form['name'], request.form['role']))
    conn.commit()
    session['responder_id'], session['responder_role'] = cursor.lastrowid, request.form['role']
    return jsonify({'success': True})

@app.route('/responder/incidents')
def resp_incs():
    if not session.get('responder_id'): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM incidents WHERE status != 'resolved'").fetchall()
    return jsonify({'incidents': [dict(r) for r in rows]})

@app.route('/incident/<int:id>/claim', methods=['POST'])
def claim(id):
    conn = get_db_connection()
    conn.execute("UPDATE incidents SET claimed_by = ?, claimed_at = datetime('now') WHERE id = ?", (session.get('responder_id'), id))
    conn.commit()
    return jsonify({'success': True})

@app.route('/incident/<int:id>/status', methods=['POST'])
def set_status(id):
    conn = get_db_connection()
    conn.execute("UPDATE incidents SET status = ? WHERE id = ?", (request.json['status'], id))
    conn.commit()
    return jsonify({'success': True})

@app.route('/incident/<int:id>/priority', methods=['POST'])
def set_prio(id):
    conn = get_db_connection()
    conn.execute("UPDATE incidents SET responder_priority = ? WHERE id = ?", (request.json['priority'], id))
    conn.commit()
    return jsonify({'success': True})

@app.route('/incident/<int:id>/note', methods=['POST'])
def note(id):
    conn = get_db_connection()
    conn.execute("INSERT INTO incident_notes (incident_id, sender_type, sender_id, message) VALUES (?, 'responder', ?, ?)", 
                 (id, session['responder_id'], request.json['message']))
    conn.commit()
    return jsonify({'success': True})

@app.route('/uploads/<filename>')
def uploads(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========================
# AUTO-START DATABASE
# ========================
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)