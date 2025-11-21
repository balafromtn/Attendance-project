import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager, get_jwt
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime 

app = Flask(__name__)
CORS(app)

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
def role_required(role):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get("roles")
            if not user_roles or role not in user_roles:
                return jsonify({"error": "Access forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/api/test')
def test_connection():
    return jsonify({"message": "Connected!"})

# --- (!!!) NEW: UNIFIED LOGIN ENDPOINT (!!!) ---
@app.route('/api/login', methods=['POST'])
def unified_login():
    """
    Tries to login as Staff first, then as Student.
    Returns the token and the user type.
    """
    try:
        data = request.get_json()
        identifier = data.get('identifier') # Username OR Register No
        password = data.get('password')     # Password OR D.O.B

        if not identifier or not password:
            return jsonify({"error": "Credentials required"}), 400

        # 1. Try Staff Login
        users_collection = db.users
        user = users_collection.find_one({'username': identifier})

        if user and bcrypt.check_password_hash(user['password'], password):
            identity = str(user['_id'])
            additional_claims = {"username": user['username'], "roles": user['roles']}
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            
            # Check if superadmin or tutor/faculty to determine redirect suggestion
            role_type = "superadmin" if "superadmin" in user['roles'] else "staff"
            
            return jsonify({
                "message": "Login successful",
                "access_token": access_token,
                "role": role_type # 'superadmin' or 'staff'
            }), 200

        # 2. Try Student Login
        students_collection = db.students
        student = students_collection.find_one({"registerNumber": identifier})

        if student and student['dob'] == password:
            identity = str(student['_id'])
            additional_claims = {
                "name": student['name'],
                "registerNumber": student['registerNumber'],
                "roles": ["student"]
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            return jsonify({
                "message": "Login successful", 
                "access_token": access_token,
                "role": "student"
            }), 200

        return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Keep Staff Register for Setup ---
@app.route('/api/staff/register', methods=['POST'])
@role_required('superadmin')
def staff_register():
    try:
        data = request.get_json()
        hashed_pw = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
        new_user = {"username": data.get('username'), "password": hashed_pw, "roles": data.get('roles')}
        db.users.insert_one(new_user)
        return jsonify({"message": "Staff created"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- ADMIN: Class & Staff ---
@app.route('/api/admin/classes', methods=['POST'])
@role_required('superadmin')
def create_class():
    db.classes.insert_one(request.get_json())
    return jsonify({"message": "Class created"}), 201

@app.route('/api/admin/classes', methods=['GET'])
@role_required('superadmin')
def get_all_classes():
    classes = []
    for doc in db.classes.find():
        doc['_id'] = str(doc['_id'])
        classes.append(doc)
    return jsonify(classes), 200

@app.route('/api/admin/staff', methods=['GET'])
@role_required('superadmin')
def get_all_staff():
    staff = []
    for doc in db.users.find():
        doc['_id'] = str(doc['_id'])
        del doc['password']
        staff.append(doc)
    return jsonify(staff), 200

@app.route('/api/admin/classes/<classId>/assign-tutor', methods=['PUT'])
@role_required('superadmin')
def assign_tutor(classId):
    data = request.get_json()
    db.classes.update_one({'_id': ObjectId(classId)}, {'$set': {'tutorId': ObjectId(data.get('tutorId'))}})
    return jsonify({"message": "Tutor assigned"}), 200

# --- TUTOR: Students & Timetable ---
@app.route('/api/tutor/students', methods=['POST'])
@role_required('tutor')
def add_student():
    tutor_class = db.classes.find_one({"tutorId": ObjectId(get_jwt_identity())})
    if not tutor_class: return jsonify({"error": "No class assigned"}), 403
    data = request.get_json()
    data['classId'] = tutor_class['_id']
    db.students.insert_one(data)
    return jsonify({"message": "Student added"}), 201

@app.route('/api/tutor/students', methods=['GET'])
@role_required('tutor')
def get_my_students():
    tutor_class = db.classes.find_one({"tutorId": ObjectId(get_jwt_identity())})
    if not tutor_class: return jsonify({"error": "No class assigned"}), 403
    students = []
    for doc in db.students.find({"classId": tutor_class['_id']}):
        doc['_id'] = str(doc['_id'])
        doc['classId'] = str(doc['classId'])
        students.append(doc)
    return jsonify(students), 200

@app.route('/api/tutor/timetable', methods=['PUT'])
@role_required('tutor')
def update_timetable():
    tutor_class = db.classes.find_one({"tutorId": ObjectId(get_jwt_identity())})
    if not tutor_class: return jsonify({"error": "No class assigned"}), 403
    
    data = request.get_json()
    schedule = {}
    for i in range(1, 7):
        day = f"day_{i}"
        if day in data:
            schedule[day] = {}
            for j in range(1, 6):
                hour = f"hour_{j}"
                fid = data[day].get(hour)
                schedule[day][hour] = ObjectId(fid) if fid else None
                
    db.timetable.update_one(
        {"classId": tutor_class['_id']},
        {'$set': {"classId": tutor_class['_id'], "schedule": schedule}},
        upsert=True
    )
    return jsonify({"message": "Timetable updated"}), 200

@app.route('/api/tutor/timetable', methods=['GET'])
@role_required('tutor')
def get_timetable():
    tutor_class = db.classes.find_one({"tutorId": ObjectId(get_jwt_identity())})
    if not tutor_class: return jsonify({"error": "No class assigned"}), 403
    timetable = db.timetable.find_one({"classId": tutor_class['_id']})
    if not timetable: return jsonify({"message": "No timetable"}), 404
    
    # Serialize ObjectIds
    res = {"_id": str(timetable['_id']), "schedule": {}}
    for day, hours in timetable['schedule'].items():
        res['schedule'][day] = {}
        for h, fid in hours.items():
            res['schedule'][day][h] = str(fid) if fid else None
    return jsonify(res), 200

# --- TUTOR: Calendar ---
@app.route('/api/tutor/calendar', methods=['POST'])
@role_required('tutor')
def set_calendar():
    tutor_class = db.classes.find_one({"tutorId": ObjectId(get_jwt_identity())})
    data = request.get_json()
    db.calendar_events.update_one(
        {"classId": tutor_class['_id'], "date": data['date']},
        {"$set": {"day_order": int(data['day_order']) if data.get('day_order') else None, "event_title": data.get('event_title'), "classId": tutor_class['_id']}},
        upsert=True
    )
    return jsonify({"message": "Calendar updated"}), 201

@app.route('/api/tutor/calendar', methods=['GET'])
@role_required('tutor')
def get_calendar():
    tutor_class = db.classes.find_one({"tutorId": ObjectId(get_jwt_identity())})
    query = {"classId": tutor_class['_id']}
    if request.args.get('month'):
        query['date'] = {"$regex": f"^{request.args.get('year')}-{int(request.args.get('month')):02d}-"}
    events = []
    for doc in db.calendar_events.find(query):
        doc['_id'] = str(doc['_id'])
        doc['classId'] = str(doc['classId'])
        events.append(doc)
    return jsonify(events), 200

# --- STUDENT DASHBOARD ---
@app.route('/api/student/me', methods=['GET'])
@role_required('student')
def get_student_me():
    student = db.students.find_one({"_id": ObjectId(get_jwt_identity())})
    s_class = db.classes.find_one({"_id": student['classId']})
    return jsonify({
        "name": student['name'], "registerNumber": student['registerNumber'],
        "classInfo": {"year": s_class['year'], "dept": s_class['department']}
    }), 200

@app.route('/api/student/my-attendance', methods=['GET'])
@role_required('student')
def get_my_attendance():
    records = list(db.attendance_records.find({"studentId": ObjectId(get_jwt_identity())}))
    total = len(records)
    present = sum(1 for r in records if r['status'] in ['present', 'on_duty'])
    
    serialized = []
    for r in records:
        r['_id'] = str(r['_id'])
        r['studentId'] = str(r['studentId'])
        r['markedBy'] = str(r['markedBy'])
        r['classId'] = str(r['classId'])
        serialized.append(r)

    return jsonify({
        "stats": {"percentage": (present/total)*100 if total > 0 else 0},
        "records": serialized
    }), 200

# --- FACULTY MARKING ---
@app.route('/api/faculty/my-schedule', methods=['GET'])
@role_required('faculty')
def get_my_schedule():
    fid = get_jwt_identity()
    today = datetime.now().strftime('%Y-%m-%d')
    # Find classes where calendar says today is a working day
    # And timetable says this faculty teaches that day order
    schedule = []
    # (Simplified logic for brevity - reusing logic from previous step)
    for tt in db.timetable.find():
        cal = db.calendar_events.find_one({"classId": tt['classId'], "date": today})
        if cal and cal.get('day_order'):
            day = f"day_{cal['day_order']}"
            if day in tt['schedule']:
                for h, assigned_id in tt['schedule'][day].items():
                    if str(assigned_id) == fid:
                        c_info = db.classes.find_one({"_id": tt['classId']})
                        schedule.append({
                            "className": f"{c_info['year']} {c_info['department']}",
                            "hour": int(h.split('_')[1]),
                            "classId": str(c_info['_id'])
                        })
    return jsonify({"today": today, "schedule": schedule}), 200

@app.route('/api/faculty/class-list/<classId>', methods=['GET'])
@role_required('faculty')
def get_class_list(classId):
    today = datetime.now().strftime('%Y-%m-%d')
    students = []
    for s in db.students.find({"classId": ObjectId(classId)}):
        att = {}
        for i in range(1, 6):
            rec = db.attendance_records.find_one({"studentId": s['_id'], "date": today, "hour": i})
            att[f"hour_{i}"] = rec['status'] if rec else "not_marked"
        students.append({
            "studentId": str(s['_id']), "name": s['name'], 
            "registerNumber": s['registerNumber'], "attendance": att
        })
    return jsonify(students), 200

@app.route('/api/faculty/mark-attendance', methods=['POST'])
@role_required('faculty')
def mark_attendance():
    data = request.get_json()
    fid = get_jwt_identity()
    today = datetime.now().strftime('%Y-%m-%d')
    
    student = db.students.find_one({"_id": ObjectId(data['studentId'])})
    cal = db.calendar_events.find_one({"classId": student['classId'], "date": today})
    
    if not cal or not cal.get('day_order'):
        return jsonify({"error": "Not a working day"}), 400
        
    tt = db.timetable.find_one({"classId": student['classId']})
    day = f"day_{cal['day_order']}"
    hour = f"hour_{data['hour']}"
    
    if str(tt['schedule'][day].get(hour)) != fid:
        return jsonify({"error": "Access forbidden"}), 403
        
    db.attendance_records.update_one(
        {"studentId": student['_id'], "date": today, "hour": data['hour']},
        {"$set": {"status": data['status'], "markedBy": ObjectId(fid), "classId": student['classId']}},
        upsert=True
    )
    return jsonify({"message": "Marked"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)