import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css'; // We will create this common CSS file

const StudentDashboard = () => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [attendance, setAttendance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Function to handle Logout
  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  useEffect(() => {
    const fetchData = async () => {
      const token = localStorage.getItem('token');
      
      if (!token) {
        navigate('/');
        return;
      }

      try {
        // Configure headers with the token
        const config = {
          headers: { Authorization: `Bearer ${token}` }
        };

        // Fetch Profile and Attendance in parallel
        const [profileRes, attendanceRes] = await Promise.all([
          axios.get('http://localhost:5000/api/student/me', config),
          axios.get('http://localhost:5000/api/student/my-attendance', config)
        ]);

        setProfile(profileRes.data);
        setAttendance(attendanceRes.data);
        setLoading(false);

      } catch (err) {
        console.error(err);
        setError('Failed to load data. Session might be expired.');
        // Optional: Auto-logout on error
        // handleLogout(); 
        setLoading(false);
      }
    };

    fetchData();
  }, [navigate]);

  if (loading) return <div className="loading-screen">Loading Dashboard...</div>;
  if (error) return <div className="error-screen">{error} <button onClick={handleLogout}>Go Back</button></div>;

  return (
    <div className="dashboard-container">
      {/* Header Section */}
      <header className="dashboard-header">
        <div>
          <h1>Welcome, {profile?.name}</h1>
          <p className="sub-text">{profile?.registerNumber} | {profile?.classInfo?.year} Year {profile?.classInfo?.department}</p>
        </div>
        <button onClick={handleLogout} className="logout-btn">Logout</button>
      </header>

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card primary">
          <h3>Total Percentage</h3>
          <div className="big-number">{attendance?.stats?.percentage}%</div>
        </div>
        <div className="stat-card">
          <h3>Present Hours</h3>
          <div className="number">{attendance?.stats?.totalPresent}</div>
        </div>
        <div className="stat-card">
          <h3>Absent Hours</h3>
          <div className="number">{attendance?.stats?.totalAbsent}</div>
        </div>
        <div className="stat-card">
          <h3>On Duty</h3>
          <div className="number">{attendance?.stats?.totalOnDuty}</div>
        </div>
      </div>

      {/* Attendance History Table */}
      <div className="table-section">
        <h2>Attendance History</h2>
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Hour</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {attendance?.records?.length > 0 ? (
                attendance.records.map((record) => (
                  <tr key={record._id}>
                    <td>{record.date}</td>
                    <td>{record.hour}</td>
                    <td>
                      <span className={`status-badge ${record.status}`}>
                        {record.status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="3" style={{textAlign: 'center'}}>No attendance records found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default StudentDashboard;