import os
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager, get_jwt
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime
import csv
import io

# --- App Configuration ---
app = Flask(__name__)
CORS(app)

# --- Database Configuration ---
try:
    client = MongoClient(os.environ.get('MONGO_URI'))
    db = client.attendanceDB
    print("MongoDB connection successful.")
except Exception as e:
    print(f"MongoDB connection failed: {e}")

app.config['JWT_SECRET_KEY'] = 'your-super-secret-key-change-this'
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# --- Helper: Role Check ---
def role_required(allowed_roles):
    if not isinstance(allowed_roles, list):
        allowed_roles = [allowed_roles]
        
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get("roles", [])
            if not any(r in user_roles for r in allowed_roles):
                return jsonify({"error": "Access forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/api/test')
def test_connection():
    return jsonify({"message": "Connected!"})

# ==========================================
# 1. AUTHENTICATION
# ==========================================

@app.route('/api/login', methods=['POST'])
def unified_login():
    try:
        data = request.get_json()
        identifier = data.get('identifier')
        password = data.get('password')

        if not identifier or not password:
            return jsonify({"error": "Credentials required"}), 400

        # A. Try Staff Login
        user = db.users.find_one({'username': identifier})
        if user and bcrypt.check_password_hash(user['password'], password):
            identity = str(user['_id'])
            additional_claims = {
                "name": user.get('name', user['username']),
                "roles": user['roles'],
                "department": user.get('department', ''),
                "email": user.get('email', '')
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            
            return jsonify({
                "message": "Login successful",
                "access_token": access_token,
                "role": "superadmin" if "superadmin" in user['roles'] else "staff",
                "user_details": additional_claims
            }), 200

        # B. Try Student Login
        student = db.students.find_one({"registerNumber": identifier})
        if student and student['dob'] == password:
            identity = str(student['_id'])
            
            s_class = db.classes.find_one({"_id": student['classId']})
            class_name = "Unknown Class"
            if s_class:
                class_name = f"{s_class['year']} {s_class['degreeType']} {s_class['department']} (Shift {s_class.get('shift', 1)})"

            additional_claims = {
                "name": student['name'],
                "registerNumber": student['registerNumber'],
                "roles": ["student"],
                "className": class_name,
                "email": student.get('email', '')
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            return jsonify({
                "message": "Login successful", 
                "access_token": access_token,
                "role": "student",
                "user_details": additional_claims
            }), 200

        return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 2. SUPERADMIN FEATURES
# ==========================================

@app.route('/api/admin/stats', methods=['GET'])
@role_required(['superadmin'])
def get_admin_dashboard_stats():
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$classId", 
                    "total": {"$sum": 1},
                    "present": {
                        "$sum": {
                            "$cond": [{"$in": ["$status", ["present", "on_duty"]]}, 1, 0]
                        }
                    }
                }
            }
        ]
        class_stats = list(db.attendance_records.aggregate(pipeline))
        
        dept_stats = {}
        total_college_present = 0
        total_college_records = 0
        
        for stat in class_stats:
            class_info = db.classes.find_one({"_id": stat['_id']})
            if class_info:
                dept = class_info['department']
                if dept not in dept_stats:
                    dept_stats[dept] = {"present": 0, "total": 0}
                
                dept_stats[dept]["present"] += stat["present"]
                dept_stats[dept]["total"] += stat["total"]
                
                total_college_present += stat["present"]
                total_college_records += stat["total"]

        dept_percentages = []
        for dept, data in dept_stats.items():
            pct = (data['present'] / data['total']) * 100 if data['total'] > 0 else 0
            dept_percentages.append({"department": dept, "percentage": round(pct, 2)})
            
        college_pct = (total_college_present / total_college_records) * 100 if total_college_records > 0 else 0
        
        return jsonify({
            "college_percentage": round(college_pct, 2),
            "department_stats": dept_percentages
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/classes', methods=['POST'])
@role_required(['superadmin'])
def create_class():
    data = request.get_json()
    db.classes.insert_one(data)
    return jsonify({"message": "Class created successfully"}), 201

@app.route('/api/staff/register', methods=['POST'])
@role_required(['superadmin'])
def create_staff():
    try:
        data = request.get_json()
        
        # Check if username exists
        if db.users.find_one({'username': data.get('username')}):
            return jsonify({"error": "Username already exists"}), 400

        hashed_pw = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
        
        new_user = {
            "username": data.get('username'),
            "password": hashed_pw,
            "name": data.get('name'),
            "email": data.get('email'),
            "department": data.get('department'),
            "roles": data.get('roles') 
        }
        result = db.users.insert_one(new_user)
        
        return jsonify({
            "message": "Staff created successfully", 
            "userId": str(result.inserted_id) 
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/classes', methods=['GET'])
@role_required(['superadmin', 'faculty', 'tutor'])
def get_all_classes():
    try:
        query = {}
        year = request.args.get('year')
        if year and year.isdigit(): query['year'] = int(year)
            
        shift = request.args.get('shift')
        if shift and shift.isdigit(): query['shift'] = int(shift)
            
        department = request.args.get('department')
        if department: query['department'] = {'$regex': f'^{department}$', '$options': 'i'}
            
        medium = request.args.get('medium')
        if medium: query['medium'] = medium

        classes = []
        for doc in db.classes.find(query):
            doc['_id'] = str(doc['_id'])
            
            # --- THE FIX IS HERE ---
            if doc.get('tutorId'):
                tutor = db.users.find_one({"_id": doc['tutorId']})
                doc['tutorName'] = tutor['name'] if tutor else "Unknown"
                doc['tutorId'] = str(doc['tutorId']) # <--- We must convert this to string!
                
            classes.append(doc)
            
        return jsonify(classes), 200
    except Exception as e:
        print(f"Search Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/classes/<classId>/assign-tutor', methods=['PUT'])
@role_required(['superadmin'])
def assign_tutor(classId):
    data = request.get_json()
    db.classes.update_one({'_id': ObjectId(classId)}, {'$set': {'tutorId': ObjectId(data.get('tutorId'))}})
    return jsonify({"message": "Tutor assigned"}), 200

# ==========================================
# 3. FACULTY / STAFF FEATURES
# ==========================================

@app.route('/api/staff/class-students/<classId>', methods=['GET'])
@role_required(['faculty', 'tutor'])
def get_students_for_marking(classId):
    date = request.args.get('date')
    hour = request.args.get('hour')
    
    if not date or not hour:
        return jsonify({"error": "Date and Hour required"}), 400

    try:
        students = []
        if not ObjectId.is_valid(classId):
             return jsonify({"error": "Invalid Class ID"}), 400

        for s in db.students.find({"classId": ObjectId(classId)}):
            record = db.attendance_records.find_one({
                "studentId": s['_id'], "date": date, "hour": int(hour)
            })
            
            students.append({
                "studentId": str(s['_id']),
                "registerNumber": s.get('registerNumber', 'N/A'),
                "name": s.get('name', 'Unknown Student'), 
                "status": record['status'] if record else None
            })
        return jsonify(students), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/staff/submit-attendance', methods=['POST'])
@role_required(['faculty', 'tutor'])
def submit_attendance_bulk():
    try:
        data = request.get_json()
        marked_by = get_jwt_identity()
        
        class_id = data.get('classId')
        date = data.get('date')
        hour = int(data.get('hour'))
        records = data.get('records')

        if not records:
            return jsonify({"error": "No records to submit"}), 400

        for rec in records:
            db.attendance_records.update_one(
                {"studentId": ObjectId(rec['studentId']), "date": date, "hour": hour},
                {"$set": {"status": rec['status'], "markedBy": ObjectId(marked_by), "classId": ObjectId(class_id)}},
                upsert=True
            )
            
        return jsonify({"message": "Attendance submitted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 4. TUTOR SPECIFIC FEATURES
# ==========================================

@app.route('/api/tutor/students', methods=['POST'])
@role_required(['tutor'])
def add_student():
    tutor_id = get_jwt_identity()
    my_class = db.classes.find_one({"tutorId": ObjectId(tutor_id)})
    if not my_class: return jsonify({"error": "No class assigned"}), 403
    
    data = request.get_json()
    data['classId'] = my_class['_id']
    if db.students.find_one({"registerNumber": data['registerNumber']}):
        return jsonify({"error": "Register Number exists"}), 400
        
    db.students.insert_one(data)
    return jsonify({"message": "Student added"}), 201

@app.route('/api/tutor/calendar', methods=['POST'])
@role_required(['tutor'])
def update_calendar():
    tutor_id = get_jwt_identity()
    my_class = db.classes.find_one({"tutorId": ObjectId(tutor_id)})
    if not my_class: return jsonify({"error": "No class assigned"}), 403
    
    data = request.get_json()
    db.calendar_events.update_one(
        {"classId": my_class['_id'], "date": data['date']},
        {"$set": {
            "day_order": int(data['day_order']) if data.get('day_order') else None,
            "event_title": data.get('event_title'),
            "classId": my_class['_id']
        }},
        upsert=True
    )
    return jsonify({"message": "Calendar updated"}), 200

# ==========================================
# 5. STUDENT DASHBOARD
# ==========================================

@app.route('/api/student/me', methods=['GET'])
@role_required(['student'])
def get_student_me():
    student_id = get_jwt_identity()
    student = db.students.find_one({"_id": ObjectId(student_id)})
    class_name = "Unknown"
    if student.get('classId'):
        c = db.classes.find_one({"_id": student['classId']})
        if c: class_name = f"{c['year']} {c['degreeType']} {c['department']}"

    return jsonify({
        "name": student['name'],
        "registerNumber": student['registerNumber'],
        "className": class_name
    }), 200

@app.route('/api/student/my-attendance', methods=['GET'])
@role_required(['student'])
def get_student_dashboard_data():
    student_id = get_jwt_identity()
    student = db.students.find_one({"_id": ObjectId(student_id)})
    class_id = student['classId']
    
    records = list(db.attendance_records.find({"studentId": ObjectId(student_id)}))
    total_p = sum(1 for r in records if r['status'] == 'present')
    total_a = sum(1 for r in records if r['status'] == 'absent')
    total_od = sum(1 for r in records if r['status'] == 'on_duty')
    total = total_p + total_a + total_od
    pct = ((total_p + total_od) / total) * 100 if total > 0 else 0
    
    calendar_events = list(db.calendar_events.find({"classId": class_id}))
    calendar_map = {}
    
    for event in calendar_events:
        calendar_map[event['date']] = {
            "day_order": event.get('day_order'),
            "events": event.get('event_title'),
            "attendance": {}
        }
        
    for record in records:
        date = record['date']
        if date not in calendar_map:
            calendar_map[date] = {"day_order": None, "events": None, "attendance": {}}
        calendar_map[date]["attendance"][record['hour']] = record['status']
        
    return jsonify({
        "stats": {
            "percentage": round(pct, 2),
            "present": total_p,
            "absent": total_a,
            "onDuty": total_od
        },
        "calendar": calendar_map
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)