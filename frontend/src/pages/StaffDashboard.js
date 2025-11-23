import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';
import './StaffDashboard.css';

const StaffDashboard = () => {
  const navigate = useNavigate();
  
  // --- STATES ---
  const [filters, setFilters] = useState({ year: '', department: '', shift: '', medium: '' });
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [students, setStudents] = useState([]);
  const [hour, setHour] = useState(1);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  
  // --- (!!!) MISSING PART ADDED HERE (!!!) ---
  const [roles, setRoles] = useState([]); 

  const token = localStorage.getItem('token');

  useEffect(() => {
    if (!token) {
      navigate('/');
      return;
    }
    
    // Decode Token to get roles (Safety check included)
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setRoles(payload.roles || []);
    } catch (e) {
      console.error("Invalid token");
    }
  }, [token, navigate]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  // --- 1. SEARCH CLASSES ---
  const handleSearch = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const cleanFilters = {};
      if (filters.department) cleanFilters.department = filters.department;
      if (filters.year) cleanFilters.year = filters.year;
      if (filters.shift) cleanFilters.shift = filters.shift;
      if (filters.medium) cleanFilters.medium = filters.medium;

      const params = new URLSearchParams(cleanFilters).toString();
      
      const res = await axios.get(`http://localhost:5000/api/admin/classes?${params}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.data.length === 0) {
        alert("No classes found matching these filters.");
      }
      setClasses(res.data);
      setSelectedClass(null);
    } catch (err) {
      console.error("Search Error:", err.response);
      if (err.response && err.response.status === 401) {
        alert("Session expired. Please login again.");
        handleLogout();
      } else {
        alert(err.response?.data?.error || "Failed to search classes");
      }
    } finally {
      setLoading(false);
    }
  };

  // --- 2. SELECT CLASS & FETCH STUDENTS ---
  const handleClassClick = async (cls) => {
    setSelectedClass(cls);
    setLoading(true);
    const date = new Date().toISOString().split('T')[0];
    
    try {
      const res = await axios.get(`http://localhost:5000/api/staff/class-students/${cls._id}?date=${date}&hour=${hour}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const initializedStudents = res.data.map(s => ({
        ...s,
        status: s.status || 'present'
      }));
      
      setStudents(initializedStudents);
    } catch (err) {
      alert("Failed to load students");
    } finally {
      setLoading(false);
    }
  };

  // --- 3. MARK ATTENDANCE ---
  const toggleStatus = (studentId, newStatus) => {
    setStudents(prev => prev.map(s => 
      s.studentId === studentId ? { ...s, status: newStatus } : s
    ));
  };

  // --- 4. SUBMIT ATTENDANCE ---
  const handleSubmit = async () => {
    setLoading(true);
    const date = new Date().toISOString().split('T')[0];
    
    const payload = {
      classId: selectedClass._id,
      date: date,
      hour: hour,
      records: students.map(s => ({ studentId: s.studentId, status: s.status }))
    };

    try {
      await axios.post('http://localhost:5000/api/staff/submit-attendance', payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessage('Attendance Submitted Successfully!');
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      alert("Failed to submit attendance");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div>
          <h1>Staff Dashboard</h1>
          <p className="sub-text">Attendance Portal</p>
        </div>
        <div style={{display:'flex', gap:'10px'}}>
          
          {/* (!!!) BUTTON VISIBLE ONLY TO TUTORS (!!!) */}
          {roles.includes('tutor') && (
            <button 
              onClick={() => navigate('/admin-dashboard')} 
              className="logout-btn" 
              style={{background: '#00b894'}}
            >
              Manage My Class
            </button>
          )}
          
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </div>
      </header>

      {/* FILTER SECTION */}
      {!selectedClass && (
        <div className="filter-card">
          <h3>Find Class</h3>
          <form onSubmit={handleSearch} className="filter-form">
            <input type="text" placeholder="Dept (e.g. Computer Science)" value={filters.department} onChange={e => setFilters({...filters, department: e.target.value})} />
            <select value={filters.year} onChange={e => setFilters({...filters, year: e.target.value})}>
              <option value="">Year</option>
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
            </select>
            <select value={filters.shift} onChange={e => setFilters({...filters, shift: e.target.value})}>
              <option value="">Shift</option>
              <option value="1">1</option>
              <option value="2">2</option>
            </select>
            <button type="submit" className="search-btn">Search</button>
          </form>

          <div className="class-grid">
            {classes.map(cls => (
              <div key={cls._id} className="class-card" onClick={() => handleClassClick(cls)}>
                <h4>{cls.year} {cls.degreeType} {cls.department}</h4>
                <p>Shift {cls.shift} | {cls.medium}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MARKING SECTION */}
      {selectedClass && (
        <div className="marking-section">
          <div className="marking-header">
            <button className="back-link" onClick={() => setSelectedClass(null)}>← Back</button>
            <div>
              <h2>{selectedClass.year} {selectedClass.department}</h2>
              <div className="hour-selector">
                <label>Select Hour:</label>
                <select value={hour} onChange={e => { setHour(e.target.value); handleClassClick(selectedClass); }}>
                  {[1,2,3,4,5].map(h => <option key={h} value={h}>Hour {h}</option>)}
                </select>
              </div>
            </div>
          </div>

          {message && <div className="success-msg">{message}</div>}

          <div className="table-responsive">
            <table className="attendance-table">
              <thead>
                <tr>
                  <th>Reg No</th>
                  <th>Name</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {students.map(s => (
                  <tr key={s.studentId}>
                    <td>{s.registerNumber}</td>
                    <td>{s.name}</td>
                    <td className="actions">
                      <button className={`status-btn p ${s.status === 'present' ? 'active' : ''}`} onClick={() => toggleStatus(s.studentId, 'present')}>P</button>
                      <button className={`status-btn a ${s.status === 'absent' ? 'active' : ''}`} onClick={() => toggleStatus(s.studentId, 'absent')}>A</button>
                      <button className={`status-btn od ${s.status === 'on_duty' ? 'active' : ''}`} onClick={() => toggleStatus(s.studentId, 'on_duty')}>OD</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <button className="submit-attendance-btn" onClick={handleSubmit} disabled={loading}>
            {loading ? 'Submitting...' : 'Submit Attendance'}
          </button>
        </div>
      )}
    </div>
  );
};

export default StaffDashboard;