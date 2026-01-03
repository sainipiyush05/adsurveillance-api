"""
Database configuration for AdSurveillance
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

# Create SQLAlchemy engine
engine = None
if settings.DATABASE_URL:
    engine = create_engine(settings.DATABASE_URL)
    print(f"✅ Database connection established to {settings.SUPABASE_URL}")
else:
    print("⚠️ No database URL configured. Using Supabase client directly.")

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

# Create Base class for models
Base = declarative_base()

# Dependency to get DB session
def get_db():
    if not SessionLocal:
        raise Exception("Database not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Supabase client (fallback)
from supabase import create_client, Client

supabase: Client = None
if settings.SUPABASE_URL and settings.SUPABASE_KEY:
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    print("✅ Supabase client initialized")
else:
    print("⚠️ Supabase credentials not configured")