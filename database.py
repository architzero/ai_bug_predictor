"""
Production-grade database implementation with:
- Connection pooling
- Context managers for automatic session cleanup
- Proper relationships between models
- Comprehensive indexes
- Migration support ready
- PostgreSQL/MySQL support
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, 
    DateTime, Text, ForeignKey, Index, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from datetime import datetime
import os
import json

Base = declarative_base()

# ============================================================================
# Models with Relationships
# ============================================================================

class Scan(Base):
    """Scan metadata - parent of all FileRisk records."""
    __tablename__ = 'scans'
    
    id = Column(Integer, primary_key=True)
    scan_id = Column(String(100), unique=True, nullable=False, index=True)
    repo_path = Column(String(500), nullable=False)
    repo_name = Column(String(200), nullable=False, index=True)
    
    # Scan results
    files_analyzed = Column(Integer, default=0)
    buggy_count = Column(Integer, default=0)
    high_risk_count = Column(Integer, default=0)
    avg_risk = Column(Float, default=0.0)
    
    # Confidence metrics
    confidence_score = Column(Float)
    confidence_level = Column(String(20))
    confidence_warnings = Column(Text)  # JSON array
    out_of_distribution = Column(Boolean, default=False)
    
    # Performance metrics
    scan_duration = Column(Float)  # seconds
    
    # Status tracking
    status = Column(String(20), default='in_progress', index=True)  # in_progress, complete, error
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime)
    
    # Relationships
    files = relationship("FileRisk", back_populates="scan", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_scan_status_date', 'status', 'created_at'),
        Index('idx_scan_repo_date', 'repo_name', 'created_at'),
    )
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'repo_path': self.repo_path,
            'repo_name': self.repo_name,
            'files_analyzed': self.files_analyzed,
            'buggy_count': self.buggy_count,
            'high_risk_count': self.high_risk_count,
            'avg_risk': round(self.avg_risk, 3) if self.avg_risk else 0.0,
            'confidence': {
                'score': round(self.confidence_score, 3) if self.confidence_score else 0.0,
                'level': self.confidence_level,
                'warnings': json.loads(self.confidence_warnings) if self.confidence_warnings else [],
                'out_of_distribution': self.out_of_distribution
            },
            'scan_duration': round(self.scan_duration, 2) if self.scan_duration else 0.0,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class FileRisk(Base):
    """File-level risk predictions."""
    __tablename__ = 'file_risks'
    
    id = Column(Integer, primary_key=True)
    scan_id = Column(Integer, ForeignKey('scans.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # File identification
    filepath = Column(String(1000), nullable=False, index=True)
    filename = Column(String(255), index=True)  # Basename for quick lookup
    language = Column(String(50), index=True)
    
    # Risk scores
    risk = Column(Float, nullable=False, index=True)
    risky = Column(Boolean, default=False, index=True)
    buggy = Column(Boolean, default=False)
    
    # Static analysis features
    loc = Column(Integer, default=0)
    avg_complexity = Column(Float, default=0.0)
    max_complexity = Column(Float, default=0.0)
    functions = Column(Integer, default=0)
    complexity_density = Column(Float, default=0.0)
    complexity_per_function = Column(Float, default=0.0)
    loc_per_function = Column(Float, default=0.0)
    
    # Git history features
    commits = Column(Integer, default=0)
    lines_added = Column(Integer, default=0)
    lines_deleted = Column(Integer, default=0)
    churn = Column(Integer, default=0)
    author_count = Column(Integer, default=0)
    ownership = Column(Float, default=0.0)
    
    # Time-window features
    commits_2w = Column(Integer, default=0)
    commits_1m = Column(Integer, default=0)
    commits_3m = Column(Integer, default=0)
    recent_churn_ratio = Column(Float, default=0.0)
    recent_activity_score = Column(Float, default=0.0)
    
    # Advanced risk features
    coupling_risk = Column(Float, default=0.0)
    temporal_bug_risk = Column(Float, default=0.0)
    instability_score = Column(Float, default=0.0)
    burst_risk = Column(Float, default=0.0)
    
    # Confidence
    confidence_score = Column(Float)
    confidence_level = Column(String(20))
    
    # Effort-aware metrics
    risk_per_loc = Column(Float, default=0.0)
    effort_priority = Column(Float, default=0.0, index=True)
    effort_category = Column(String(20))  # HIGH_VALUE, EFFICIENT, EXPENSIVE, LOW_PRIORITY
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    scan = relationship("Scan", back_populates="files")
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_file_risk_desc', 'scan_id', 'risk'),
        Index('idx_file_risky', 'scan_id', 'risky'),
        Index('idx_file_effort', 'scan_id', 'effort_priority'),
        Index('idx_file_language_risk', 'language', 'risk'),
    )
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'filepath': self.filepath,
            'filename': self.filename,
            'language': self.language,
            'risk': round(self.risk, 3),
            'risky': self.risky,
            'buggy': self.buggy,
            'loc': self.loc,
            'avg_complexity': round(self.avg_complexity, 2) if self.avg_complexity else 0.0,
            'max_complexity': round(self.max_complexity, 2) if self.max_complexity else 0.0,
            'functions': self.functions,
            'complexity_density': round(self.complexity_density, 3) if self.complexity_density else 0.0,
            'commits': self.commits,
            'lines_added': self.lines_added,
            'lines_deleted': self.lines_deleted,
            'author_count': self.author_count,
            'commits_1m': self.commits_1m,
            'coupling_risk': round(self.coupling_risk, 3) if self.coupling_risk else 0.0,
            'temporal_bug_risk': round(self.temporal_bug_risk, 3) if self.temporal_bug_risk else 0.0,
            'instability_score': round(self.instability_score, 3) if self.instability_score else 0.0,
            'confidence_score': round(self.confidence_score, 3) if self.confidence_score else 0.0,
            'confidence_level': self.confidence_level,
            'risk_per_loc': round(self.risk_per_loc, 6) if self.risk_per_loc else 0.0,
            'effort_priority': round(self.effort_priority, 2) if self.effort_priority else 0.0,
            'effort_category': self.effort_category,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================================
# Database Manager with Connection Pooling
# ============================================================================

class DatabaseManager:
    """
    Singleton database manager with connection pooling and session management.
    
    Usage:
        db = DatabaseManager.get_instance()
        
        # Context manager (recommended)
        with db.session_scope() as session:
            files = session.query(FileRisk).filter(FileRisk.risk > 0.7).all()
        
        # Or manual
        session = db.get_session()
        try:
            # ... queries
            session.commit()
        finally:
            session.close()
    """
    
    _instance = None
    
    def __init__(self, database_url=None, echo=False):
        """
        Initialize database connection.
        
        Args:
            database_url: SQLAlchemy database URL
                - SQLite: 'sqlite:///bug_predictor.db'
                - PostgreSQL: 'postgresql://user:pass@localhost/dbname'
                - MySQL: 'mysql+pymysql://user:pass@localhost/dbname'
            echo: Print SQL queries (debug mode)
        """
        if database_url is None:
            # Default to SQLite in project root
            database_url = f'sqlite:///{os.path.join(os.getcwd(), "bug_predictor.db")}'
        
        # Connection pooling configuration
        if database_url.startswith('sqlite'):
            # SQLite doesn't support connection pooling well
            self.engine = create_engine(
                database_url,
                echo=echo,
                connect_args={'check_same_thread': False}  # Allow multi-threading
            )
        else:
            # PostgreSQL/MySQL with connection pooling
            self.engine = create_engine(
                database_url,
                echo=echo,
                poolclass=QueuePool,
                pool_size=10,          # Number of connections to maintain
                max_overflow=20,       # Max connections beyond pool_size
                pool_timeout=30,       # Timeout waiting for connection
                pool_recycle=3600,     # Recycle connections after 1 hour
                pool_pre_ping=True     # Verify connections before use
            )
        
        # Thread-safe session factory
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
    
    @classmethod
    def get_instance(cls, database_url=None, echo=False):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(database_url, echo)
        return cls._instance
    
    def get_session(self):
        """Get a new session (remember to close it!)."""
        return self.Session()
    
    @contextmanager
    def session_scope(self):
        """
        Context manager for automatic session cleanup.
        
        Usage:
            with db.session_scope() as session:
                user = session.query(User).first()
                # session automatically committed and closed
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def close(self):
        """Close all connections."""
        self.Session.remove()
        self.engine.dispose()


