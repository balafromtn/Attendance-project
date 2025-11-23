from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from flask import Flask
import os

app = Flask(__name__)
bcrypt = Bcrypt(app)

# Connect to the Database inside Docker
# We use 'localhost' if running locally, or 'db' if running inside container.
# Since we will run this via 'docker exec', we use the internal URI logic implicitly, 
# but let's just use the standard pymongo connection which defaults to localhost:27017 
# if we run it against the mapped port.

# TRICK: We will assume this runs INSIDE the container where 'MONGO_URI' is set.
client = MongoClient(os.environ.get('MONGO_URI', 'mongodb://db:27017/attendanceDB'))
db = client.attendanceDB

def create_super_admin():
    # 1. Check if exists
    if db.users.find_one({'username': 'superadmin'}):
        print("⚠️  Superadmin already exists!")
        return

    # 2. Create Data
    password = "admin123"
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    user = {
        "username": "superadmin",
        "password": hashed_password,
        "name": "System Administrator",
        "email": "admin@college.edu",
        "department": "Management",
        "roles": ["superadmin"]
    }

    # 3. Insert
    try:
        db.users.insert_one(user)
        print("✅ SUCCESS: Superadmin created!")
        print("👉 Username: superadmin")
        print("👉 Password: admin123")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    create_super_admin()