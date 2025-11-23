import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';
import './AdminDashboard.css';

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [stats, setStats] = useState(null);
  const [userRoles, setUserRoles] = useState([]);
  const [classList, setClassList] = useState([]); // To populate the dropdown

  // --- FORM STATES ---
  const [calendarData, setCalendarData] = useState({ date: '', day_order: '', event_title: '' });
  const [studentData, setStudentData] = useState({ name: '', registerNumber: '', dob: '' });
  
  // Create Class Form
  const [classData, setClassData] = useState({ degreeType: 'UG', year: '', department: '', shift: '1', medium: 'English' });
  
  // Create Staff Form
  const [staffData, setStaffData] = useState({ 
    name: '', 
    email: '', 
    department: '', 
    username: '', 
    password: '', 
    roles: '', // e.g. "tutor, faculty"
    assignClassId: '' // Selected class to assign if tutor
  });

  const token = localStorage.getItem('token');

  useEffect(() => {
    if (!token) {
      navigate('/');
      return;
    }
    
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const roles = payload.roles || [];
      setUserRoles(roles);
      
      // Set Default Tab based on Role
      if (roles.includes('superadmin')) {
        if (activeTab === '') setActiveTab('stats');
        fetchStats();
        fetchClasses(); // Fetch classes so we can assign them to tutors
      } else if (roles.includes('tutor')) {
        if (activeTab === '') setActiveTab('calendar');
      }
    } catch (e) {
      navigate('/');
    }
  }, [navigate, token]);

  const isSuperAdmin = userRoles.includes('superadmin');
  const isTutor = userRoles.includes('tutor');

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  // --- DATA FETCHING ---
  const fetchStats = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/admin/stats', { headers: { Authorization: `Bearer ${token}` } });
      setStats(res.data);
    } catch (err) { console.error(err); }
  };

  const fetchClasses = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/admin/classes', { headers: { Authorization: `Bearer ${token}` } });
      setClassList(res.data);
    } catch (err) { console.error(err); }
  };

  // --- SUBMIT HANDLERS ---

  // 1. Create Staff (And Assign Tutor if selected)
  const submitStaff = async (e) => {
    e.preventDefault();
    setMessage(''); setError('');
    
    try {
      // Step 1: Create the User
      const rolesArray = staffData.roles.split(',').map(r => r.trim().toLowerCase());
      const res = await axios.post('http://localhost:5000/api/staff/register', { 
        ...staffData, 
        roles: rolesArray 
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const newUserId = res.data.userId;

      // Step 2: If a class was selected, assign this new user as the tutor
      if (staffData.assignClassId && newUserId) {
        await axios.put(`http://localhost:5000/api/admin/classes/${staffData.assignClassId}/assign-tutor`, {
          tutorId: newUserId
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }

      setMessage(`Staff '${staffData.name}' created successfully!`);
      // Reset form
      setStaffData({ name: '', email: '', department: '', username: '', password: '', roles: '', assignClassId: '' });
      fetchClasses(); // Refresh list
    } catch (err) { 
      setError(err.response?.data?.error || 'Failed to create staff'); 
    }
  };

  // 2. Create Class
  const submitClass = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...classData, year: parseInt(classData.year), shift: parseInt(classData.shift) };
      await axios.post('http://localhost:5000/api/admin/classes', payload, { headers: { Authorization: `Bearer ${token}` } });
      setMessage('Class created successfully!');
      fetchClasses(); // Refresh list
    } catch (err) { setError(err.response?.data?.error || 'Failed'); }
  };

  // 3. Tutor Actions
  const submitCalendar = async (e) => {
    e.preventDefault();
    try {
      await axios.post('http://localhost:5000/api/tutor/calendar', calendarData, { headers: { Authorization: `Bearer ${token}` } });
      setMessage('Calendar updated successfully!');
      setCalendarData({ date: '', day_order: '', event_title: '' });
    } catch (err) { setError(err.response?.data?.error || 'Failed'); }
  };

  const submitStudent = async (e) => {
    e.preventDefault();
    try {
      await axios.post('http://localhost:5000/api/tutor/students', studentData, { headers: { Authorization: `Bearer ${token}` } });
      setMessage('Student added successfully!');
      setStudentData({ name: '', registerNumber: '', dob: '' });
    } catch (err) { setError(err.response?.data?.error || 'Failed'); }
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div>
          <h1>{isSuperAdmin ? 'Admin Dashboard' : 'Class Management'}</h1>
          <p className="sub-text">{isSuperAdmin ? 'College Control Center' : 'Manage your class details'}</p>
        </div>
        <div style={{display:'flex', gap:'10px'}}>
          {!isSuperAdmin && <button onClick={() => navigate('/staff-dashboard')} className="back-btn">Back to Attendance</button>}
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </div>
      </header>

      <div className="admin-layout">
        {/* SIDEBAR */}
        <div className="sidebar">
          {/* Super Admin Menu */}
          {isSuperAdmin && (
            <>
              <div className="divider">Super Admin</div>
              <button className={activeTab === 'stats' ? 'active' : ''} onClick={() => setActiveTab('stats')}>📊 College Stats</button>
              <button className={activeTab === 'class' ? 'active' : ''} onClick={() => setActiveTab('class')}>🏫 Create Class</button>
              <button className={activeTab === 'staff' ? 'active' : ''} onClick={() => setActiveTab('staff')}>👥 Create Staff</button>
            </>
          )}
          
          {/* Tutor Menu (Hidden for Superadmin based on your requirement) */}
          {isTutor && (
            <>
              <div className="divider">Tutor Controls</div>
              <button className={activeTab === 'calendar' ? 'active' : ''} onClick={() => {setActiveTab('calendar'); setMessage(''); setError('')}}>📅 Set Calendar</button>
              <button className={activeTab === 'student' ? 'active' : ''} onClick={() => {setActiveTab('student'); setMessage(''); setError('')}}>🎓 Add Student</button>
            </>
          )}
        </div>

        {/* CONTENT AREA */}
        <div className="content-area">
          {message && <div className="success-msg">{message}</div>}
          {error && <div className="error-msg">{error}</div>}

          {/* 1. STATS VIEW */}
          {activeTab === 'stats' && isSuperAdmin && (
            <div className="stats-view">
              <div className="stats-grid">
                <div className="stat-card primary">
                  <h3>Overall College Attendance</h3>
                  <div className="big-number">{stats?.college_percentage || 0}%</div>
                </div>
              </div>
              <h3>Department Wise Breakdown</h3>
              <div className="dept-list">
                {stats?.department_stats?.map((dept, idx) => (
                  <div key={idx} className="dept-card"><span>{dept.department}</span><span className="dept-pct">{dept.percentage}%</span></div>
                ))}
              </div>
            </div>
          )}

          {/* 2. CREATE CLASS FORM */}
          {activeTab === 'class' && isSuperAdmin && (
            <div className="form-card">
              <h2>Create New Class</h2>
              <form onSubmit={submitClass}>
                <div className="form-row">
                  <div className="form-group"><label>Degree</label><select value={classData.degreeType} onChange={(e) => setClassData({...classData, degreeType: e.target.value})}><option value="UG">UG</option><option value="PG">PG</option></select></div>
                  <div className="form-group"><label>Year</label><input type="number" min="1" max="3" value={classData.year} onChange={(e) => setClassData({...classData, year: e.target.value})} required /></div>
                </div>
                <div className="form-group"><label>Department</label><input type="text" value={classData.department} onChange={(e) => setClassData({...classData, department: e.target.value})} required /></div>
                <div className="form-row">
                  <div className="form-group"><label>Shift</label><select value={classData.shift} onChange={(e) => setClassData({...classData, shift: e.target.value})}><option value="1">Shift 1</option><option value="2">Shift 2</option></select></div>
                  <div className="form-group"><label>Medium</label><select value={classData.medium} onChange={(e) => setClassData({...classData, medium: e.target.value})}><option value="English">English</option><option value="Tamil">Tamil</option></select></div>
                </div>
                <button type="submit" className="submit-btn">Create Class</button>
              </form>
            </div>
          )}

          {/* 3. CREATE STAFF FORM (Updated with all fields) */}
          {activeTab === 'staff' && isSuperAdmin && (
            <div className="form-card">
              <h2>Create Staff / Tutor</h2>
              <form onSubmit={submitStaff}>
                {/* Profile Details */}
                <div className="form-group">
                  <label>Full Name</label>
                  <input type="text" placeholder="e.g. Dr. John Smith" value={staffData.name} onChange={(e) => setStaffData({...staffData, name: e.target.value})} required />
                </div>
                
                <div className="form-row">
                  <div className="form-group">
                    <label>Email</label>
                    <input type="email" placeholder="john@college.edu" value={staffData.email} onChange={(e) => setStaffData({...staffData, email: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label>Department</label>
                    <input type="text" placeholder="e.g. CS" value={staffData.department} onChange={(e) => setStaffData({...staffData, department: e.target.value})} required />
                  </div>
                </div>

                {/* Login Details */}
                <div className="form-row">
                  <div className="form-group">
                    <label>Username</label>
                    <input type="text" value={staffData.username} onChange={(e) => setStaffData({...staffData, username: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label>Password</label>
                    <input type="password" value={staffData.password} onChange={(e) => setStaffData({...staffData, password: e.target.value})} required />
                  </div>
                </div>

                {/* Roles & Class Assignment */}
                <div className="form-group">
                  <label>Roles (type 'faculty' or 'tutor, faculty')</label>
                  <input type="text" value={staffData.roles} onChange={(e) => setStaffData({...staffData, roles: e.target.value})} required />
                </div>

                {/* Only show Class Assignment if 'tutor' is typed in roles */}
                {staffData.roles.includes('tutor') && (
                  <div className="form-group" style={{background: '#f9f9f9', padding: '10px', borderRadius: '8px', border: '1px solid #eee'}}>
                    <label style={{color: '#1e3c72'}}>Assign Class (Optional)</label>
                    <select value={staffData.assignClassId} onChange={(e) => setStaffData({...staffData, assignClassId: e.target.value})}>
                      <option value="">-- Select a Class --</option>
                      {classList.map(cls => (
                        <option key={cls._id} value={cls._id}>
                          {cls.year} {cls.degreeType} {cls.department} (Shift {cls.shift}) - {cls.medium}
                        </option>
                      ))}
                    </select>
                    <small style={{display:'block', marginTop:'5px', color:'#666'}}>Selecting a class will make this user the Class Tutor.</small>
                  </div>
                )}

                <button type="submit" className="submit-btn">Create Staff</button>
              </form>
            </div>
          )}

          {/* 4. TUTOR FORMS (Only for Tutors) */}
          {activeTab === 'calendar' && isTutor && (
            <div className="form-card">
              <h2>Set Calendar Day</h2>
              <form onSubmit={submitCalendar}>
                <div className="form-group"><label>Date</label><input type="date" value={calendarData.date} onChange={(e) => setCalendarData({...calendarData, date: e.target.value})} required /></div>
                <div className="form-group"><label>Day Order (1-6) OR Leave Empty for Holiday</label><input type="number" min="1" max="6" value={calendarData.day_order} onChange={(e) => setCalendarData({...calendarData, day_order: e.target.value})} /></div>
                <div className="form-group"><label>Event Title (Optional)</label><input type="text" value={calendarData.event_title} onChange={(e) => setCalendarData({...calendarData, event_title: e.target.value})} /></div>
                <button type="submit" className="submit-btn">Update Calendar</button>
              </form>
            </div>
          )}

          {activeTab === 'student' && isTutor && (
            <div className="form-card">
              <h2>Add New Student</h2>
              <form onSubmit={submitStudent}>
                <div className="form-group"><label>Name</label><input type="text" value={studentData.name} onChange={(e) => setStudentData({...studentData, name: e.target.value})} required /></div>
                <div className="form-group"><label>Register Number</label><input type="text" value={studentData.registerNumber} onChange={(e) => setStudentData({...studentData, registerNumber: e.target.value})} required /></div>
                <div className="form-group"><label>Date of Birth</label><input type="date" value={studentData.dob} onChange={(e) => setStudentData({...studentData, dob: e.target.value})} required /></div>
                <button type="submit" className="submit-btn">Add Student</button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;