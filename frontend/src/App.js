import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import StudentDashboard from './pages/StudentDashboard'; // Import the new page

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Login />} />
        
        {/* Connect the real Student Dashboard */}
        <Route path="/student-dashboard" element={<StudentDashboard />} />
        
        <Route path="/staff-dashboard" element={<h1>Staff Dashboard Coming Soon</h1>} />
        <Route path="/admin-dashboard" element={<h1>Admin Dashboard Coming Soon</h1>} />
      </Routes>
    </Router>
  );
}

export default App;