// src/components/StepIndicator.js
import React from 'react';

const StepIndicator = ({ currentStep }) => {
  const steps = [
    { number: 1, label: 'Contact Info' },
    { number: 2, label: 'Verify Email' },
    { number: 3, label: 'Complete' }
  ];

  return (
    <div className="step-indicator">
      {steps.map((step) => (
        <div 
          key={step.number}
          className={`step-item ${
            currentStep === step.number ? 'active' : 
            currentStep > step.number ? 'completed' : ''
          }`}
        >
          <div className="step-number">{step.number}</div>
          <span>{step.label}</span>
        </div>
      ))}
    </div>
  );
};

export default StepIndicator;
