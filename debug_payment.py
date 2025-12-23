#!/usr/bin/env python3
"""
Debug script to check and fix payment info storage.
"""

from app import app, db, User
from sqlalchemy import text

with app.app_context():
    print("=== DEBUGGING PAYMENT INFO ===\n")
    
    # 1. Check database columns
    print("1. Checking users table columns...")
    result = db.session.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'users' AND table_schema = 'public'
        ORDER BY column_name;
    """))
    columns = {row[0]: row[1] for row in result.fetchall()}
    
    required_columns = ['bank_name', 'branch_name', 'account_name', 'account_number', 'ifsc_code', 'gpay_phonepe']
    missing_columns = []
    
    for col in required_columns:
        if col in columns:
            print(f"   ✓ {col} exists ({columns[col]})")
        else:
            print(f"   ✗ {col} MISSING!")
            missing_columns.append(col)
    
    # 2. Add missing columns if any
    if missing_columns:
        print(f"\n2. Adding missing columns: {missing_columns}")
        for col in missing_columns:
            try:
                db.session.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(200);"))
                print(f"   Added {col}")
            except Exception as e:
                print(f"   Error adding {col}: {e}")
        db.session.commit()
        print("   Columns added!")
    else:
        print("\n2. All columns exist!")
    
    # 3. Check all users' payment info
    print("\n3. Checking users' payment info...")
    users = User.query.all()
    for user in users:
        print(f"\n   User: {user.name} ({user.email})")
        print(f"   - bank_name: '{user.bank_name or 'EMPTY'}'")
        print(f"   - branch_name: '{user.branch_name or 'EMPTY'}'")
        print(f"   - account_name: '{user.account_name or 'EMPTY'}'")
        print(f"   - account_number: '{user.account_number or 'EMPTY'}'")
        print(f"   - ifsc_code: '{user.ifsc_code or 'EMPTY'}'")
        print(f"   - gpay_phonepe: '{user.gpay_phonepe or 'EMPTY'}'")
    
    print("\n=== DONE ===")
    print("\nIf fields show 'EMPTY', the data was NOT saved to the database.")
    print("Go to Settings, fill the fields, click 'Save Payment Info', then run this script again.")

