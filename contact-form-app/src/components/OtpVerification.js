// src/components/OtpVerification.js
import React, { useState } from 'react';

const OtpVerification = ({ onVerify, onResend, onBack, loading, email, initialOtp }) => {
  const [otp, setOtp] = useState(initialOtp);

  const handleSubmit = (e) => {
    e.preventDefault();
    onVerify(otp);
  };

  const handleOtpChange = (e) => {
    const value = e.target.value.replace(/\D/g, '');
    setOtp(value);
  };

  return (
    <div className="step active">
      <div className="otp-container">
        <h2>Email Verification</h2>
        <p>We've sent a 6-digit OTP to your email address.</p>
        <p>Please enter the code below to verify your email.</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="otp">Enter OTP Code</label>
            <input
              type="text"
              id="otp"
              name="otp"
              className="otp-input"
              maxLength="6"
              placeholder="000000"
              value={otp}
              onChange={handleOtpChange}
              required
            />
          </div>

          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
            <button type="button" className="btn btn-secondary" onClick={onBack}>
              Back
            </button>
            <button type="submit" className="btn" disabled={loading}>
              <span className="btn-text">
                {loading ? (
                  <>
                    <span className="loading"></span>
                    Processing...
                  </>
                ) : (
                  'Verify OTP'
                )}
              </span>
            </button>
          </div>
        </form>

        <p style={{ marginTop: '20px' }}>
          Didn't receive the code?{' '}
          <button
            type="button"
            onClick={onResend}
            style={{
              background: 'none',
              border: 'none',
              color: '#667eea',
              cursor: 'pointer',
              textDecoration: 'underline'
            }}
          >
            Resend OTP
          </button>
        </p>
      </div>
    </div>
  );
};

export default OtpVerification;
