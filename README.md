# Remnow Invoice & Quotation Generator

A Flask-based web application for generating quotations and invoices with PDF export functionality.

## Features

- Create quotations/invoices with customizable fields
- Dynamic item table with add/remove functionality
- Payment information management
- PDF generation using HTML template
- PostgreSQL database for data persistence
- Beautiful UI built with DaisyUI and Tailwind CSS

## Setup Instructions

### 1. Install Dependencies

**First, install wkhtmltopdf:**

**macOS:**
```bash
brew install wkhtmltopdf
```

**Ubuntu/Debian:**
```bash
sudo apt-get install wkhtmltopdf
```

**Windows:**
Download and install from: https://wkhtmltopdf.org/downloads.html

**Then install Python packages:**
```bash
pip install -r requirements.txt
```

### 2. Set Up PostgreSQL Database

Create a PostgreSQL database:

```bash
createdb remnow_invoice
```

Or using psql:

```sql
CREATE DATABASE remnow_invoice;
```

### 3. Configure Environment Variables

Set your database connection string as an environment variable:

**macOS/Linux:**
```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/remnow_invoice"
export SECRET_KEY="your-secret-key-here"
```

**Windows:**
```cmd
set DATABASE_URL=postgresql://username:password@localhost:5432/remnow_invoice
set SECRET_KEY=your-secret-key-here
```

Or create a `.env` file (if using python-dotenv):
```
DATABASE_URL=postgresql://username:password@localhost:5432/remnow_invoice
SECRET_KEY=your-secret-key-here
```

**Default connection (if DATABASE_URL not set):**
- Database: `remnow_invoice`
- User: `postgres`
- Password: `postgres`
- Host: `localhost`
- Port: `5432`

### 4. Initialize Database Tables

```bash
python init_db.py
```

Or the tables will be created automatically when you first run the app.

### 5. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Usage

1. Fill in the quotation form:
   - Quotation No
   - Date
   - To (Address)
   - Currency
   - Add items (Description, HSN Code, Month, Rate, Amount)
   - Payment Information (Bank Name, Branch Name, Account Name, Account Number, IFSC Code)

2. Click "Generate PDF" to create and download the PDF

## Project Structure

```
RemnowInvoice/
├── app.py                 # Main Flask application
├── index.html            # PDF template
├── templates/
│   └── form.html         # Form UI with DaisyUI
├── assets/               # Images and static files
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Technologies Used

- Flask - Web framework
- PostgreSQL - Database
- SQLAlchemy - ORM
- pdfkit + wkhtmltopdf - PDF generation
- DaisyUI - UI component library
- Tailwind CSS - Styling

