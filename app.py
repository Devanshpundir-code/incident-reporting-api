from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, session
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
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

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pokemon29@', # Ensure this matches your local password
    'database': 'incidence',
    'port': 3306
}

# ========================
# HELPER FUNCTIONS
# ========================
def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

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
    R = 6371000  # Earth radius in meters
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat, delta_lon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def ai_suggest_severity(description, incident_type):
    desc = description.lower()
    critical = ['fire', 'explosion', 'gun', 'shot', 'stab', 'unconscious', 'breathing', 'heart attack']
    serious = ['accident', 'crash', 'hit', 'broken', 'pain', 'bleeding', 'fall', 'assault', 'robbery']
    
    for kw in critical:
        if kw in desc: return 'critical'
    for kw in serious:
        if kw in desc: return 'serious'
    
    type_map = {'medical': 'serious', 'fire': 'critical', 'crime': 'serious', 'accident': 'medium'}
    return type_map.get(incident_type, 'minor')

def get_severity_color(severity):
    return {'critical': 'red', 'serious': 'orange', 'medium': 'yellow', 'minor': 'green'}.get(severity, 'green')

def get_time_ago(ts):
    if not ts: return "Just now"
    diff = datetime.now() - ts
    if diff.days > 0: return f"{diff.days}d ago"
    if diff.seconds > 3600: return f"{diff.seconds // 3600}h ago"
    if diff.seconds > 60: return f"{diff.seconds // 60}m ago"
    return "Just now"

# ========================
# ROUTES
# ========================

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/report', methods=['POST'])
def report_incident():
    try:
        incident_type = request.form.get('type')
        description = request.form.get('description')
        latitude = float(request.form.get('latitude'))
        longitude = float(request.form.get('longitude'))
        user_id = request.form.get('user_id', 1) 
        
        media_path = save_uploaded_file(request.files.get('media'))
        ai_severity = ai_suggest_severity(description, incident_type)
        severity_color = get_severity_color(ai_severity)
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Duplicate check (200m)
        cursor.execute("SELECT id, latitude, longitude FROM incidents WHERE type = %s AND status NOT IN ('resolved', 'false') AND created_at >= NOW() - INTERVAL 15 MINUTE", (incident_type,))
        incidents = cursor.fetchall()
        
        duplicate_id = next((i['id'] for i in incidents if calculate_distance(latitude, longitude, i['latitude'], i['longitude']) <= 200), None)

        if duplicate_id:
            cursor.execute("INSERT INTO incident_reports (incident_id, reporter_id, description, media_path) VALUES (%s, %s, %s, %s)", (duplicate_id, user_id, description, media_path))
            incident_id = duplicate_id
        else:
            cursor.execute("INSERT INTO incidents (type, description, latitude, longitude, severity_color, ai_suggested_severity, status, created_by) VALUES (%s, %s, %s, %s, %s, %s, 'unverified', %s)",
                           (incident_type, description, latitude, longitude, severity_color, ai_severity, user_id))
            incident_id = cursor.lastrowid
            cursor.execute("INSERT INTO incident_reports (incident_id, reporter_id, description, media_path) VALUES (%s, %s, %s, %s)", (incident_id, user_id, description, media_path))

        conn.commit()
        return jsonify({'success': True, 'incident_id': incident_id, 'ai_severity': ai_severity}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals(): conn.close()

@app.route('/incidents/nearby', methods=['GET'])
def get_nearby_incidents():
    try:
        lat, lng = float(request.args.get('lat', 0)), float(request.args.get('lng', 0))
        radius = float(request.args.get('radius', 500))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM incidents WHERE status NOT IN ('resolved', 'false')")
        
        nearby = []
        for inc in cursor.fetchall():
            dist = calculate_distance(lat, lng, inc['latitude'], inc['longitude'])
            if dist <= radius:
                inc['distance'] = f"{round(dist)}m"
                inc['time_ago'] = get_time_ago(inc['created_at'])
                nearby.append(inc)
        
        return jsonify({'success': True, 'incidents': nearby})
    finally:
        if 'conn' in locals(): conn.close()

@app.route('/responder/incidents', methods=['GET'])
def get_responder_incidents():
    try:
        role = session.get('responder_role')
        if not role: return jsonify({'error': 'Unauthorized'}), 401

        role_map = {'medical': ['medical'], 'police': ['crime'], 'fire': ['fire'], 'traffic': ['accident'], 'disaster': ['medical', 'crime', 'fire', 'accident', 'other']}
        allowed = role_map.get(role, [])
        placeholders = ','.join(['%s'] * len(allowed))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Optimized query with GROUP_CONCAT for verifications
        query = f"""
            SELECT i.*, GROUP_CONCAT(v.response) as verification_responses, COUNT(DISTINCT ir.id) as report_count
            FROM incidents i
            LEFT JOIN incident_reports ir ON i.id = ir.incident_id
            LEFT JOIN verifications v ON i.id = v.incident_id
            WHERE i.status NOT IN ('resolved', 'false') AND i.type IN ({placeholders})
            GROUP BY i.id ORDER BY i.created_at DESC
        """
        cursor.execute(query, tuple(allowed))
        incidents = cursor.fetchall()

        for inc in incidents:
            resps = (inc['verification_responses'] or "").split(',')
            inc['verification_summary'] = {'yes': resps.count('yes'), 'no': resps.count('no'), 'not_sure': resps.count('not_sure')}

        return jsonify({'success': True, 'incidents': incidents})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals(): conn.close()

@app.route('/incident/<int:incident_id>/claim', methods=['POST'])
def claim_incident(incident_id):
    responder_id = session.get('responder_id')
    if not responder_id: return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("UPDATE incidents SET claimed_by = %s, claimed_at = NOW(), status = 'in_progress' WHERE id = %s AND claimed_by IS NULL", (responder_id, incident_id))
    conn.commit()
    return jsonify({'success': cursor.rowcount > 0})

@app.route('/responder/register', methods=['POST'])
def submit_responder_registration():
    try:
        name = request.form.get('name')
        role = request.form.get('role') # Ensure this is lowercase: 'medical', 'police', etc.

        if not name or not role:
            return jsonify({'error': 'Name and Role are required'}), 400

        proof_file = request.files.get('proof')
        proof_path = None

        if proof_file and proof_file.filename != '':
            # 1. FIX: Ensure the folder exists before saving
            upload_dir = os.path.join('static', 'responder_proofs')
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = secure_filename(proof_file.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            proof_path = f"responder_proofs/{unique_name}"
            
            # Save the file
            proof_file.save(os.path.join('static', proof_path))

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor()

        # 2. FIX: Check if your SQL 'role' matches exactly what comes from HTML
        # The DB expects: 'medical','police','fire','traffic','disaster'
        cursor.execute("""
            INSERT INTO responders (name, role, proof_path, status)
            VALUES (%s, %s, %s, 'approved')
        """, (name, role.lower(), proof_path))

        conn.commit()

        responder_id = cursor.lastrowid
        session['responder_id'] = responder_id
        session['responder_role'] = role.lower()

        return jsonify({'success': True})

    except Exception as e:
        # This will print the EXACT error in your terminal/cmd
        print("!!! REGISTRATION ERROR:", str(e))
        return jsonify({'error': f"Server Error: {str(e)}"}), 500
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/incident/<int:incident_id>/status', methods=['POST'])
def update_status(incident_id):
    status = request.get_json().get('status')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE incidents SET status = %s, resolved_at = %s WHERE id = %s", 
                   (status, datetime.now() if status == 'resolved' else None, incident_id))
    conn.commit()
    return jsonify({'success': True})

@app.route('/responder/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)