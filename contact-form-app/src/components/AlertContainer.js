// src/components/AlertContainer.js
import React from 'react';

const AlertContainer = ({ alert }) => {
  if (!alert.message) return null;

  return (
    <div className={`alert alert-${alert.type}`}>
      {alert.message}
    </div>
  );
};

export default AlertContainer;
