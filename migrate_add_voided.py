from app import app, db
from models import Quotation

def migrate():
    with app.app_context():
        try:
            # Add voided column
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE quotation ADD COLUMN voided BOOLEAN DEFAULT FALSE'))
                conn.commit()
            
            print("✓ Added 'voided' column to quotation table")
            
        except Exception as e:
            if 'duplicate column name' in str(e).lower() or 'already exists' in str(e).lower():
                print("✓ Column 'voided' already exists")
            else:
                print(f"Error: {e}")
                raise

if __name__ == '__main__':
    migrate()
    print("\nMigration completed successfully!")
