import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';
import './AdminDashboard.css'; // We'll create this next

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('calendar');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  
  // Form States
  const [calendarData, setCalendarData] = useState({ date: '', day_order: '', event_title: '' });
  const [studentData, setStudentData] = useState({ name: '', registerNumber: '', dob: '' });
  const [classData, setClassData] = useState({ degreeType: 'UG', year: '', department: '', shift: '' });
  const [staffData, setStaffData] = useState({ username: '', password: '', roles: [] });

  const token = localStorage.getItem('token');

  useEffect(() => {
    if (!token) navigate('/');
  }, [navigate, token]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  // --- API ACTIONS ---

  const submitCalendar = async (e) => {
    e.preventDefault();
    try {
      await axios.post('http://localhost:5000/api/tutor/calendar', calendarData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessage('Calendar updated successfully!');
      setCalendarData({ date: '', day_order: '', event_title: '' });
    } catch (err) { setError(err.response?.data?.error || 'Failed'); }
  };

  const submitStudent = async (e) => {
    e.preventDefault();
    try {
      await axios.post('http://localhost:5000/api/tutor/students', studentData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessage('Student added successfully!');
      setStudentData({ name: '', registerNumber: '', dob: '' });
    } catch (err) { setError(err.response?.data?.error || 'Failed'); }
  };

  const submitClass = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...classData, year: parseInt(classData.year), shift: parseInt(classData.shift) };
      await axios.post('http://localhost:5000/api/admin/classes', payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessage('Class created successfully!');
    } catch (err) { setError(err.response?.data?.error || 'Failed'); }
  };

  const submitStaff = async (e) => {
    e.preventDefault();
    try {
      const rolesArray = staffData.roles.split(',').map(r => r.trim()); // e.g., "tutor, faculty"
      await axios.post('http://localhost:5000/api/staff/register', { ...staffData, roles: rolesArray }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessage('Staff created successfully!');
    } catch (err) { setError(err.response?.data?.error || 'Failed'); }
  };

  // --- RENDER HELPERS ---

  const renderMessage = () => (
    <>
      {message && <div className="success-msg">{message}</div>}
      {error && <div className="error-msg">{error}</div>}
    </>
  );

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Management Dashboard</h1>
        <button onClick={handleLogout} className="logout-btn">Logout</button>
      </header>

      <div className="admin-layout">
        {/* Sidebar Navigation */}
        <div className="sidebar">
          <button className={activeTab === 'calendar' ? 'active' : ''} onClick={() => {setActiveTab('calendar'); setMessage(''); setError('')}}>📅 Set Calendar</button>
          <button className={activeTab === 'student' ? 'active' : ''} onClick={() => {setActiveTab('student'); setMessage(''); setError('')}}>🎓 Add Student</button>
          <div className="divider">Admin Only</div>
          <button className={activeTab === 'class' ? 'active' : ''} onClick={() => {setActiveTab('class'); setMessage(''); setError('')}}>🏫 Create Class</button>
          <button className={activeTab === 'staff' ? 'active' : ''} onClick={() => {setActiveTab('staff'); setMessage(''); setError('')}}>👥 Create Staff</button>
        </div>

        {/* Main Content Area */}
        <div className="content-area">
          {renderMessage()}

          {/* 1. CALENDAR FORM */}
          {activeTab === 'calendar' && (
            <div className="form-card">
              <h2>Set Calendar Day</h2>
              <form onSubmit={submitCalendar}>
                <div className="form-group">
                  <label>Date</label>
                  <input type="date" value={calendarData.date} onChange={(e) => setCalendarData({...calendarData, date: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Day Order (1-6) OR Leave Empty for Holiday</label>
                  <input type="number" min="1" max="6" value={calendarData.day_order} onChange={(e) => setCalendarData({...calendarData, day_order: e.target.value})} />
                </div>
                <div className="form-group">
                  <label>Event Title (Optional - e.g., "Holiday")</label>
                  <input type="text" value={calendarData.event_title} onChange={(e) => setCalendarData({...calendarData, event_title: e.target.value})} />
                </div>
                <button type="submit" className="submit-btn">Update Calendar</button>
              </form>
            </div>
          )}

          {/* 2. STUDENT FORM */}
          {activeTab === 'student' && (
            <div className="form-card">
              <h2>Add New Student</h2>
              <form onSubmit={submitStudent}>
                <div className="form-group">
                  <label>Name</label>
                  <input type="text" value={studentData.name} onChange={(e) => setStudentData({...studentData, name: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Register Number</label>
                  <input type="text" value={studentData.registerNumber} onChange={(e) => setStudentData({...studentData, registerNumber: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Date of Birth</label>
                  <input type="date" value={studentData.dob} onChange={(e) => setStudentData({...studentData, dob: e.target.value})} required />
                </div>
                <button type="submit" className="submit-btn">Add Student</button>
              </form>
            </div>
          )}

          {/* 3. CLASS FORM */}
          {activeTab === 'class' && (
            <div className="form-card">
              <h2>Create New Class</h2>
              <form onSubmit={submitClass}>
                <div className="form-group">
                  <label>Degree Type</label>
                  <select value={classData.degreeType} onChange={(e) => setClassData({...classData, degreeType: e.target.value})}>
                    <option value="UG">UG</option>
                    <option value="PG">PG</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Year (1, 2, 3)</label>
                  <input type="number" value={classData.year} onChange={(e) => setClassData({...classData, year: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Department</label>
                  <input type="text" value={classData.department} onChange={(e) => setClassData({...classData, department: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Shift (1 or 2)</label>
                  <input type="number" value={classData.shift} onChange={(e) => setClassData({...classData, shift: e.target.value})} />
                </div>
                <button type="submit" className="submit-btn">Create Class</button>
              </form>
            </div>
          )}

          {/* 4. STAFF FORM */}
          {activeTab === 'staff' && (
            <div className="form-card">
              <h2>Create Staff</h2>
              <form onSubmit={submitStaff}>
                <div className="form-group">
                  <label>Username</label>
                  <input type="text" value={staffData.username} onChange={(e) => setStaffData({...staffData, username: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Password</label>
                  <input type="password" value={staffData.password} onChange={(e) => setStaffData({...staffData, password: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label>Roles (comma separated)</label>
                  <input type="text" placeholder="e.g. tutor, faculty" value={staffData.roles} onChange={(e) => setStaffData({...staffData, roles: e.target.value})} required />
                </div>
                <button type="submit" className="submit-btn">Create Staff</button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;