import os
from sqlalchemy import create_engine, Column, String, Text, Float, Integer
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://citizen360:citizen360@localhost:5432/citizen360"
)

# PostgreSQL connection pool configuration
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SessionModel(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    username = Column(String, index=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

class MessageModel(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    sql = Column(Text)
    result = Column(Text)
    created_at = Column(String, nullable=False)

class QueryLogModel(Base):
    __tablename__ = "query_log"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(String, nullable=False)
    username = Column(String, index=True)
    session_id = Column(String, index=True)
    question = Column(Text)
    generated_sql = Column(Text)
    status = Column(String)
    answer = Column(Text)
    error = Column(Text)
    gen_time_s = Column(Float, default=0.0)
    exec_time_s = Column(Float, default=0.0)
    total_time_s = Column(Float, default=0.0)

def init_postgres_db():
    Base.metadata.create_all(bind=engine)
