# Advanced Email Management API and Contact Form

This project consists of two main parts:

1.  **Advanced Email Management API:** A FastAPI application for sending and receiving emails with advanced features.
2.  **Contact Form:** A React application that uses the Advanced Email Management API to send contact form submissions with OTP verification.

## Advanced Email Management API

### Overview

The Advanced Email Management API is a FastAPI application that provides a comprehensive solution for sending and receiving emails. It includes features such as:

*   Sending emails with attachments
*   Sending bulk emails
*   Receiving and searching emails
*   Email management (read, delete, move)
*   Advanced configuration
*   Connection testing

### Technologies Used

*   FastAPI
*   Python 3.9+
*   smtplib
*   imaplib
*   pydantic
*   python-dotenv

### Setup

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd Email_configuration
    ```
2.  **Create a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Linux/macOS
    venv\Scripts\activate.bat  # On Windows
    ```
3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**

    Create a `.env` file in the root directory and set the following environment variables:

    ```
    EMAIL_USER=<your_email_address>
    EMAIL_PASS=<your_email_password>
    ADMIN_EMAIL=<admin_email_address> # Optional, for receiving contact form submissions
    SMTP_SERVER=<smtp_server_address> # Optional, defaults to smtp.gmail.com
    SMTP_PORT=<smtp_server_port> # Optional, defaults to 587
    IMAP_SERVER=<imap_server_address> # Optional, defaults to imap.gmail.com
    IMAP_PORT=<imap_server_port> # Optional, defaults to 993
    ```

    **Note:** For Gmail, you may need to enable "Less secure app access" or use an "App Password".

5.  **Run the API:**

    ```bash
    python main.py
    ```

    The API will be accessible at `http://localhost:8000`.

### Endpoints

*   `/`: Health check and API information
*   `/email/send`: Send a single email
*   `/email/send-with-attachments`: Send an email with attachments
*   `/email/send-bulk`: Send bulk emails
*   `/email/folders`: Get list of email folders
*   `/email/list`: Get emails from a folder
*   `/email/search`: Search emails
*   `/email/unread`: Get unread emails
*   `/email/mark-read`: Mark emails as read
*   `/email/delete`: Delete emails
*   `/email/move`: Move emails between folders
*   `/email/test-connections`: Test SMTP and IMAP connections
*   `/email/config`: Get email configuration
*   `/email/stats`: Get email statistics

### Testing

The API includes several endpoints for testing purposes:

*   `/contact/test-email`: Test email service
*   `/contact/debug`: Debug information (testing only)
*   `/contact/submissions`: Get all contact submissions (testing only)

## Contact Form

### Overview

The Contact Form is a React application that allows users to submit contact form submissions with OTP verification. It uses the Advanced Email Management API to send the submissions.

### Technologies Used

*   React
*   JavaScript
*   CSS

### Setup

1.  **Navigate to the `contact-form-app` directory:**

    ```bash
    cd contact-form-app
    ```

2.  **Install dependencies:**

    ```bash
    npm install
    ```

3.  **Configure the API base URL:**

    In `src/App.js`, set the `API_BASE_URL` variable to the address of your Advanced Email Management API.

    ```javascript
    const API_BASE_URL = "http://localhost:8000";
    ```

4.  **Run the application:**

    ```bash
    npm start
    ```

    The application will be accessible at `http://localhost:3000`.

### Components

*   `Header`: Displays the header of the application.
*   `StepIndicator`: Indicates the current step in the form.
*   `ContactForm`: Displays the contact form.
*   `OtpVerification`: Displays the OTP verification form.
*   `SuccessStep`: Displays the success message after submitting the form.
*   `AlertContainer`: Displays alerts and messages.
*   `DebugPanel`: Displays debug information (only in development mode).

### Debug Mode

The application includes a debug mode that can be enabled by setting the `isDebugMode` variable to `true` in `src/App.js`. In debug mode, the application will display the OTP in the alert message and provide access to the debug panel.

## License

This project is licensed under the MIT License.