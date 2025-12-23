#!/usr/bin/env python3
"""
Complete database fix script.
This will add all missing columns and verify the database structure.
"""

from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        print("=== FIXING DATABASE STRUCTURE ===")
        
        # First, let's check what columns exist
        print("\n1. Checking existing columns in users table...")
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND table_schema = 'public'
            ORDER BY column_name;
        """))
        user_columns = [row[0] for row in result.fetchall()]
        print(f"Existing user columns: {user_columns}")
        
        print("\n2. Checking existing columns in quotations table...")
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'quotations' AND table_schema = 'public'
            ORDER BY column_name;
        """))
        quotation_columns = [row[0] for row in result.fetchall()]
        print(f"Existing quotation columns: {quotation_columns}")
        
        # Add missing columns to users table
        print("\n3. Adding missing columns to users table...")
        missing_user_columns = [
            ('bank_name', 'VARCHAR(200)'),
            ('branch_name', 'VARCHAR(200)'),
            ('account_name', 'VARCHAR(200)'),
            ('account_number', 'VARCHAR(50)'),
            ('ifsc_code', 'VARCHAR(20)'),
            ('gpay_phonepe', 'VARCHAR(50)')
        ]
        
        for col_name, col_type in missing_user_columns:
            if col_name not in user_columns:
                print(f"Adding {col_name} to users table...")
                db.session.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};"))
            else:
                print(f"{col_name} already exists in users table")
        
        # Add missing columns to quotations table
        print("\n4. Adding missing columns to quotations table...")
        missing_quotation_columns = [
            ('client_phone', 'VARCHAR(50)'),
            ('share_token', 'VARCHAR(100)'),
            ('voided', 'BOOLEAN DEFAULT FALSE NOT NULL'),
            ('sub_total', 'NUMERIC(10, 2)'),
            ('gst_amount', 'NUMERIC(10, 2)')
        ]
        
        for col_name, col_type in missing_quotation_columns:
            if col_name not in quotation_columns:
                print(f"Adding {col_name} to quotations table...")
                if col_name == 'voided':
                    # Special handling for voided column
                    db.session.execute(text(f"ALTER TABLE quotations ADD COLUMN {col_name} BOOLEAN DEFAULT FALSE;"))
                    db.session.execute(text("UPDATE quotations SET voided = FALSE WHERE voided IS NULL;"))
                    db.session.execute(text("ALTER TABLE quotations ALTER COLUMN voided SET NOT NULL;"))
                else:
                    db.session.execute(text(f"ALTER TABLE quotations ADD COLUMN {col_name} {col_type};"))
            else:
                print(f"{col_name} already exists in quotations table")
        
        # Update existing quotations with default values
        print("\n5. Updating existing quotations with default values...")
        db.session.execute(text("""
            UPDATE quotations 
            SET sub_total = total_amount,
                gst_amount = 0
            WHERE sub_total IS NULL;
        """))
        
        db.session.commit()
        print("\n=== DATABASE STRUCTURE FIXED SUCCESSFULLY! ===")
        
        # Test the payment info endpoint
        print("\n6. Testing current user payment info...")
        from flask_login import current_user
        
        # We need to simulate a user context, so let's just check if we can query users
        users = db.session.execute(text("SELECT id, name, email, bank_name FROM users LIMIT 1;")).fetchall()
        if users:
            user = users[0]
            print(f"Sample user: ID={user[0]}, Name={user[1]}, Email={user[2]}, Bank={user[3] or 'None'}")
        
        print("\n=== ALL DONE! Restart your Flask app now. ===")
        
    except Exception as e:
        db.session.rollback()
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