# ============================================================================
# High-Level Query Functions
# ============================================================================

def save_scan_results(df, scan_id, repo_path, confidence_result=None, scan_duration=None):
    """
    Save scan results to database.
    
    Args:
        df: DataFrame with scan results
        scan_id: Unique scan identifier
        repo_path: Repository path
        confidence_result: Confidence assessment dict
        scan_duration: Scan duration in seconds
    
    Returns:
        Scan object
    """
    db = DatabaseManager.get_instance()
    
    with db.session_scope() as session:
        # Create scan record
        scan = Scan(
            scan_id=scan_id,
            repo_path=repo_path,
            repo_name=os.path.basename(repo_path),
            files_analyzed=len(df),
            buggy_count=int(df.get('buggy', 0).sum()),
            high_risk_count=int((df.get('risk', 0) > 0.7).sum()),
            avg_risk=float(df.get('risk', 0).mean()),
            scan_duration=scan_duration,
            status='complete',
            completed_at=datetime.utcnow()
        )
        
        # Add confidence metrics
        if confidence_result:
            scan.confidence_score = confidence_result.get('confidence_score')
            scan.confidence_level = confidence_result.get('confidence_level')
            scan.confidence_warnings = json.dumps(confidence_result.get('warnings', []))
            scan.out_of_distribution = confidence_result.get('out_of_distribution', False)
        
        session.add(scan)
        session.flush()  # Get scan.id
        
        # Bulk insert file risks
        file_risks = []
        for _, row in df.iterrows():
            file_risk = FileRisk(
                scan_id=scan.id,
                filepath=str(row.get('file', '')),
                filename=os.path.basename(str(row.get('file', ''))),
                language=row.get('language', 'unknown'),
                risk=float(row.get('risk', 0.0)),
                risky=bool(row.get('risky', False)),
                buggy=bool(row.get('buggy', False)),
                loc=int(row.get('loc', 0)),
                avg_complexity=float(row.get('avg_complexity', 0.0)),
                max_complexity=float(row.get('max_complexity', 0.0)),
                functions=int(row.get('functions', 0)),
                complexity_density=float(row.get('complexity_density', 0.0)),
                commits=int(row.get('commits', 0)),
                lines_added=int(row.get('lines_added', 0)),
                lines_deleted=int(row.get('lines_deleted', 0)),
                author_count=int(row.get('author_count', 0)),
                commits_1m=int(row.get('commits_1m', 0)),
                coupling_risk=float(row.get('coupling_risk', 0.0)),
                temporal_bug_risk=float(row.get('temporal_bug_risk', 0.0)),
                instability_score=float(row.get('instability_score', 0.0)),
                confidence_score=float(row.get('confidence_score', 0.0)),
                confidence_level=row.get('confidence_level', 'UNKNOWN'),
                risk_per_loc=float(row.get('risk_per_loc', 0.0)),
                effort_priority=float(row.get('effort_priority', 0.0)),
                effort_category=row.get('effort_category', 'MODERATE')
            )
            file_risks.append(file_risk)
        
        session.bulk_save_objects(file_risks)
        
        return scan


