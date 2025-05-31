// src/components/DebugPanel.js
import React from 'react';

const DebugPanel = ({ debugInfo, showDebug, onToggle, onRefresh }) => (
  <div className="debug-panel">
    <h3>Debug Information (Testing Mode)</h3>
    <button
      type="button"
      className="btn"
      onClick={onToggle}
      style={{ width: 'auto', marginBottom: '15px' }}
    >
      Toggle Debug Info
    </button>
    
    {showDebug && (
      <div>
        <button
          type="button"
          className="btn"
          onClick={onRefresh}
          style={{ width: 'auto', marginBottom: '15px', marginLeft: '10px' }}
        >
          Refresh Debug Info
        </button>
        
        <div className="debug-info">
          <strong>API Status:</strong> Connected
        </div>
        <div className="debug-info">
          <strong>Stored OTPs:</strong> {debugInfo.otp_store_count || 0}
        </div>
        <div className="debug-info">
          <strong>Rate Limits:</strong> {debugInfo.rate_limit_count || 0}
        </div>
        <div className="debug-info">
          <strong>Submissions:</strong> {debugInfo.submissions_count || 0}
        </div>
      </div>
    )}
  </div>
);

export default DebugPanel;
