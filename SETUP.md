# Remnow Invoice Generator

A professional invoice and quotation generator with user authentication and PDF export capabilities.

## Features

- ✅ **User Authentication** - Secure login and registration system
- ✅ **Invoice Generation** - Create professional invoices with customizable templates
- ✅ **PDF Export** - Generate PDF invoices for download
- ✅ **Multi-Currency Support** - USD, INR, EUR, GBP
- ✅ **User Dashboard** - Manage all your invoices in one place
- ✅ **Responsive Design** - Works on desktop, tablet, and mobile

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install wkhtmltopdf (Required for PDF generation)

**macOS:**
```bash
brew install wkhtmltopdf
```

**Ubuntu/Debian:**
```bash
sudo apt-get install wkhtmltopdf
```

### 3. Set up PostgreSQL Database

Make sure PostgreSQL is running and create a database:

```bash
createdb remnow_invoice
```

Or update the database URL in `app.py` if using different credentials.

### 4. Update Database Schema

Run the migration script to create tables:

```bash
python update_db.py
```

### 5. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## First Time Usage

1. Navigate to `http://localhost:5000`
2. You'll be redirected to the login page
3. Click "Sign up" to create a new account
4. After registration, you'll be automatically logged in
5. Start creating invoices!

## Project Structure

```
RemnowInvoice/
├── app.py                 # Main Flask application
├── update_db.py          # Database migration script
├── requirements.txt      # Python dependencies
├── index.html           # Invoice template
├── assets/              # Static files (logos, etc.)
├── templates/           # HTML templates
│   ├── login.html       # Login page
│   ├── register.html    # Registration page
│   └── form.html        # Invoice creation form
└── README.md           # This file
```

## Security Notes

- Change the `SECRET_KEY` in `app.py` for production use
- Use environment variables for sensitive configuration
- Enable HTTPS in production
- Set up proper database backups

## Technologies Used

- **Backend:** Flask, SQLAlchemy, Flask-Login
- **Frontend:** HTML, Tailwind CSS, DaisyUI
- **Database:** PostgreSQL
- **PDF Generation:** pdfkit, wkhtmltopdf

## License

© 2025 Remnow Solutions. All rights reserved.
