import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager, get_jwt
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime 

# --- App Configuration ---
app = Flask(__name__)
CORS(app)

# --- Database Configuration ---
try:
    client = MongoClient(os.environ.get('MONGO_URI'))
    db = client.attendanceDB
    db.command('ping')
    print("MongoDB connection successful.")
except Exception as e:
    print(f"MongoDB connection failed: {e}")

# --- Security & JWT Configuration ---
app.config['JWT_SECRET_KEY'] = 'your-super-secret-key-change-this'
bcrypt = Bcrypt(app)
jwt = JWTManager(app)


# --- Role Checking Helper ---
def role_required(role):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get("roles")
            
            if not user_roles or role not in user_roles:
                return jsonify({"error": "Access forbidden: Requires specified role"}), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# --- Test Route (Keep for checking) ---
@app.route('/api/test')
def test_connection():
    try:
        db.command('ping')
        return jsonify({"message": "Hello from Flask! Connected to MongoDB successfully!"})
    except Exception as e:
        return jsonify({"message": f"Connection failed: {e}"}), 500


# --- STUDENT AUTHENTICATION ---
@app.route('/api/student/login', methods=['POST'])
def student_login():
    try:
        data = request.get_json()
        register_number = data.get('registerNumber')
        dob = data.get('dob')

        if not register_number or not dob:
            return jsonify({"error": "Register Number and D.O.B. are required"}), 400

        students_collection = db.students
        student = students_collection.find_one({"registerNumber": register_number})

        if student and student['dob'] == dob:
            identity = str(student['_id'])
            additional_claims = {
                "name": student['name'],
                "registerNumber": student['registerNumber'],
                "roles": ["student"]
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            return jsonify({"message": "Login successful", "access_token": access_token}), 200
        else:
            return jsonify({"error": "Invalid Register Number or D.O.B."}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- STAFF AUTHENTICATION ENDPOINTS ---
@app.route('/api/staff/register', methods=['POST'])
@role_required('superadmin')
def staff_register():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        roles = data.get('roles')

        if not username or not password or not roles:
            return jsonify({"error": "Username, password, and roles are required"}), 400

        users_collection = db.users
        if users_collection.find_one({'username': username}):
            return jsonify({"error": "Username already exists"}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = {"username": username, "password": hashed_password, "roles": roles}
        result = users_collection.insert_one(new_user)
        return jsonify({"message": "Staff user created successfully", "userId": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/staff/login', methods=['POST'])
def staff_login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        users_collection = db.users
        user = users_collection.find_one({'username': username})

        if user and bcrypt.check_password_hash(user['password'], password):
            identity = str(user['_id'])
            additional_claims = {"username": user['username'], "roles": user['roles']}
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            return jsonify({"message": "Login successful", "access_token": access_token}), 200
        else:
            return jsonify({"error": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- SUPERADMIN: Class Management Endpoints ---
@app.route('/api/admin/classes', methods=['POST'])
@role_required('superadmin')
def create_class():
    try:
        data = request.get_json()
        new_class = {
            "degreeType": data.get('degreeType'), "year": data.get('year'),
            "department": data.get('department'), "shift": data.get('shift'),
            "tutorId": None
        }
        classes_collection = db.classes
        result = classes_collection.insert_one(new_class)
        return jsonify({"message": "Class created successfully", "classId": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/classes', methods=['GET'])
@role_required('superadmin')
def get_all_classes():
    try:
        classes_collection = db.classes
        all_classes = []
        for doc in classes_collection.find():
            doc['_id'] = str(doc['_id'])
            all_classes.append(doc)
        return jsonify(all_classes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- SUPERADMIN: Staff Management ---
@app.route('/api/admin/staff', methods=['GET'])
@role_required('superadmin')
def get_all_staff():
    try:
        users_collection = db.users
        all_staff = []
        for doc in users_collection.find():
            doc['_id'] = str(doc['_id'])
            del doc['password']
            all_staff.append(doc)
        return jsonify(all_staff), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/classes/<classId>/assign-tutor', methods=['PUT'])
@role_required('superadmin')
def assign_tutor(classId):
    try:
        data = request.get_json()
        tutor_id = data.get('tutorId')
        if not tutor_id:
            return jsonify({"error": "tutorId is required"}), 400
        
        classes_collection = db.classes
        users_collection = db.users
        
        tutor = users_collection.find_one({'_id': ObjectId(tutor_id), 'roles': 'tutor'})
        if not tutor:
            return jsonify({"error": "Tutor not found or user is not a tutor"}), 404

        existing_class = classes_collection.find_one({"tutorId": ObjectId(tutor_id)})
        if existing_class and str(existing_class['_id']) != classId:
            return jsonify({"error": "This tutor is already assigned to another class"}), 400

        result = classes_collection.update_one(
            {'_id': ObjectId(classId)}, {'$set': {'tutorId': ObjectId(tutor_id)}}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Class not found"}), 404
        return jsonify({"message": "Tutor assigned successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- TUTOR: Student Management ---
def get_tutor_class(tutor_id):
    classes_collection = db.classes
    tutor_class = classes_collection.find_one({"tutorId": ObjectId(tutor_id)})
    return tutor_class

@app.route('/api/tutor/students', methods=['POST'])
@role_required('tutor')
def add_student():
    try:
        tutor_id = get_jwt_identity()
        tutor_class = get_tutor_class(tutor_id)
        if not tutor_class:
            return jsonify({"error": "You are not assigned to any class"}), 403

        data = request.get_json()
        new_student = {
            "name": data.get("name"), "registerNumber": data.get("registerNumber"),
            "dob": data.get("dob"), "classId": tutor_class['_id']
        }
        students_collection = db.students
        if students_collection.find_one({"registerNumber": new_student['registerNumber']}):
            return jsonify({"error": "Student with this register number already exists"}), 400
        result = students_collection.insert_one(new_student)
        return jsonify({"message": "Student added successfully", "studentId": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tutor/students', methods=['GET'])
@role_required('tutor')
def get_my_students():
    try:
        tutor_id = get_jwt_identity()
        tutor_class = get_tutor_class(tutor_id)
        if not tutor_class:
            return jsonify({"error": "You are not assigned to any class"}), 403

        students_collection = db.students
        my_students = []
        for doc in students_collection.find({"classId": tutor_class['_id']}):
            doc['_id'] = str(doc['_id'])
            doc['classId'] = str(doc['classId'])
            my_students.append(doc)
        return jsonify(my_students), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- TUTOR: Timetable Management ---
@app.route('/api/tutor/timetable', methods=['GET'])
@role_required('tutor')
def get_timetable():
    try:
        tutor_id = get_jwt_identity()
        tutor_class = get_tutor_class(tutor_id)
        if not tutor_class:
            return jsonify({"error": "You are not assigned to any class"}), 403

        timetable_collection = db.timetable
        timetable_doc = timetable_collection.find_one({"classId": tutor_class['_id']})
        
        if not timetable_doc:
            return jsonify({"message": "No timetable found", "timetable": None}), 404
        
        serializable_timetable = {
            "_id": str(timetable_doc.get('_id')),
            "classId": str(timetable_doc.get('classId')),
            "schedule": {}
        }
        
        if 'schedule' in timetable_doc:
            for i in range(1, 7):
                day_key = f"day_{i}"
                if day_key in timetable_doc['schedule']:
                    hours = timetable_doc['schedule'][day_key]
                    serializable_timetable['schedule'][day_key] = {
                        "hour_1": str(hours.get("hour_1")) if hours.get("hour_1") else None,
                        "hour_2": str(hours.get("hour_2")) if hours.get("hour_2") else None,
                        "hour_3": str(hours.get("hour_3")) if hours.get("hour_3") else None,
                        "hour_4": str(hours.get("hour_4")) if hours.get("hour_4") else None,
                        "hour_5": str(hours.get("hour_5")) if hours.get("hour_5") else None,
                    }
        
        return jsonify(serializable_timetable), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tutor/timetable', methods=['PUT'])
@role_required('tutor')
def update_timetable():
    try:
        tutor_id = get_jwt_identity()
        tutor_class = get_tutor_class(tutor_id)
        if not tutor_class:
            return jsonify({"error": "You are not assigned to any class"}), 403

        data = request.get_json()
        
        schedule = {}
        users_collection = db.users
        
        for i in range(1, 7):
            day_key = f"day_{i}"
            if day_key not in data:
                return jsonify({"error": f"Missing {day_key} in timetable data"}), 400
            
            hours = data[day_key]
            schedule[day_key] = {}
            
            for j in range(1, 6):
                hour_key = f"hour_{j}"
                faculty_id_str = hours.get(hour_key)
                
                if faculty_id_str:
                    faculty = users_collection.find_one({
                        "_id": ObjectId(faculty_id_str), "roles": "faculty"
                    })
                    if not faculty:
                        return jsonify({"error": f"Invalid faculty ID for {day_key}, {hour_key}"}), 400
                    schedule[day_key][hour_key] = ObjectId(faculty_id_str)
                else:
                    schedule[day_key][hour_key] = None

        timetable_collection = db.timetable
        
        timetable_collection.update_one(
            {"classId": tutor_class['_id']},
            {'$set': {"classId": tutor_class['_id'], "schedule": schedule}},
            upsert=True
        )
        
        return jsonify({"message": "Timetable updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- TUTOR: Master Calendar Management ---
@app.route('/api/tutor/calendar', methods=['POST'])
@role_required('tutor')
def set_calendar_day():
    try:
        tutor_id = get_jwt_identity()
        tutor_class = get_tutor_class(tutor_id)
        if not tutor_class:
            return jsonify({"error": "You are not assigned to any class"}), 403

        data = request.get_json()
        date = data.get('date') # "YYYY-MM-DD"
        day_order = data.get('day_order') # 1-6, or null
        event_title = data.get('event_title') # "Holiday", "Symposium", etc.

        if not date:
            return jsonify({"error": "Date is required"}), 400
        
        if event_title and day_order:
             return jsonify({"error": "A day with an event/holiday cannot have a day order"}), 400
        
        # We must cast day_order to int if it exists, otherwise it's null
        day_order_int = None
        if day_order:
            try:
                day_order_int = int(day_order)
                if day_order_int not in range(1, 7):
                    raise ValueError()
            except ValueError:
                return jsonify({"error": "day_order must be an integer between 1 and 6"}), 400

        if not event_title and day_order_int is None:
             return jsonify({"error": "A working day must have a day_order (1-6)"}), 400

        calendar_collection = db.calendar_events
        
        calendar_collection.update_one(
            {"classId": tutor_class['_id'], "date": date},
            {"$set": {
                "classId": tutor_class['_id'], "date": date,
                "day_order": day_order_int,
                "event_title": event_title if event_title else None
            }},
            upsert=True
        )
        
        return jsonify({"message": "Calendar updated successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tutor/calendar', methods=['GET'])
@role_required('tutor')
def get_calendar_events():
    try:
        tutor_id = get_jwt_identity()
        tutor_class = get_tutor_class(tutor_id)
        if not tutor_class:
            return jsonify({"error": "You are not assigned to any class"}), 403

        query = {"classId": tutor_class['_id']}
        
        month = request.args.get('month')
        year = request.args.get('year')
        
        if month and year:
            date_regex = f"^{year}-{int(month):02d}-"
            query['date'] = {"$regex": date_regex}

        calendar_collection = db.calendar_events
        events = []
        for doc in calendar_collection.find(query):
            doc['_id'] = str(doc['_id'])
            doc['classId'] = str(doc['classId'])
            events.append(doc)
            
        return jsonify(events), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- STUDENT DASHBOARD ENDPOINTS ---
@app.route('/api/student/me', methods=['GET'])
@role_required('student')
def get_student_me():
    try:
        student_id = get_jwt_identity()
        students_collection = db.students
        student = students_collection.find_one({"_id": ObjectId(student_id)})
        if not student:
            return jsonify({"error": "Student not found"}), 404

        class_collection = db.classes
        student_class = class_collection.find_one({"_id": student['classId']})
        
        profile = {
            "name": student['name'], "registerNumber": student['registerNumber'],
            "dob": student['dob'],
            "classInfo": {
                "degreeType": student_class.get('degreeType'), "year": student_class.get('year'),
                "department": student_class.get('department'), "shift": student_class.get('shift')
            }
        }
        return jsonify(profile), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/student/my-attendance', methods=['GET'])
@role_required('student')
def get_student_attendance():
    try:
        student_id = get_jwt_identity()
        attendance_collection = db.attendance_records
        records = list(attendance_collection.find({"studentId": ObjectId(student_id)}))
        
        total_present, total_absent, total_on_duty = 0, 0, 0
        
        for record in records:
            if record['status'] == 'present': total_present += 1
            elif record['status'] == 'absent': total_absent += 1
            elif record['status'] == 'on_duty': total_on_duty += 1
        
        total_marked_hours = total_present + total_absent + total_on_duty
        total_counted_as_present = total_present + total_on_duty
        percentage = (total_counted_as_present / total_marked_hours) * 100 if total_marked_hours > 0 else 0
        
        serializable_records = []
        for record in records:
            serializable_record = {
                "_id": str(record.get('_id')), "studentId": str(record.get('studentId')),
                "date": record.get('date'), "hour": record.get('hour'),
                "status": record.get('status'), "markedBy": str(record.get('markedBy')),
                "classId": str(record.get('classId'))
            }
            serializable_records.append(serializable_record)
            
        return jsonify({
            "stats": {
                "totalPresent": total_present, "totalAbsent": total_absent,
                "totalOnDuty": total_on_duty, "totalMarkedHours": total_marked_hours,
                "percentage": round(percentage, 2)
            },
            "records": serializable_records
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- (!!!) NEW AND CORRECTED - FACULTY: Attendance Marking (!!!) ---

@app.route('/api/faculty/my-schedule', methods=['GET'])
@role_required('faculty')
def get_my_schedule_today():
    """
    Finds all classes/hours the logged-in faculty member
    teaches based on the MASTER CALENDAR'S day order.
    """
    try:
        faculty_id = get_jwt_identity()
        today_date = datetime.now().strftime('%Y-%m-%d') # "2025-11-17"
        
        my_schedule = []
        
        # Find all classes this faculty might teach in
        timetable_collection = db.timetable
        classes_collection = db.classes
        calendar_collection = db.calendar_events
        
        # This is a complex query: "Find all timetables"
        # In a larger system, we'd optimize this, but for one college it's fine.
        for timetable in timetable_collection.find():
            class_id = timetable['classId']
            
            # 1. Find today's calendar entry for this class
            calendar_entry = calendar_collection.find_one({
                "classId": class_id,
                "date": today_date
            })
            
            # 2. Check if it's a working day
            if calendar_entry and calendar_entry.get('day_order'):
                day_order = calendar_entry.get('day_order')
                day_key = f"day_{day_order}" # e.g., "day_1"
                
                # 3. Check if this faculty teaches on this day order
                if day_key in timetable['schedule']:
                    day_schedule = timetable['schedule'][day_key]
                    
                    for hour, assigned_faculty_id in day_schedule.items():
                        if str(assigned_faculty_id) == faculty_id:
                            # This faculty teaches this hour!
                            class_info = classes_collection.find_one({"_id": class_id})
                            my_schedule.append({
                                "classId": str(class_info['_id']),
                                "className": f"{class_info['year']} {class_info['department']} {class_info.get('shift', '')}",
                                "hour": int(hour.split('_')[1]) # "hour_1" -> 1
                            })

        return jsonify({
            "today": today_date,
            "schedule": my_schedule
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/faculty/class-list/<classId>', methods=['GET'])
@role_required('faculty')
def get_class_list_for_marking(classId):
    """
    Gets the list of students for a specific class.
    Also returns any attendance already marked for TODAY.
    """
    try:
        students_collection = db.students
        attendance_collection = db.attendance_records
        
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        student_list = []
        for student in students_collection.find({"classId": ObjectId(classId)}):
            student_attendance_today = {}
            for i in range(1, 6): # Hours 1-5
                record = attendance_collection.find_one({
                    "studentId": student['_id'],
                    "date": today_date,
                    "hour": i
                })
                student_attendance_today[f"hour_{i}"] = record['status'] if record else "not_marked"

            student_list.append({
                "studentId": str(student['_id']),
                "name": student['name'],
                "registerNumber": student['registerNumber'],
                "attendance": student_attendance_today
            })
            
        return jsonify(student_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/faculty/mark-attendance', methods=['POST'])
@role_required('faculty')
def mark_attendance():
    """
    Marks (or updates) an attendance record, but now
    checks against the MASTER CALENDAR.
    """
    try:
        faculty_id = get_jwt_identity()
        data = request.get_json()
        
        student_id = data.get('studentId')
        hour = data.get('hour') # e.g., 1, 2, 3
        status = data.get('status') # "present", "absent", "on_duty"
        
        today_date = datetime.now().strftime('%Y-%m-%d')

        if not student_id or not hour or not status:
            return jsonify({"error": "studentId, hour, and status are required"}), 400
        
        if status not in ['present', 'absent', 'on_duty']:
            return jsonify({"error": "Invalid status"}), 400
        
        # --- (!!!) NEW, CORRECT SECURITY CHECK (!!!) ---
        students_collection = db.students
        timetable_collection = db.timetable
        calendar_collection = db.calendar_events
        
        # 1. Find the student's class
        student = students_collection.find_one({"_id": ObjectId(student_id)})
        if not student:
            return jsonify({"error": "Student not found"}), 404
        
        # 2. Find today's calendar entry for that class
        calendar_entry = calendar_collection.find_one({
            "classId": student['classId'],
            "date": today_date
        })
        if not calendar_entry or not calendar_entry.get('day_order'):
            return jsonify({"error": "This is not a working day on the calendar"}), 400
        
        day_order = calendar_entry.get('day_order')
        day_key = f"day_{day_order}" # e.g., "day_1"
        
        # 3. Find the timetable for that class
        timetable = timetable_collection.find_one({"classId": student['classId']})
        if not timetable or day_key not in timetable['schedule']:
            return jsonify({"error": "No timetable found for this class or day order"}), 404
            
        # 4. Check if this faculty is assigned to this hour
        hour_key = f"hour_{hour}"
        assigned_faculty_id = timetable['schedule'][day_key].get(hour_key)
        
        if str(assigned_faculty_id) != faculty_id:
            return jsonify({"error": "Access forbidden: You do not teach this hour."}), 403
        
        # --- (Security Check Passed) ---
        
        attendance_collection = db.attendance_records
        
        attendance_collection.update_one(
            {
                "studentId": ObjectId(student_id),
                "date": today_date,
                "hour": hour
            },
            {
                "$set": {
                    "status": status,
                    "markedBy": ObjectId(faculty_id),
                    "classId": student['classId']
                }
            },
            upsert=True
        )
        
        return jsonify({"message": "Attendance marked successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Run the App ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)