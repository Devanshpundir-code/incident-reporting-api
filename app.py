from flask import Flask, request, jsonify, send_from_directory, render_template, redirect
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
CORS(app)  # Enable CORS for frontend-backend communication

# Configuration
app.config['SECRET_KEY'] = 'emergency-app-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pokemon29@',
    'database': 'incidence',
    'port': 3306
}

# ========================
# HELPER FUNCTIONS
# ========================
def get_db_connection():
    """Create and return database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file):
    """Save uploaded file and return path"""
    if file and allowed_file(file.filename):
        # Generate unique filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in meters (Haversine formula)"""
    R = 6371000  # Earth radius in meters
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * \
        math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def ai_suggest_severity(description, incident_type):
    """
    Simple rule-based AI to suggest severity
    This is a placeholder - in production, use ML model
    """
    description_lower = description.lower()
    
    # Critical keywords
    critical_keywords = ['fire', 'explosion', 'gun', 'shot', 'stab', 'bleeding', 
                        'unconscious', 'not breathing', 'heart attack', 'stroke',
                        'trapped', 'collapsed building', 'gas leak']
    
    # Serious keywords
    serious_keywords = ['accident', 'crash', 'hit', 'broken bone', 'severe pain',
                       'bleeding', 'fall', 'assault', 'fight', 'robbery']
    
    # Medium keywords
    medium_keywords = ['minor accident', 'small fire', 'injury', 'pain',
                      'argument', 'disturbance', 'suspicious']
    
    # Check for critical
    for keyword in critical_keywords:
        if keyword in description_lower:
            return 'critical'
    
    # Check for serious
    for keyword in serious_keywords:
        if keyword in description_lower:
            return 'serious'
    
    # Check for medium
    for keyword in medium_keywords:
        if keyword in description_lower:
            return 'medium'
    
    # Default based on incident type
    type_severity = {
        'medical': 'serious',
        'fire': 'critical',
        'crime': 'serious',
        'accident': 'medium',
        'other': 'minor'
    }
    
    return type_severity.get(incident_type, 'minor')

def get_severity_color(severity):
    """Convert severity level to color code"""
    color_map = {
        'critical': 'red',
        'serious': 'orange',
        'medium': 'yellow',
        'minor': 'green'
    }
    return color_map.get(severity, 'yellow')

# ========================
# ROUTES
# ========================

@app.route("/")
def index():
    return render_template("index.html")

from flask import session

@app.route('/responder')
def responder():
    # Check if responder is registered
    if not session.get('responder_id'):
        return redirect('/responder/register')

    return render_template('responder.html')



