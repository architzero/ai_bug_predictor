import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

class DatabaseManager:
    _instance = None
    
    @classmethod
    def get_instance(cls, db_path="bug_predictor.db"):
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance
    
    def __init__(self, db_path="bug_predictor.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                scan_id TEXT PRIMARY KEY,
                repo_path TEXT NOT NULL,
                scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                files_analyzed INTEGER,
                high_risk_count INTEGER,
                avg_risk REAL,
                scan_duration REAL,
                confidence_score REAL,
                confidence_level TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_risks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT,
                file_path TEXT,
                risk_score REAL,
                is_buggy INTEGER,
                complexity INTEGER,
                FOREIGN KEY (scan_id) REFERENCES scans(scan_id)
            )
        ''')
        
        conn.commit()
        conn.close()

class Scan:
    pass

class FileRisk:
    pass

def save_scan_results(df: pd.DataFrame, scan_id: str, repo_path: str, 
                     confidence_result: Dict, scan_duration: float) -> Dict:
    db = DatabaseManager.get_instance()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    high_risk_count = int((df['risk'] > 0.7).sum())
    avg_risk = float(df['risk'].mean())
    
    cursor.execute('''
        INSERT INTO scans (scan_id, repo_path, files_analyzed, high_risk_count, 
                          avg_risk, scan_duration, confidence_score, confidence_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (scan_id, repo_path, len(df), high_risk_count, avg_risk, scan_duration,
          confidence_result['confidence_score'], confidence_result['confidence_level']))
    
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO file_risks (scan_id, file_path, risk_score, is_buggy, complexity)
            VALUES (?, ?, ?, ?, ?)
        ''', (scan_id, str(row['file']), float(row['risk']), 
              int(row.get('buggy', 0)), int(row.get('avg_complexity', 0))))
    
    conn.commit()
    conn.close()
    
    return {"scan_id": scan_id, "files": len(df)}

def get_recent_scans(limit: int = 10) -> List[Dict]:
    db = DatabaseManager.get_instance()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT scan_id, repo_path, scan_date, files_analyzed, high_risk_count, avg_risk
        FROM scans ORDER BY scan_date DESC LIMIT ?
    ''', (limit,))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'scan_id': row[0],
            'repo_path': row[1],
            'scan_date': row[2],
            'files_analyzed': row[3],
            'high_risk_count': row[4],
            'avg_risk': row[5]
        })
    
    conn.close()
    return results

def get_high_risk_files(scan_id: str, limit: int = 100) -> List[Dict]:
    db = DatabaseManager.get_instance()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT file_path, risk_score, is_buggy, complexity
        FROM file_risks WHERE scan_id = ?
        ORDER BY risk_score DESC LIMIT ?
    ''', (scan_id, limit))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'file': row[0],
            'risk': row[1],
            'buggy': row[2],
            'complexity': row[3]
        })
    
    conn.close()
    return results

def get_scan_by_id(scan_id: str) -> Optional[Dict]:
    db = DatabaseManager.get_instance()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM scans WHERE scan_id = ?', (scan_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'scan_id': row[0],
            'repo_path': row[1],
            'scan_date': row[2],
            'files_analyzed': row[3],
            'high_risk_count': row[4],
            'avg_risk': row[5]
        }
    return None
