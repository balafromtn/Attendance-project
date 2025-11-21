import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css'; // Reuse our common CSS
import './StaffDashboard.css'; // Specific styles for staff

const StaffDashboard = () => {
  const navigate = useNavigate();
  const [schedule, setSchedule] = useState([]);
  const [today, setToday] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedClass, setSelectedClass] = useState(null); // To track which class is clicked
  const [students, setStudents] = useState([]);
  const [error, setError] = useState('');

  const token = localStorage.getItem('token');

  // 1. Fetch Schedule on Load
  useEffect(() => {
    if (!token) {
      navigate('/');
      return;
    }
    fetchSchedule();
  }, [navigate, token]);

  const fetchSchedule = async () => {
    try {
      const res = await axios.get('http://localhost:5000/api/faculty/my-schedule', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSchedule(res.data.schedule);
      setToday(res.data.today);
      setLoading(false);
    } catch (err) {
      setError('Failed to load schedule.');
      setLoading(false);
    }
  };

  // 2. Handle Class Click (Fetch Students)
  const handleClassClick = async (classItem) => {
    // Set selected class (including the specific hour!)
    setSelectedClass(classItem); 
    setLoading(true);
    
    try {
      const res = await axios.get(`http://localhost:5000/api/faculty/class-list/${classItem.classId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStudents(res.data);
      setLoading(false);
    } catch (err) {
      alert('Failed to load student list');
      setLoading(false);
      setSelectedClass(null);
    }
  };

  // 3. Handle Marking Attendance
  const markAttendance = async (studentId, status) => {
    try {
      await axios.post('http://localhost:5000/api/faculty/mark-attendance', {
        studentId: studentId,
        hour: selectedClass.hour, // We need the hour from the selected class
        status: status
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Optimistically update the UI so it feels fast
      setStudents(prevStudents => 
        prevStudents.map(s => {
          if (s.studentId === studentId) {
            // Update the nested attendance object for the specific hour
            return {
              ...s,
              attendance: {
                ...s.attendance,
                [`hour_${selectedClass.hour}`]: status
              }
            };
          }
          return s;
        })
      );

    } catch (err) {
      alert(err.response?.data?.error || 'Failed to mark attendance');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  // --- RENDER ---
  if (loading && !students.length) return <div className="loading-screen">Loading...</div>;

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div>
          <h1>Staff Dashboard</h1>
          <p className="sub-text">Date: {today}</p>
        </div>
        <button onClick={handleLogout} className="logout-btn">Logout</button>
      </header>

      {error && <div className="error-msg">{error}</div>}

      {/* VIEW 1: THE SCHEDULE (Show if no class selected) */}
      {!selectedClass && (
        <div className="schedule-section">
          <h2>Your Schedule Today</h2>
          {schedule.length === 0 ? (
            <p className="no-data">No classes scheduled for today.</p>
          ) : (
            <div className="class-grid">
              {schedule.map((item, index) => (
                <div key={index} className="class-card" onClick={() => handleClassClick(item)}>
                  <div className="hour-badge">Hour {item.hour}</div>
                  <h3>{item.className}</h3>
                  <p>Click to mark attendance</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* VIEW 2: THE STUDENT LIST (Show if class is selected) */}
      {selectedClass && (
        <div className="attendance-section">
          <button className="back-btn" onClick={() => {setSelectedClass(null); setStudents([]);}}>
            ← Back to Schedule
          </button>
          
          <h2>Marking: {selectedClass.className} (Hour {selectedClass.hour})</h2>
          
          <div className="table-responsive">
            <table className="attendance-table">
              <thead>
                <tr>
                  <th>Reg No</th>
                  <th>Name</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {students.map((student) => {
                  const currentStatus = student.attendance[`hour_${selectedClass.hour}`];
                  return (
                    <tr key={student.studentId}>
                      <td>{student.registerNumber}</td>
                      <td>{student.name}</td>
                      <td className="action-cell">
                        <button 
                          className={`status-btn present ${currentStatus === 'present' ? 'active' : ''}`}
                          onClick={() => markAttendance(student.studentId, 'present')}
                        >
                          P
                        </button>
                        <button 
                          className={`status-btn absent ${currentStatus === 'absent' ? 'active' : ''}`}
                          onClick={() => markAttendance(student.studentId, 'absent')}
                        >
                          A
                        </button>
                        <button 
                          className={`status-btn onduty ${currentStatus === 'on_duty' ? 'active' : ''}`}
                          onClick={() => markAttendance(student.studentId, 'on_duty')}
                        >
                          OD
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default StaffDashboard;