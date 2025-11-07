import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager, get_jwt
from bson.objectid import ObjectId
from functools import wraps

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


# --- STAFF AUTHENTICATION ENDPOINTS ---

@app.route('/api/staff/register', methods=['POST'])
@role_required('superadmin') # (!!!) CHANGED (!!!) - This is now protected!
def staff_register():
    """
    Creates a new staff user (tutor, faculty, admin).
    Protected: Only a 'superadmin' can access this.
    """
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


# --- (!!!) NEW - SUPERADMIN: Staff Management (!!!) ---

@app.route('/api/admin/staff', methods=['GET'])
@role_required('superadmin')
def get_all_staff():
    """
    Gets a list of all staff (users collection), but omits passwords.
    Protected: Only a 'superadmin' can access this.
    """
    try:
        users_collection = db.users
        all_staff = []
        
        # Find all documents, convert ObjectId, and remove password
        for doc in users_collection.find():
            doc['_id'] = str(doc['_id'])
            del doc['password'] # Never send passwords to the frontend!
            all_staff.append(doc)

        return jsonify(all_staff), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/classes/<classId>/assign-tutor', methods=['PUT'])
@role_required('superadmin')
def assign_tutor(classId):
    """
    Assigns a tutor to a class by updating the class's 'tutorId' field.
    Protected: Only a 'superadmin' can access this.
    """
    try:
        data = request.get_json()
        tutor_id = data.get('tutorId')

        if not tutor_id:
            return jsonify({"error": "tutorId is required"}), 400
        
        classes_collection = db.classes
        
        # Find the class and update it
        result = classes_collection.update_one(
            {'_id': ObjectId(classId)},
            {'$set': {'tutorId': ObjectId(tutor_id)}} # Store as ObjectId for proper linking
        )

        if result.matched_count == 0:
            return jsonify({"error": "Class not found"}), 404

        return jsonify({"message": "Tutor assigned successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Run the App ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)