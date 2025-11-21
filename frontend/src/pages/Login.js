import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import './Login.css';

const Login = () => {
  const [formData, setFormData] = useState({
    identifier: '', // Handles Username OR Register No
    password: ''    // Handles Password OR DOB
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Use the new Unified Login Endpoint
      const response = await axios.post('http://localhost:5000/api/login', {
        identifier: formData.identifier,
        password: formData.password
      });
      
      // Save token
      localStorage.setItem('token', response.data.access_token);
      
      // Redirect based on the role returned by backend
      const role = response.data.role;
      
      if (role === 'student') {
        navigate('/student-dashboard');
      } else if (role === 'superadmin') {
        // We haven't built this page yet, but logic is ready
        navigate('/admin-dashboard');
      } else {
        // For Tutors and Faculty
        navigate('/staff-dashboard'); 
      }

    } catch (err) {
      setError(err.response?.data?.error || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h2>Attendance System</h2>
        <p className="subtitle">Please sign in to continue</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>ID / Username</label>
            <input 
              type="text" 
              name="identifier" 
              placeholder="Username (Staff) or Reg No. (Students)"
              value={formData.identifier}
              onChange={handleChange}
              required 
            />
          </div>
          
          <div className="form-group">
            <label>Password</label>
            <input 
              type="password" 
              name="password" 
              placeholder="Password or D.O.B (YYYY-MM-DD)"
              value={formData.password}
              onChange={handleChange}
              required 
            />
          </div>

          {error && <div className="error-msg">{error}</div>}

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;