#!/usr/bin/env python3
"""
Migration script to add GST fields to quotations table
Run this script to add gst_type, cgst_rate, sgst_rate, and igst_rate columns
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

load_dotenv()

def migrate():
    # Get database connection string
    db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI', 'postgresql://postgres:12345@localhost:5432/remnow_invoice')
    
    # Parse connection string
    # Format: postgresql://user:password@host:port/database
    parts = db_uri.replace('postgresql://', '').split('/')
    db_name = parts[1] if len(parts) > 1 else 'remnow_invoice'
    auth_part = parts[0] if parts else ''
    
    auth_parts = auth_part.split('@')
    if len(auth_parts) == 2:
        user_pass = auth_parts[0].split(':')
        user = user_pass[0] if user_pass else 'postgres'
        password = user_pass[1] if len(user_pass) > 1 else ''
        host_port = auth_parts[1].split(':')
        host = host_port[0] if host_port else 'localhost'
        port = host_port[1] if len(host_port) > 1 else '5432'
    else:
        user = 'postgres'
        password = '12345'
        host = 'localhost'
        port = '5432'
    
    try:
        # Connect to PostgreSQL
        print(f"Connecting to database {db_name} on {host}:{port}...")
        conn = psycopg2.connect(
            dbname='postgres',  # Connect to default database first
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists, if not create it
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()
        if not exists:
            print(f"Database {db_name} does not exist. Creating...")
            cur.execute(f'CREATE DATABASE "{db_name}"')
            print(f"Database {db_name} created successfully.")
        
        cur.close()
        conn.close()
        
        # Now connect to the actual database
        conn = psycopg2.connect(
            dbname=db_name,
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        print(f"Connected to database {db_name}")
        
        # Check if quotations table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'quotations'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("ERROR: quotations table does not exist!")
            print("Please run init_db.py first to create the database schema.")
            return
        
        # Check if columns already exist
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'quotations' 
            AND column_name IN ('gst_type', 'cgst_rate', 'sgst_rate', 'igst_rate');
        """)
        existing_columns = [row[0] for row in cur.fetchall()]
        
        # Add GST columns if they don't exist
        if 'gst_type' not in existing_columns:
            print("Adding gst_type column...")
            cur.execute("""
                ALTER TABLE quotations 
                ADD COLUMN gst_type VARCHAR(20);
            """)
            print("✓ Added gst_type column")
        else:
            print("✓ gst_type column already exists")
        
        if 'cgst_rate' not in existing_columns:
            print("Adding cgst_rate column...")
            cur.execute("""
                ALTER TABLE quotations 
                ADD COLUMN cgst_rate NUMERIC(5, 2);
            """)
            print("✓ Added cgst_rate column")
        else:
            print("✓ cgst_rate column already exists")
        
        if 'sgst_rate' not in existing_columns:
            print("Adding sgst_rate column...")
            cur.execute("""
                ALTER TABLE quotations 
                ADD COLUMN sgst_rate NUMERIC(5, 2);
            """)
            print("✓ Added sgst_rate column")
        else:
            print("✓ sgst_rate column already exists")
        
        if 'igst_rate' not in existing_columns:
            print("Adding igst_rate column...")
            cur.execute("""
                ALTER TABLE quotations 
                ADD COLUMN igst_rate NUMERIC(5, 2);
            """)
            print("✓ Added igst_rate column")
        else:
            print("✓ igst_rate column already exists")
        
        print("\n✅ Migration completed successfully!")
        print("All GST fields have been added to the quotations table.")
        
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    print("=" * 60)
    print("GST Fields Migration Script")
    print("=" * 60)
    print()
    migrate()