def get_recent_scans(limit=10):
    """Get recent scans."""
    db = DatabaseManager.get_instance()
    with db.session_scope() as session:
        scans = session.query(Scan).order_by(
            Scan.created_at.desc()
        ).limit(limit).all()
        return [scan.to_dict() for scan in scans]


def get_scan_by_id(scan_id):
    """Get scan by ID with all files."""
    db = DatabaseManager.get_instance()
    with db.session_scope() as session:
        scan = session.query(Scan).filter(Scan.scan_id == scan_id).first()
        if scan:
            result = scan.to_dict()
            result['files'] = [f.to_dict() for f in scan.files]
            return result
        return None


def get_high_risk_files(scan_id=None, limit=20):
    """Get high-risk files, optionally filtered by scan."""
    db = DatabaseManager.get_instance()
    with db.session_scope() as session:
        query = session.query(FileRisk).filter(FileRisk.risk > 0.7)
        
        if scan_id:
            scan = session.query(Scan).filter(Scan.scan_id == scan_id).first()
            if scan:
                query = query.filter(FileRisk.scan_id == scan.id)
        
        files = query.order_by(FileRisk.risk.desc()).limit(limit).all()
        return [f.to_dict() for f in files]


def get_files_by_effort(scan_id=None, limit=10):
    """Get files ordered by effort priority."""
    db = DatabaseManager.get_instance()
    with db.session_scope() as session:
        query = session.query(FileRisk)
        
        if scan_id:
            scan = session.query(Scan).filter(Scan.scan_id == scan_id).first()
            if scan:
                query = query.filter(FileRisk.scan_id == scan.id)
        
        files = query.order_by(FileRisk.effort_priority.desc()).limit(limit).all()
        return [f.to_dict() for f in files]


def delete_old_scans(days=30):
    """Delete scans older than specified days."""
    db = DatabaseManager.get_instance()
    from datetime import timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    with db.session_scope() as session:
        deleted = session.query(Scan).filter(
            Scan.created_at < cutoff_date
        ).delete()
        return deleted


# ============================================================================
# Initialization
# ============================================================================

def init_database(database_url=None, echo=False):
    """
    Initialize database and create tables.
    
    Args:
        database_url: Database connection string
        echo: Print SQL queries
    
    Returns:
        DatabaseManager instance
    """
    db = DatabaseManager.get_instance(database_url, echo)
    print(f"✓ Database initialized: {database_url or 'SQLite (default)'}")
    print(f"✓ Tables created: {', '.join(Base.metadata.tables.keys())}")
    return db


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Initialize database
    db = init_database(echo=True)
    
    # Example: Save scan results
    import pandas as pd
    
    df = pd.DataFrame({
        'file': ['src/main.py', 'src/utils.py'],
        'risk': [0.85, 0.45],
        'risky': [True, False],
        'buggy': [True, False],
        'loc': [450, 200],
        'avg_complexity': [12.5, 5.2],
        'commits': [150, 50],
        'language': ['python', 'python']
    })
    
    scan = save_scan_results(
        df=df,
        scan_id='test-123',
        repo_path='dataset/test',
        scan_duration=45.2
    )
    print(f"\n✓ Scan saved: {scan.scan_id}")
    
    # Query recent scans
    recent = get_recent_scans(limit=5)
    print(f"\n✓ Recent scans: {len(recent)}")
    
    # Query high-risk files
    high_risk = get_high_risk_files(limit=10)
    print(f"\n✓ High-risk files: {len(high_risk)}")
    
    print("\n✓ Database test complete!")
