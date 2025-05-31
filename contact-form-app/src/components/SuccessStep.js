// src/components/SuccessStep.js
import React from 'react';

const SuccessStep = ({ submissionDetails, onReset }) => (
  <div className="step active">
    <div style={{ textAlign: 'center', padding: '40px' }}>
      <div style={{ fontSize: '4rem', color: '#28a745', marginBottom: '20px' }}>
        ✅
      </div>
      <h2>Thank You!</h2>
      <p>
        Your message has been sent successfully. We'll get back to you
        within 24-48 hours.
      </p>

      <div
        style={{
          background: '#f8f9fa',
          padding: '20px',
          borderRadius: '8px',
          margin: '20px 0',
          textAlign: 'left'
        }}
      >
        <h4>Submission Details:</h4>
        <p><strong>Submission ID:</strong> {submissionDetails.submission_id}</p>
        <p><strong>Email:</strong> {submissionDetails.email}</p>
        <p><strong>Status:</strong> Successfully submitted</p>
        <p><strong>Next Steps:</strong> You will receive a confirmation email shortly.</p>
      </div>

      <button type="button" className="btn" onClick={onReset}>
        Send Another Message
      </button>
    </div>
  </div>
);

export default SuccessStep;
