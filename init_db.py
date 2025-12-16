#!/usr/bin/env python3
"""
Database initialization script.
Run this once to create the database tables.
"""

from app import app, db

with app.app_context():
    db.create_all()
    print("Database tables created successfully!")

