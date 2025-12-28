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

# Configuration
app.config['SECRET_KEY'] = 'emergency-app-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ========================
# DATABASE INITIALIZATION (SQLite)
# ========================
def init_db():
    """Initialize SQLite database with your exact schema and modifications"""
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # 1. USERS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100),
                phone VARCHAR(15),
                email VARCHAR(100),
                role TEXT CHECK(role IN ('user','responder')) DEFAULT 'user',
                latitude DECIMAL(9,6),
                longitude DECIMAL(9,6),
                siren_opt_in BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. INCIDENTS (Including all your ALTER modifications)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type VARCHAR(50),
                description TEXT,
                latitude DECIMAL(9,6),
                longitude DECIMAL(9,6),
                severity_color TEXT DEFAULT 'green',
                ai_suggested_severity TEXT,
                status TEXT DEFAULT 'unverified',
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP NULL,
                responder_priority TEXT DEFAULT NULL,
                claimed_by INTEGER DEFAULT NULL,
                claimed_at DATETIME DEFAULT NULL,
                responder_note TEXT NULL,
                responder_eta VARCHAR(50),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')

        # 3. INCIDENT REPORTS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incident_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER,
                reporter_id INTEGER,
                description TEXT,
                media_path VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (incident_id) REFERENCES incidents(id),
                FOREIGN KEY (reporter_id) REFERENCES users(id)
            )
        ''')

        # 4. VERIFICATIONS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER,
                user_id INTEGER,
                response TEXT CHECK(response IN ('yes','no','not_sure')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (incident_id) REFERENCES incidents(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # 5. RESPONDERS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS responders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100),
                role TEXT CHECK(role IN ('medical','police','fire','traffic','disaster')),
                proof_path VARCHAR(255),
                status TEXT CHECK(status IN ('pending','approved','rejected')) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 6. INCIDENT NOTES
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incident_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                sender_type TEXT CHECK(sender_type IN ('responder', 'ai')) NOT NULL,
                sender_id INTEGER NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Insert Demo User if doesn't exist
        cursor.execute("SELECT id FROM users WHERE id = 1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Demo User')")

        conn.commit()
        conn.close()
        print("Database Initialized with full schema.")
    except Exception as e:
        print(f"Database Init Error: {e}")

# ========================
# HELPER FUNCTIONS
# ========================
def get_db_connection():
    """Create and return SQLite connection with dict-like access"""
    conn = sqlite3.connect('database.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat, delta_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def ai_suggest_severity(description, incident_type):
    d_l = description.lower()
    crit = ['fire', 'explosion', 'gun', 'shot', 'stab', 'bleeding', 'unconscious', 'not breathing', 'heart attack', 'stroke', 'trapped', 'gas leak']
    seri = ['accident', 'crash', 'hit', 'broken bone', 'severe pain', 'fall', 'assault', 'fight', 'robbery']
    medi = ['minor', 'small', 'injury', 'pain', 'argument', 'disturbance', 'suspicious']
    
    for k in crit: 
        if k in d_l: return 'critical'
    for k in seri: 
        if k in d_l: return 'serious'
    for k in medi: 
        if k in d_l: return 'medium'
    
    defaults = {'medical': 'serious', 'fire': 'critical', 'crime': 'serious', 'accident': 'medium', 'other': 'minor'}
    return defaults.get(incident_type, 'minor')

def get_severity_color(severity):
    return {'critical': 'red', 'serious': 'orange', 'medium': 'yellow', 'minor': 'green'}.get(severity, 'yellow')

def get_time_ago(ts):
    if not ts: return "Just now"
    now = datetime.now()
    if isinstance(ts, str):
        try: ts = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
        except: return "Just now"
    diff = now - ts
    if diff.days > 365: return f"{diff.days // 365} years ago"
    if diff.days > 30: return f"{diff.days // 30} months ago"
    if diff.days > 0: return f"{diff.days} days ago"
    if diff.seconds > 3600: return f"{diff.seconds // 3600} hours ago"
    if diff.seconds > 60: return f"{diff.seconds // 60} minutes ago"
    return "Just now"

# ========================
# ROUTES
# ========================

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/responder')
def responder():
    if not session.get('responder_id'): return redirect('/responder/register')
    return render_template('responder.html')

@app.route('/report', methods=['POST'])
def report_incident():
    try:
        i_type, desc = request.form.get('type'), request.form.get('description')
        lat, lon = float(request.form.get('latitude')), float(request.form.get('longitude'))
        u_id = request.form.get('user_id', 1)
        
        if not all([i_type, desc, lat, lon]): return jsonify({'error': 'Missing fields'}), 400
        
        media_path = None
        if 'media' in request.files:
            file = request.files['media']
            if file.filename != '': media_path = save_uploaded_file(file)
        
        ai_sev = ai_suggest_severity(desc, i_type)
        sev_col = get_severity_color(ai_sev)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # SQLite duplicate check (within 15 mins)
        cursor.execute("""
            SELECT id, latitude, longitude FROM incidents 
            WHERE type = ? AND status NOT IN ('resolved', 'false') 
            AND created_at >= datetime('now', '-15 minutes')
        """, (i_type,))
        incidents = cursor.fetchall()
        dup_id = None
        for i in incidents:
            if calculate_distance(lat, lon, i['latitude'], i['longitude']) <= 200:
                dup_id = i['id']
                break
        
        if dup_id:
            incident_id = dup_id
            cursor.execute("INSERT INTO incident_reports (incident_id, reporter_id, description, media_path, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", (incident_id, u_id, desc, media_path))
            cursor.execute("SELECT ai_suggested_severity FROM incidents WHERE id = ?", (incident_id,))
            row = cursor.fetchone()
            existing_sev = row['ai_suggested_severity'] if row else 'minor'
            s_map = {'minor': 0, 'medium': 1, 'serious': 2, 'critical': 3}
            if s_map.get(ai_sev, 0) > s_map.get(existing_sev, 0):
                cursor.execute("UPDATE incidents SET ai_suggested_severity = ?, severity_color = ? WHERE id = ?", (ai_sev, sev_col, incident_id))
        else:
            cursor.execute("INSERT INTO incidents (type, description, latitude, longitude, severity_color, ai_suggested_severity, status, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, 'unverified', ?, CURRENT_TIMESTAMP)", (i_type, desc, lat, lon, sev_col, ai_sev, u_id))
            incident_id = cursor.lastrowid
            session['last_reported_incident'] = incident_id
            cursor.execute("INSERT INTO incident_reports (incident_id, reporter_id, description, media_path, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", (incident_id, u_id, desc, media_path))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'incident_id': incident_id, 'status': 'unverified'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/incidents/nearby', methods=['GET'])
def get_nearby_incidents():
    try:
        lat, lng = float(request.args.get('lat', 0)), float(request.args.get('lng', 0))
        rad = float(request.args.get('radius', 500))
        if lat == 0 and lng == 0: return jsonify({'error': 'Location required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, type, description, latitude, longitude, severity_color, ai_suggested_severity, status, created_at FROM incidents WHERE status NOT IN ('resolved', 'false') ORDER BY created_at DESC")
        incidents = cursor.fetchall()
        nearby = []
        for i in incidents:
            dist = calculate_distance(lat, lng, i['latitude'], i['longitude'])
            if dist <= rad:
                row = dict(i)
                row['distance_str'] = f"{round(dist)}m"
                row['type'] = row['type'].title()
                row['severity'] = row['ai_suggested_severity']
                row['time_ago'] = get_time_ago(row['created_at'])
                nearby.append(row)
        conn.close()
        return jsonify({'success': True, 'count': len(nearby), 'incidents': nearby})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify', methods=['POST'])
def verify_incident():
    try:
        data = request.get_json()
        inc_id, u_id, resp = data.get('incident_id'), data.get('user_id', 1), data.get('response')
        if not all([inc_id, resp]): return jsonify({'error': 'Missing fields'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM verifications WHERE incident_id = ? AND user_id = ?", (inc_id, u_id))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Already verified'}), 400
            
        cursor.execute("INSERT INTO verifications (incident_id, user_id, response, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (inc_id, u_id, resp))
        cursor.execute("SELECT SUM(CASE WHEN response = 'yes' THEN 1 ELSE 0 END) as y, SUM(CASE WHEN response = 'no' THEN 1 ELSE 0 END) as n FROM verifications WHERE incident_id = ?", (inc_id,))
        counts = cursor.fetchone()
        y, n = counts['y'] or 0, counts['n'] or 0
        new_status = 'verified' if y >= 3 and y > n else ('false' if n >= 3 and n > y else 'unverified')
        cursor.execute("UPDATE incidents SET status = ? WHERE id = ?", (new_status, inc_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'incident_status': new_status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/incident/<int:incident_id>', methods=['GET'])
def get_incident_details(incident_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT i.*, u.name as reporter_name FROM incidents i LEFT JOIN users u ON i.created_by = u.id WHERE i.id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc: return jsonify({'error': 'Not found'}), 404
        
        cursor.execute("SELECT ir.*, u.name as reporter_name FROM incident_reports ir LEFT JOIN users u ON ir.reporter_id = u.id WHERE ir.incident_id = ? ORDER BY ir.created_at DESC", (incident_id,))
        reps = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("SELECT response, COUNT(*) as c FROM verifications WHERE incident_id = ? GROUP BY response", (incident_id,))
        v_rows = cursor.fetchall()
        v_summary = {'yes': 0, 'no': 0, 'not_sure': 0}
        for v in v_rows: v_summary[v['response']] = v['c']
        
        conn.close()
        return jsonify({'success': True, 'incident': dict(inc), 'reports': reps, 'verification_summary': v_summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/responder/incidents', methods=['GET'])
def get_responder_incidents():
    try:
        role = session.get('responder_role')
        if not role: return jsonify({'error': 'Unauthorized'}), 401
        
        map_roles = {'medical': ['medical'], 'police': ['crime'], 'fire': ['fire'], 'traffic': ['accident'], 'disaster': ['medical', 'crime', 'fire', 'accident', 'other']}
        allowed = map_roles.get(role, [])
        if not allowed: return jsonify({'success': True, 'incidents': []})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(allowed))
        query = f"SELECT i.*, i.ai_suggested_severity AS severity, ? AS responder_id FROM incidents i WHERE i.status NOT IN ('resolved', 'false') AND i.type IN ({placeholders}) ORDER BY i.created_at DESC"
        cursor.execute(query, [session['responder_id']] + allowed)
        incs = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'incidents': incs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/incident/<int:incident_id>/status', methods=['POST'])
def update_status(incident_id):
    try:
        status = request.get_json().get('status')
        if status not in ['in_progress', 'resolved', 'false']: return jsonify({'error': 'Invalid'}), 400
        conn = get_db_connection()
        if status == 'resolved':
            conn.execute("UPDATE incidents SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (status, incident_id))
        else:
            conn.execute("UPDATE incidents SET status = ? WHERE id = ?", (status, incident_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'new_status': status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/responder/register', methods=['GET', 'POST'])
def responder_register():
    if request.method == 'GET': return render_template('responder_register.html')
    try:
        name, role = request.form.get('name'), request.form.get('role')
        proof_path = None
        if 'proof' in request.files:
            file = request.files['proof']
            if file.filename != '':
                proof_path = f"responder_proofs/{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                os.makedirs(os.path.join('static', 'responder_proofs'), exist_ok=True)
                file.save(os.path.join('static', proof_path))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO responders (name, role, proof_path, status) VALUES (?, ?, ?, 'approved')", (name, role, proof_path))
        conn.commit()
        session['responder_id'], session['responder_role'] = cursor.lastrowid, role
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/incident/<int:incident_id>/priority', methods=['POST'])
def set_priority(incident_id):
    p = request.get_json().get('priority')
    conn = get_db_connection()
    conn.execute("UPDATE incidents SET responder_priority = ? WHERE id = ?", (p, incident_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/incident/<int:incident_id>/claim', methods=['POST'])
def claim(incident_id):
    rid = session.get('responder_id')
    conn = get_db_connection()
    conn.execute("UPDATE incidents SET claimed_by = ?, claimed_at = CURRENT_TIMESTAMP WHERE id = ?", (rid, incident_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/incident/<int:incident_id>/user-status', methods=['GET'])
def u_status(incident_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT i.status, i.claimed_by, r.name FROM incidents i LEFT JOIN responders r ON i.claimed_by = r.id WHERE i.id = ?", (incident_id,))
    row = cursor.fetchone()
    conn.close()
    if not row: return jsonify({'error': 'Not found'}), 404
    return jsonify({"status": row[0], "claimed": row[1] is not None, "responder_name": row[2]})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========================
# DATABASE INITIALIZATION TRIGGER
# ========================
with app.app_context():
    init_db()

if __name__ == '__main__':
    print("Emergency Incident Reporting API (SQLite Running)")
    app.run(debug=True, host='0.0.0.0', port=5000)