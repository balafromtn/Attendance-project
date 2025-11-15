import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager, get_jwt
from bson.objectid import ObjectId
from functools import wraps
from datetime import datetime # --- NEW --- To get the current day

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
        dob = data.get('dob') # Expected format: "YYYY-MM-DD"

        if not register_number or not dob:
            return jsonify({"error": "Register Number and D.O.B. are required"}), 400

        students_collection = db.students
        student = students_collection.find_one({
            "registerNumber": register_number
        })

        if student and student['dob'] == dob:
            identity = str(student['_id'])
            additional_claims = {
                "name": student['name'],
                "registerNumber": student['registerNumber'],
                "roles": ["student"] # Hardcode the student role
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            
            return jsonify({
                "message": "Login successful",
                "access_token": access_token
            }), 200
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

        new_user = {
            "username": username,
            "password": hashed_password,
            "roles": roles
        }
        result = users_collection.insert_one(new_user)

        return jsonify({
            "message": "Staff user created successfully",
            "userId": str(result.inserted_id)
        }), 201
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
            additional_claims = {
                "username": user['username'],
                "roles": user['roles']
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            
            return jsonify({
                "message": "Login successful",
                "access_token": access_token
            }), 200
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
            "degreeType": data.get('degreeType'),
            "year": data.get('year'),
            "department": data.get('department'),
            "shift": data.get('shift'),
            "tutorId": None
        }

        if not new_class['degreeType'] or not new_class['year'] or not new_class['department']:
            return jsonify({"error": "degreeType, year, and department are required"}), 400

        classes_collection = db.classes
        result = classes_collection.insert_one(new_class)

        return jsonify({
            "message": "Class created successfully",
            "classId": str(result.inserted_id)
        }), 201
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
            {'_id': ObjectId(classId)},
            {'$set': {'tutorId': ObjectId(tutor_id)}}
        )

        if result.matched_count == 0:
            return jsonify({"error": "Class not found"}), 404

        return jsonify({"message": "Tutor assigned successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- TUTOR: Student Management ---

# Helper function to find a tutor's class
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
            "name": data.get("name"),
            "registerNumber": data.get("registerNumber"),
            "dob": data.get("dob"),
            "classId": tutor_class['_id']
        }

        if not new_student['name'] or not new_student['registerNumber'] or not new_student['dob']:
            return jsonify({"error": "Name, registerNumber, and dob are required"}), 400

        students_collection = db.students
        if students_collection.find_one({"registerNumber": new_student['registerNumber']}):
            return jsonify({"error": "Student with this register number already exists"}), 400
        
        result = students_collection.insert_one(new_student)
        
        return jsonify({
            "message": "Student added successfully",
            "studentId": str(result.inserted_id)
        }), 201
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
            return jsonify({
                "message": "No timetable found for this class. Please create one.",
                "timetable": None
            }), 404
        
        serializable_timetable = {
            "_id": str(timetable_doc.get('_id')),
            "classId": str(timetable_doc.get('classId')),
            "schedule": {}
        }
        
        if 'schedule' in timetable_doc:
            for day, hours in timetable_doc['schedule'].items():
                serializable_timetable['schedule'][day] = {
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
        
        for day, hours in data.items():
            schedule[day] = {}
            for hour, faculty_id_str in hours.items():
                if faculty_id_str:
                    faculty = users_collection.find_one({
                        "_id": ObjectId(faculty_id_str),
                        "roles": "faculty"
                    })
                    if not faculty:
                        return jsonify({"error": f"Invalid faculty ID for {day}, {hour}: {faculty_id_str}"}), 400
                    
                    schedule[day][hour] = ObjectId(faculty_id_str)
                else:
                    schedule[day][hour] = None

        timetable_collection = db.timetable
        
        timetable_collection.update_one(
            {"classId": tutor_class['_id']},
            {'$set': {
                "classId": tutor_class['_id'],
                "schedule": schedule
            }},
            upsert=True
        )
        
        return jsonify({"message": "Timetable updated successfully"}), 200
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
            "name": student['name'],
            "registerNumber": student['registerNumber'],
            "dob": student['dob'],
            "classInfo": {
                "degreeType": student_class.get('degreeType'),
                "year": student_class.get('year'),
                "department": student_class.get('department'),
                "shift": student_class.get('shift')
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
        
        total_present = 0
        total_absent = 0
        total_on_duty = 0
        
        for record in records:
            if record['status'] == 'present':
                total_present += 1
            elif record['status'] == 'absent':
                total_absent += 1
            elif record['status'] == 'on_duty':
                total_on_duty += 1
        
        total_marked_hours = total_present + total_absent + total_on_duty
        
        total_counted_as_present = total_present + total_on_duty
        percentage = 0
        if total_marked_hours > 0:
            percentage = (total_counted_as_present / total_marked_hours) * 100
        
        serializable_records = []
        for record in records:
            record['_id'] = str(record['_id'])
            record['studentId'] = str(record['studentId'])
            serializable_records.append(record)
            
        return jsonify({
            "stats": {
                "totalPresent": total_present,
                "totalAbsent": total_absent,
                "totalOnDuty": total_on_duty,
                "totalMarkedHours": total_marked_hours,
                "percentage": round(percentage, 2)
            },
            "records": serializable_records
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- (!!!) NEW - FACULTY: Attendance Marking (!!!) ---

@app.route('/api/faculty/my-schedule', methods=['GET'])
@role_required('faculty')
def get_my_schedule_today():
    """
    Finds all classes/hours the logged-in faculty member
    teaches for the current day of the week.
    """
    try:
        faculty_id = get_jwt_identity()
        
        # Get current day (e.g., "monday", "tuesday")
        today_day = datetime.now().strftime('%A').lower() # e.g., 'saturday'
        
        # If it's Saturday or Sunday, return empty
        if today_day in ['saturday', 'sunday']:
            return jsonify({
                "day": today_day,
                "schedule": []
            }), 200
            
        timetable_collection = db.timetable
        classes_collection = db.classes
        
        my_schedule = []
        
        # Find all timetables
        for timetable in timetable_collection.find():
            if today_day in timetable['schedule']:
                day_schedule = timetable['schedule'][today_day]
                class_info = classes_collection.find_one({"_id": timetable['classId']})

                for hour, assigned_faculty_id in day_schedule.items():
                    if str(assigned_faculty_id) == faculty_id:
                        # This faculty teaches this hour!
                        my_schedule.append({
                            "classId": str(class_info['_id']),
                            "className": f"{class_info['year']} {class_info['department']} {class_info.get('shift', '')}",
                            "hour": int(hour.split('_')[1]) # "hour_1" -> 1
                        })

        return jsonify({
            "day": today_day,
            "schedule": my_schedule
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/faculty/class-list/<classId>', methods=['GET'])
@role_required('faculty')
def get_class_list_for_marking(classId):
    """
    Gets the list of students for a specific class.
    Also returns any attendance already marked for today.
    """
    try:
        students_collection = db.students
        attendance_collection = db.attendance_records
        
        # Get today's date as a string "YYYY-MM-DD"
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        student_list = []
        for student in students_collection.find({"classId": ObjectId(classId)}):
            # For each student, find their attendance records for today
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
    Marks (or updates) an attendance record for a single student/hour.
    """
    try:
        faculty_id = get_jwt_identity()
        data = request.get_json()
        
        student_id = data.get('studentId')
        hour = data.get('hour') # e.g., 1, 2, 3
        status = data.get('status') # "present", "absent", "on_duty"
        
        # Get today's date as a string "YYYY-MM-DD"
        today_date = datetime.now().strftime('%Y-%m-%d')

        if not student_id or not hour or not status:
            return jsonify({"error": "studentId, hour, and status are required"}), 400
        
        if status not in ['present', 'absent', 'on_duty']:
            return jsonify({"error": "Invalid status"}), 400

        # --- (!!!) CRITICAL SECURITY CHECK (!!!) ---
        # Check if this faculty is *actually* assigned to teach this
        # student's class at this hour on this day.
        
        students_collection = db.students
        timetable_collection = db.timetable
        
        # 1. Find the student's class
        student = students_collection.find_one({"_id": ObjectId(student_id)})
        if not student:
            return jsonify({"error": "Student not found"}), 404
        
        # 2. Find the timetable for that class
        timetable = timetable_collection.find_one({"classId": student['classId']})
        if not timetable:
            return jsonify({"error": "No timetable found for this class"}), 404
            
        # 3. Check today's schedule
        today_day = datetime.now().strftime('%A').lower()
        if today_day not in timetable['schedule']:
             return jsonify({"error": "No schedule for today"}), 400
        
        hour_key = f"hour_{hour}"
        assigned_faculty_id = timetable['schedule'][today_day].get(hour_key)
        
        if str(assigned_faculty_id) != faculty_id:
            return jsonify({"error": "Access forbidden: You do not teach this hour."}), 403
        
        # --- (Security Check Passed) ---
        
        attendance_collection = db.attendance_records
        
        # Use 'upsert=True' to create a new record or update an existing one
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