@app.route('/report', methods=['POST'])
def report_incident():
    print("===== /report HIT =====")
    print("FORM DATA:", request.form)
    print("FILES:", request.files)
    """
    POST /report
    Submit a new incident report
    """
    try:
        # Get form data
        incident_type = request.form.get('type')
        description = request.form.get('description')
        latitude = float(request.form.get('latitude'))
        longitude = float(request.form.get('longitude'))
        user_id = request.form.get('user_id', 1)  # Default to user_id 1 for demo
        
        if not all([incident_type, description, latitude, longitude]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Save uploaded file if exists
        media_path = None
        if 'media' in request.files:
            file = request.files['media']
            if file.filename != '':
                media_path = save_uploaded_file(file)
        
        # AI severity suggestion
        ai_severity = ai_suggest_severity(description, incident_type)
        severity_color = get_severity_color(ai_severity)
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Check for duplicate incidents within 200m radius
        duplicate_incident_id = None
        cursor.execute("""
            SELECT id, latitude, longitude 
            FROM incidents 
            WHERE type = %s 
                AND status NOT IN ('resolved', 'false') 
                AND created_at >= NOW() - INTERVAL 15 MINUTE
        """, (incident_type,))
        
        incidents = cursor.fetchall()

        for incident in incidents:
            distance = calculate_distance(latitude, longitude, 
                                         incident['latitude'], incident['longitude'])
            if distance <= 200:  # 200 meters radius
                duplicate_incident_id = incident['id']
                break
        
        if duplicate_incident_id:
            # Attach to existing incident
            incident_id = duplicate_incident_id
            cursor.execute("""
                INSERT INTO incident_reports 
                (incident_id, reporter_id, description, media_path, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (incident_id, user_id, description, media_path))
            
            # Update incident severity if this report suggests higher severity
            cursor.execute(
                "SELECT ai_suggested_severity FROM incidents WHERE id = %s",
                (incident_id,)
            )
            row = cursor.fetchone()
            existing_severity = row['ai_suggested_severity'] if row else 'minor'

            
            severity_order = {'minor': 0, 'medium': 1, 'serious': 2, 'critical': 3}
            if severity_order.get(ai_severity, 0) > severity_order.get(existing_severity, 0):
                cursor.execute("""
                    UPDATE incidents 
                    SET ai_suggested_severity = %s, severity_color = %s
                    WHERE id = %s
                """, (ai_severity, severity_color, incident_id))
        
        else:
            # Create new incident
            cursor.execute("""
                INSERT INTO incidents 
                (type, description, latitude, longitude, severity_color, 
                 ai_suggested_severity, status, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'unverified', %s, NOW())
            """, (incident_type, description, latitude, longitude, 
                  severity_color, ai_severity, user_id))
            
            incident_id = cursor.lastrowid
            session['last_reported_incident'] = incident_id

            # Create first report
            cursor.execute("""
                INSERT INTO incident_reports 
                (incident_id, reporter_id, description, media_path, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (incident_id, user_id, description, media_path))
        
        connection.commit()
        
        response_data = {
            'success': True,
            'incident_id': incident_id,
            'status': 'unverified',
            'ai_suggested_severity': ai_severity,
            'severity_color': severity_color,
            'message': 'Incident reported successfully'
        }
        
        return jsonify(response_data), 201
        
    except Exception as e:
        print(f"Error in /report: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@app.route('/incidents/nearby', methods=['GET'])
def get_nearby_incidents():
    """
    GET /incidents/nearby
    Fetch incidents within 500m radius
    Query params: lat, lng, radius (optional, default 500m)
    """
    try:
        lat = float(request.args.get('lat', 0))
        lng = float(request.args.get('lng', 0))
        radius = float(request.args.get('radius', 500))  # meters
        
        if lat == 0 and lng == 0:
            return jsonify({'error': 'Location required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get all active incidents (not resolved/false)
        cursor.execute("""
            SELECT id, type, description, latitude, longitude, 
                   severity_color, ai_suggested_severity, status, created_at
            FROM incidents 
            WHERE status NOT IN ('resolved', 'false')
            ORDER BY created_at DESC
        """)
        
        incidents = cursor.fetchall()
        nearby_incidents = []
        
        # Filter by distance
        for incident in incidents:
            distance = calculate_distance(lat, lng, 
                                         incident['latitude'], incident['longitude'])
            if distance <= radius:
                incident['distance'] = round(distance)
                incident['distance_unit'] = 'm'
                
                # Format for frontend
                formatted_incident = {
                    'id': incident['id'],
                    'type': incident['type'].title(),
                    'description': incident['description'],
                    'severity': incident['ai_suggested_severity'],
                    'severity_color': incident['severity_color'],
                    'status': incident['status'],
                    'time_ago': get_time_ago(incident['created_at']),
                    'distance': f"{incident['distance']}m"
                }
                nearby_incidents.append(formatted_incident)
        
        return jsonify({
            'success': True,
            'count': len(nearby_incidents),
            'incidents': nearby_incidents
        })
        
    except Exception as e:
        print(f"Error in /incidents/nearby: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@app.route('/verify', methods=['POST'])
def verify_incident():
    """
    POST /verify
    Submit verification response (Yes/No/Not Sure)
    """
    try:
        data = request.get_json()
        incident_id = data.get('incident_id')
        user_id = data.get('user_id', 1)  # Default for demo
        response = data.get('response')  # yes, no, not_sure
        
        if not all([incident_id, response]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if response not in ['yes', 'no', 'not_sure']:
            return jsonify({'error': 'Invalid response type'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Check if user already verified this incident
        cursor.execute("""
            SELECT id FROM verifications 
            WHERE incident_id = %s AND user_id = %s
        """, (incident_id, user_id))
        
        if cursor.fetchone():
            return jsonify({'error': 'Already verified this incident'}), 400
        
        # Insert verification
        cursor.execute("""
            INSERT INTO verifications 
            (incident_id, user_id, response, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (incident_id, user_id, response))
        
        # Get verification counts
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN response = 'yes' THEN 1 ELSE 0 END) as yes_count,
                SUM(CASE WHEN response = 'no' THEN 1 ELSE 0 END) as no_count,
                SUM(CASE WHEN response = 'not_sure' THEN 1 ELSE 0 END) as not_sure_count
            FROM verifications 
            WHERE incident_id = %s
        """, (incident_id,))
        
        counts = cursor.fetchone()
        
        # Update incident status based on verifications
        yes_count = counts['yes_count'] or 0
        no_count = counts['no_count'] or 0
        
        if yes_count >= 3 and yes_count > no_count:
            new_status = 'verified'
        elif no_count >= 3 and no_count > yes_count:
            new_status = 'false'
        else:
            new_status = 'unverified'
        
        cursor.execute("""
            UPDATE incidents 
            SET status = %s 
            WHERE id = %s
        """, (new_status, incident_id))
        
        connection.commit()
        
        return jsonify({
            'success': True,
            'message': 'Verification recorded',
            'verification_counts': {
                'yes': yes_count,
                'no': no_count,
                'not_sure': counts['not_sure_count'] or 0
            },
            'incident_status': new_status
        })
        
    except Exception as e:
        print(f"Error in /verify: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@app.route('/incident/<int:incident_id>', methods=['GET'])
def get_incident_details(incident_id):
    """
    GET /incident/<id>
    Get detailed incident information
    """
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get incident details
        cursor.execute("""
            SELECT i.*, u.name as reporter_name
            FROM incidents i
            LEFT JOIN users u ON i.created_by = u.id
            WHERE i.id = %s
        """, (incident_id,))
        
        incident = cursor.fetchone()
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        # Get all reports for this incident
        cursor.execute("""
            SELECT ir.*, u.name as reporter_name
            FROM incident_reports ir
            LEFT JOIN users u ON ir.reporter_id = u.id
            WHERE ir.incident_id = %s
            ORDER BY ir.created_at DESC
        """, (incident_id,))
        
        reports = cursor.fetchall()
        
        # Get verification counts
        cursor.execute("""
            SELECT 
                response,
                COUNT(*) as count,
                GROUP_CONCAT(u.name) as verifiers
            FROM verifications v
            LEFT JOIN users u ON v.user_id = u.id
            WHERE v.incident_id = %s
            GROUP BY response
        """, (incident_id,))
        
        verifications = cursor.fetchall()
        
        # Calculate verification summary
        verification_summary = {
            'yes': 0,
            'no': 0,
            'not_sure': 0,
            'verifiers': []
        }
        
        for v in verifications:
            verification_summary[v['response']] = v['count']
            if v['verifiers']:
                verification_summary['verifiers'].extend(v['verifiers'].split(','))
        
        return jsonify({
            'success': True,
            'incident': incident,
            'reports': reports,
            'verification_summary': verification_summary
        })
        
    except Exception as e:
        print(f"Error in /incident/<id>: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@app.route('/responder/incidents', methods=['GET'])
def get_responder_incidents():
    try:
        responder_role = session.get('responder_role')
        if not responder_role:
            return jsonify({'error': 'Unauthorized'}), 401

        ROLE_INCIDENT_MAP = {
            'medical': ['medical'],
            'police': ['crime'],
            'fire': ['fire'],
            'traffic': ['accident'],
            'disaster': ['medical', 'crime', 'fire', 'accident', 'other']
        }

        allowed_types = ROLE_INCIDENT_MAP.get(responder_role, [])
        if not allowed_types:
            return jsonify({'success': True, 'count': 0, 'incidents': []})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        placeholders = ','.join(['%s'] * len(allowed_types))

        query = f"""
    SELECT 
        i.id,
        i.type,
        i.description,
        i.latitude,
        i.longitude,
        i.status,
        i.created_at,
        i.ai_suggested_severity AS severity,
        i.responder_priority,
        i.claimed_by,
        %s AS responder_id,
        COUNT(DISTINCT ir.id) AS related_reports_count
    FROM incidents i
    LEFT JOIN incident_reports ir ON i.id = ir.incident_id
    WHERE i.status NOT IN ('resolved', 'false')
      AND i.type IN ({placeholders})
    GROUP BY i.id
    ORDER BY i.created_at DESC
"""


        cursor.execute(
    query,
    (session['responder_id'], *allowed_types)
)

        incidents = cursor.fetchall()

        for incident in incidents:
            incident['verification_summary'] = {}

            if incident.get('verification_responses'):
                responses = incident['verification_responses'].split(',')
                incident['verification_summary'] = {
                    'yes': responses.count('yes'),
                    'no': responses.count('no'),
                    'not_sure': responses.count('not_sure')
                }

            incident.pop('verification_responses', None)

        return jsonify({
            'success': True,
            'count': len(incidents),
            'incidents': incidents
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@app.route('/incident/<int:incident_id>/status', methods=['POST'])
def update_incident_status(incident_id):
    """
    POST /incident/<id>/status
    Update incident status (for responders)
    """
    try:
        data = request.get_json()
        new_status = data.get('status')
        responder_id = data.get('responder_id', 1)  # Default for demo
        
        if not new_status:
            return jsonify({'error': 'Status required'}), 400
        
        if new_status not in ['in_progress', 'resolved', 'false']:
            return jsonify({'error': 'Invalid status'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Check if incident exists
        cursor.execute("SELECT id FROM incidents WHERE id = %s", (incident_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Incident not found'}), 404
        
        # Update status
        if new_status == 'resolved':
            cursor.execute("""
                UPDATE incidents 
                SET status = %s, resolved_at = NOW()
                WHERE id = %s
            """, (new_status, incident_id))
        else:
            cursor.execute("""
                UPDATE incidents 
                SET status = %s
                WHERE id = %s
            """, (new_status, incident_id))
        
        # Log status change (optional - could add to separate table)
        
        connection.commit()
        
        return jsonify({
            'success': True,
            'message': f'Incident status updated to {new_status}',
            'incident_id': incident_id,
            'new_status': new_status
        })
        
    except Exception as e:
        print(f"Error in /incident/<id>/status: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
            
@app.route('/responder/register')
def responder_register():
    return render_template('responder_register.html')

@app.route('/responder/register', methods=['POST'])
def submit_responder_registration():
    try:
        name = request.form.get('name')
        role = request.form.get('role')

        if not name or not role:
            return jsonify({'error': 'Missing fields'}), 400

        proof_file = request.files.get('proof')
        proof_path = None

        if proof_file and proof_file.filename != '':
            filename = secure_filename(proof_file.filename)
            proof_path = f"responder_proofs/{uuid.uuid4().hex}_{filename}"
            full_path = os.path.join('static', proof_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            proof_file.save(full_path)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO responders (name, role, proof_path, status)
            VALUES (%s, %s, %s, 'approved')
        """, (name, role, proof_path))

        conn.commit()

        # ✅ ADD THESE 3 LINES (VERY IMPORTANT)
        responder_id = cursor.lastrowid
        session['responder_id'] = responder_id
        session['responder_role'] = role

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/responder/logout')
def responder_logout():
    session.clear()   # remove responder session
    return redirect('/') 

@app.route('/incident/<int:incident_id>/priority', methods=['POST'])
def update_incident_priority(incident_id):
    if not session.get('responder_id'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    priority = data.get('priority')

    if priority not in ['low', 'medium', 'high', 'critical']:
        return jsonify({'error': 'Invalid priority'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE incidents
        SET responder_priority = %s
        WHERE id = %s
    """, (priority, incident_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'priority': priority})

@app.route('/incident/<int:incident_id>/responder-update', methods=['POST'])
def responder_update(incident_id):
    if not session.get('responder_id'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    note = data.get('note')
    eta = data.get('eta')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE incidents
        SET responder_note = %s,
            responder_eta = %s
        WHERE id = %s
    """, (note, eta, incident_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/incident/<int:incident_id>/claim', methods=['POST'])
def claim_incident(incident_id):
    if not session.get('responder_id'):
        return jsonify({'error': 'Unauthorized'}), 401

    responder_id = session['responder_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if already claimed
    cursor.execute(
        "SELECT claimed_by FROM incidents WHERE id = %s",
        (incident_id,)
    )
    row = cursor.fetchone()

    if not row:
        return jsonify({'error': 'Incident not found'}), 404

    if row['claimed_by'] and row['claimed_by'] != responder_id:
        return jsonify({'error': 'Already claimed by another responder'}), 409

    # Claim it
    cursor.execute("""
        UPDATE incidents
        SET claimed_by = %s, claimed_at = NOW()
        WHERE id = %s
    """, (responder_id, incident_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'claimed_by': responder_id})

@app.route('/incident/<int:incident_id>/note', methods=['POST'])
def add_incident_note(incident_id):
    if not session.get('responder_id'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    message = data.get('message')

    if not message:
        return jsonify({'error': 'Message required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO incident_notes
        (incident_id, sender_type, sender_id, message)
        VALUES (%s, 'responder', %s, %s)
    """, (incident_id, session['responder_id'], message))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/incident/<int:incident_id>/notes', methods=['GET'])
def get_incident_notes(incident_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT sender_type, message, created_at
        FROM incident_notes
        WHERE incident_id = %s
        ORDER BY created_at ASC
    """, (incident_id,))

    notes = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify({'notes': notes})

@app.route('/incident/<int:incident_id>/user-status', methods=['GET'])
def user_incident_status(incident_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            i.status,
            i.claimed_by,
            i.claimed_at,
            i.responder_priority,
            i.responder_note,
            i.responder_eta,
            r.name AS responder_name
        FROM incidents i
        LEFT JOIN responders r ON i.claimed_by = r.id
        WHERE i.id = %s
    """, (incident_id,))

    incident = cursor.fetchone()
    cursor.close()
    conn.close()

    if not incident:
        return jsonify({'error': 'Incident not found'}), 404

    return jsonify({
        "status": incident["status"],
        "claimed": incident["claimed_by"] is not None,
        "responder_name": incident["responder_name"],
        "priority": incident["responder_priority"],
        "note": incident["responder_note"],
        "eta": incident["responder_eta"],
        "claimed_at": incident["claimed_at"]
    })



@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========================
# HELPER FUNCTIONS (continued)
# ========================
def get_time_ago(timestamp):
    """Convert timestamp to human-readable time ago"""
    if not timestamp:
        return "Just now"
    
    now = datetime.now()
    if isinstance(timestamp, str):
        timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    
    diff = now - timestamp
    
    if diff.days > 365:
        return f"{diff.days // 365} years ago"
    elif diff.days > 30:
        return f"{diff.days // 30} months ago"
    elif diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hours ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minutes ago"
    else:
        return "Just now"



# ========================
# ERROR HANDLERS
# ========================
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ========================
# MAIN ENTRY POINT
# ========================
if __name__ == '__main__':
    print("Emergency Incident Reporting API")
    print("Available endpoints:")
    print("  POST /report - Submit incident report")
    print("  GET /incidents/nearby - Get nearby incidents")
    print("  POST /verify - Verify incident")
    print("  GET /incident/<id> - Get incident details")
    print("  GET /responder/incidents - Responder dashboard")
    print("  POST /incident/<id>/status - Update incident status")
    print("\nStarting server on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

    #kofkr