from app import create_app
from app.models import db
import os

app = create_app()

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("All tables dropped")
    
    print("Creating all tables with correct schema...")
    db.create_all()
    print("All tables created successfully")
    
    # Verify the table structure
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    
    print("\n=== VERIFYING TABLE STRUCTURE ===")
    for table_name in inspector.get_table_names():
        print(f"\n{table_name}:")
        for column in inspector.get_columns(table_name):
            print(f"  {column['name']}: {column['type']} (nullable: {column['nullable']})")