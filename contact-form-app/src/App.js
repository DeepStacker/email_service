// src/App.js
import React, { useState, useEffect } from 'react';
import './App.css';
import Header from './components/Header';
import StepIndicator from './components/StepIndicator';
import ContactForm from './components/ContactForm';
import OtpVerification from './components/OtpVerification';
import SuccessStep from './components/SuccessStep';
import AlertContainer from './components/AlertContainer';
import DebugPanel from './components/DebugPanel';
// Base URL for the API

const API_BASE_URL = "https://es-h4c2.onrender.com";

function App() {
  const [currentStep, setCurrentStep] = useState(1);
  const [contactData, setContactData] = useState({});
  const [alert, setAlert] = useState({ message: '', type: '' });
  const [loading, setLoading] = useState({ sendOtp: false, verifyOtp: false });
  const [debugInfo, setDebugInfo] = useState({});
  const [showDebug, setShowDebug] = useState(false);
  const [submissionDetails, setSubmissionDetails] = useState({});
  const [result, setResult] = useState({});
  const isDebugMode = true; // Set to false for production

  useEffect(() => {
    if (isDebugMode) {
      loadDebugInfo();
    }
  }, []);

  const showAlert = (message, type = 'info') => {
    setAlert({ message, type });
    if (type === 'success') {
      setTimeout(() => setAlert({ message: '', type: '' }), 5000);
    }
  };

  const goToStep = (step) => {
    setCurrentStep(step);
  };

  const loadDebugInfo = async () => {
    if (!isDebugMode) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/contact/debug`);
      const result = await response.json();
      setDebugInfo(result.data || {});
    } catch (error) {
      console.error("Debug info error:", error);
    }
  };

  const handleContactSubmit = async (formData) => {
    const data = {
      name: formData.name,
      email: formData.email,
      phone: formData.phone,
      company: formData.company || null,
      subject: formData.subject,
      message: formData.message,
    };

    setContactData(data);
    setLoading({ ...loading, sendOtp: true });

    try {
      const response = await fetch(`${API_BASE_URL}/contact/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      const result = await response.json();

      if (result.success) {
        setResult(result);
        showAlert(`OTP sent successfully to ${data.email}`, 'success');
        
        if (isDebugMode && result.data?.otp_for_testing) {
          showAlert(`Debug: OTP is ${result.data.otp_for_testing}`, 'info');
        }
        
        goToStep(2);
      } else {
        showAlert(result.message || 'Failed to send OTP', 'error');
      }
    } catch (error) {
      console.error('Error:', error);
      showAlert('Network error. Please check your connection.', 'error');
    } finally {
      setLoading({ ...loading, sendOtp: false });
    }
  };

  const handleOtpVerify = async (otp) => {
    if (otp.length !== 6) {
      showAlert('Please enter a 6-digit OTP', 'error');
      return;
    }

    setLoading({ ...loading, verifyOtp: true });

    try {
      const verifyResponse = await fetch(`${API_BASE_URL}/contact/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: contactData.email, otp }),
      });

      const verifyResult = await verifyResponse.json();

      if (verifyResult.success) {
        const submitResponse = await fetch(`${API_BASE_URL}/contact/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ contact_data: contactData, otp }),
        });

        const submitResult = await submitResponse.json();

        if (submitResult.success) {
          setSubmissionDetails(submitResult.data);
          goToStep(3);
        } else {
          showAlert(submitResult.message || 'Failed to submit contact form', 'error');
        }
      } else {
        showAlert(verifyResult.message || 'Invalid OTP', 'error');
      }
    } catch (error) {
      console.error('Error:', error);
      showAlert('Network error. Please try again.', 'error');
    } finally {
      setLoading({ ...loading, verifyOtp: false });
    }
  };

  const resendOtp = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/contact/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(contactData),
      });

      const result = await response.json();

      if (result.success) {
        showAlert('OTP resent successfully', 'success');
        
        if (isDebugMode && result.data?.otp_for_testing) {
          showAlert(`Debug: New OTP is ${result.data.otp_for_testing}`, 'info');
        }
      } else {
        showAlert(result.message || 'Failed to resend OTP', 'error');
      }
    } catch (error) {
      console.error('Error:', error);
      showAlert('Failed to resend OTP', 'error');
    }
  };

  const resetForm = () => {
    setContactData({});
    setAlert({ message: '', type: '' });
    setSubmissionDetails({});
    goToStep(1);
  };

  return (
    <div className="container">
      <Header />
      <div className="form-container">
        <StepIndicator currentStep={currentStep} />
        <AlertContainer alert={alert} />
        
        {currentStep === 1 && (
          <ContactForm 
            onSubmit={handleContactSubmit} 
            loading={loading.sendOtp} 
          />
        )}
        
        {currentStep === 2 && (
          <OtpVerification 
            onVerify={handleOtpVerify}
            onResend={resendOtp}
            onBack={() => goToStep(1)}
            loading={loading.verifyOtp}
            email={contactData.email}
            initialOtp={result.data.otp_for_testing || ''}
          />
        )}
        
        {currentStep === 3 && (
          <SuccessStep 
            submissionDetails={submissionDetails}
            onReset={resetForm}
          />
        )}
        
        {isDebugMode && (
          <DebugPanel 
            debugInfo={debugInfo}
            showDebug={showDebug}
            onToggle={() => setShowDebug(!showDebug)}
            onRefresh={loadDebugInfo}
          />
        )}
      </div>
    </div>
  );
}

export default App;
