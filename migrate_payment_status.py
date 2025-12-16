"""
Migration script to add payment_status column to quotations table
Run this script once to update your existing database
"""
from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            # Check if the column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='quotations' AND column_name='payment_status'
            """))
            
            if result.fetchone() is None:
                # Add the payment_status column with default value 'unpaid'
                db.session.execute(text("""
                    ALTER TABLE quotations 
                    ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid'
                """))
                db.session.commit()
                print("✓ Successfully added payment_status column to quotations table")
                print("✓ All existing invoices have been set to 'unpaid' status by default")
            else:
                print("✓ Column payment_status already exists in quotations table")
                
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error during migration: {e}")
            print("If you're using SQLite, try this alternative:")
            print("1. Backup your database first")
            print("2. Delete the database file")
            print("3. Run init_db.py to recreate it with the new schema")

if __name__ == '__main__':
    print("Starting database migration...")
    migrate()
