#!/usr/bin/env python3
"""
Database module for DMARC Monitor - Phase 2
Handles SQLite storage for historical analysis and trend tracking
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class DMARCDatabase:
    def __init__(self, db_path: str = "data/dmarc_monitor.db"):
        """Initialize database connection and create tables if needed"""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Create database tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    org_name TEXT NOT NULL,
                    report_id TEXT NOT NULL,
                    date_begin INTEGER NOT NULL,
                    date_end INTEGER NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    policy_p TEXT,
                    policy_sp TEXT,
                    policy_pct INTEGER,
                    total_messages INTEGER DEFAULT 0,
                    total_sources INTEGER DEFAULT 0,
                    UNIQUE(domain, org_name, report_id, date_begin, date_end)
                );
                
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id INTEGER NOT NULL,
                    source_ip TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    disposition TEXT,
                    dkim_result TEXT,
                    spf_result TEXT,
                    FOREIGN KEY (report_id) REFERENCES reports (id)
                );
                
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id INTEGER NOT NULL,
                    claude_analysis TEXT NOT NULL,
                    has_issues BOOLEAN DEFAULT FALSE,
                    auth_success_rate REAL,
                    new_sources_detected INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (report_id) REFERENCES reports (id)
                );
                
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    threshold_exceeded TEXT,
                    alert_sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_reports_domain_date ON reports (domain, date_begin);
                CREATE INDEX IF NOT EXISTS idx_records_report_id ON records (report_id);
                CREATE INDEX IF NOT EXISTS idx_analyses_report_id ON analyses (report_id);
                CREATE INDEX IF NOT EXISTS idx_alert_history_domain ON alert_history (domain, created_at);
            """)
        logger.info("Database initialized successfully")
    
    def store_report(self, parsed_report: Dict, claude_analysis: str) -> int:
        """Store a DMARC report and its analysis in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Insert report metadata
                report_cursor = conn.execute("""
                    INSERT OR IGNORE INTO reports 
                    (domain, org_name, report_id, date_begin, date_end, policy_p, policy_sp, policy_pct, total_messages, total_sources)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    parsed_report['policy']['domain'],
                    parsed_report['metadata']['org_name'],
                    parsed_report['metadata']['report_id'],
                    int(parsed_report['metadata']['date_range']['begin']),
                    int(parsed_report['metadata']['date_range']['end']),
                    parsed_report['policy']['p'],
                    parsed_report['policy']['sp'],
                    int(parsed_report['policy']['pct']),
                    sum(record['count'] for record in parsed_report['records']),
                    len(parsed_report['records'])
                ))
                
                # Get the report ID (either inserted or existing)
                db_report_id = conn.execute("""
                    SELECT id FROM reports 
                    WHERE domain = ? AND org_name = ? AND report_id = ? AND date_begin = ? AND date_end = ?
                """, (
                    parsed_report['policy']['domain'],
                    parsed_report['metadata']['org_name'],
                    parsed_report['metadata']['report_id'],
                    int(parsed_report['metadata']['date_range']['begin']),
                    int(parsed_report['metadata']['date_range']['end'])
                )).fetchone()[0]
                
                # Insert records
                for record in parsed_report['records']:
                    conn.execute("""
                        INSERT OR IGNORE INTO records 
                        (report_id, source_ip, count, disposition, dkim_result, spf_result)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        db_report_id,
                        record['source_ip'],
                        record['count'],
                        record['disposition'],
                        record['dkim'],
                        record['spf']
                    ))
                
                # Calculate metrics
                has_issues, auth_success_rate, new_sources = self._analyze_report_metrics(parsed_report, claude_analysis)
                
                # Insert analysis
                conn.execute("""
                    INSERT OR REPLACE INTO analyses 
                    (report_id, claude_analysis, has_issues, auth_success_rate, new_sources_detected)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    db_report_id,
                    claude_analysis,
                    has_issues,
                    auth_success_rate,
                    new_sources
                ))
                
                conn.commit()
                logger.info(f"Stored report for domain {parsed_report['policy']['domain']} (DB ID: {db_report_id})")
                return db_report_id
                
        except Exception as e:
            logger.error(f"Error storing report: {e}")
            return None
    
    def _analyze_report_metrics(self, parsed_report: Dict, claude_analysis: str) -> Tuple[bool, float, int]:
        """Analyze report to determine if it has issues and calculate metrics"""
        total_messages = sum(record['count'] for record in parsed_report['records'])
        
        if total_messages == 0:
            return False, 100.0, 0
        
        # Calculate authentication success rate
        successful_messages = sum(
            record['count'] for record in parsed_report['records']
            if record['dkim'] == 'pass' and record['spf'] == 'pass'
        )
        auth_success_rate = (successful_messages / total_messages) * 100
        
        # Detect issues from Claude analysis and metrics
        has_issues = (
            auth_success_rate < 95.0 or  # Less than 95% success rate
            'issue' in claude_analysis.lower() or
            'problem' in claude_analysis.lower() or
            'fail' in claude_analysis.lower() or
            'suspicious' in claude_analysis.lower() or
            '⚠️' in claude_analysis or
            '❌' in claude_analysis
        )
        
        # Check for new sources (simplified - in real implementation, compare with historical data)
        new_sources = len(set(record['source_ip'] for record in parsed_report['records']))
        
        return has_issues, auth_success_rate, new_sources
    
    def get_historical_data(self, domain: str, days_back: int = 30) -> List[Dict]:
        """Get historical data for a domain for trend analysis"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT r.*, a.has_issues, a.auth_success_rate, a.new_sources_detected, a.claude_analysis
                FROM reports r
                JOIN analyses a ON r.id = a.report_id
                WHERE r.domain = ? AND r.date_begin >= ?
                ORDER BY r.date_begin DESC
            """, (domain, cutoff_timestamp))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_issues(self, hours_back: int = 24) -> List[Dict]:
        """Get reports with issues from the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT r.domain, r.org_name, r.total_messages, a.auth_success_rate, a.claude_analysis, r.processed_at
                FROM reports r
                JOIN analyses a ON r.id = a.report_id
                WHERE a.has_issues = TRUE AND r.processed_at >= ?
                ORDER BY r.processed_at DESC
            """, (cutoff_time.isoformat(),))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_summary_stats(self, hours_back: int = 24) -> Dict:
        """Get summary statistics for recent reports"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_reports,
                    COUNT(DISTINCT r.domain) as unique_domains,
                    SUM(r.total_messages) as total_messages,
                    SUM(CASE WHEN a.has_issues THEN 1 ELSE 0 END) as reports_with_issues,
                    AVG(a.auth_success_rate) as avg_auth_rate
                FROM reports r
                JOIN analyses a ON r.id = a.report_id
                WHERE r.processed_at >= ?
            """, (cutoff_time.isoformat(),))
            
            result = cursor.fetchone()
            return {
                'total_reports': result[0] or 0,
                'unique_domains': result[1] or 0,
                'total_messages': result[2] or 0,
                'reports_with_issues': result[3] or 0,
                'avg_auth_rate': round(result[4] or 100.0, 1),
                'clean_reports': (result[0] or 0) - (result[3] or 0)
            }
    
    def compare_with_historical(self, domain: str, current_auth_rate: float) -> Dict:
        """Compare current performance with historical average"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT AVG(a.auth_success_rate) as historical_avg
                FROM reports r
                JOIN analyses a ON r.id = a.report_id
                WHERE r.domain = ? AND r.processed_at <= datetime('now', '-7 days')
                AND r.processed_at >= datetime('now', '-30 days')
            """, (domain,))
            
            result = cursor.fetchone()
            historical_avg = result[0] if result and result[0] else current_auth_rate
            
            change = current_auth_rate - historical_avg
            return {
                'historical_avg': round(historical_avg, 1),
                'current_rate': round(current_auth_rate, 1),
                'change': round(change, 1),
                'trend': 'improved' if change > 2 else 'declined' if change < -2 else 'stable'
            }
    
    def log_alert(self, domain: str, alert_type: str, threshold_info: str, sent: bool = False):
        """Log an alert that was generated"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO alert_history (domain, alert_type, threshold_exceeded, alert_sent)
                VALUES (?, ?, ?, ?)
            """, (domain, alert_type, threshold_info, sent))
            conn.commit()
    
    def purge_old_data(self, retention_days: int = 30) -> Dict:
        """Purge data older than retention_days to keep database size manageable"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        logger.info(f"Starting data purge for records older than {retention_days} days ({cutoff_date.strftime('%Y-%m-%d')})")
        
        purge_stats = {
            'reports_deleted': 0,
            'records_deleted': 0,
            'analyses_deleted': 0,
            'alerts_deleted': 0,
            'cutoff_date': cutoff_date.strftime('%Y-%m-%d'),
            'retention_days': retention_days
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Count records before deletion
                cursor = conn.execute("SELECT COUNT(*) FROM reports WHERE date_begin < ?", (cutoff_timestamp,))
                old_reports = cursor.fetchone()[0]
                
                if old_reports == 0:
                    logger.info("No old data found to purge")
                    return purge_stats
                
                # Get report IDs that will be deleted (for cascade deletion)
                cursor = conn.execute("SELECT id FROM reports WHERE date_begin < ?", (cutoff_timestamp,))
                old_report_ids = [row[0] for row in cursor.fetchall()]
                
                if old_report_ids:
                    # Delete associated records first (foreign key constraints)
                    placeholders = ','.join('?' * len(old_report_ids))
                    
                    # Delete records
                    cursor = conn.execute(f"DELETE FROM records WHERE report_id IN ({placeholders})", old_report_ids)
                    purge_stats['records_deleted'] = cursor.rowcount
                    
                    # Delete analyses
                    cursor = conn.execute(f"DELETE FROM analyses WHERE report_id IN ({placeholders})", old_report_ids)
                    purge_stats['analyses_deleted'] = cursor.rowcount
                
                # Delete old reports
                cursor = conn.execute("DELETE FROM reports WHERE date_begin < ?", (cutoff_timestamp,))
                purge_stats['reports_deleted'] = cursor.rowcount
                
                # Delete old alert history
                alert_cutoff = cutoff_date.isoformat()
                cursor = conn.execute("DELETE FROM alert_history WHERE created_at < ?", (alert_cutoff,))
                purge_stats['alerts_deleted'] = cursor.rowcount
                
                conn.commit()
            
            # Vacuum database to reclaim space (must be outside transaction)
            with sqlite3.connect(self.db_path) as vacuum_conn:
                vacuum_conn.execute("VACUUM")
                
                logger.info(f"Data purge completed: {purge_stats['reports_deleted']} reports, "
                          f"{purge_stats['records_deleted']} records, "
                          f"{purge_stats['analyses_deleted']} analyses, "
                          f"{purge_stats['alerts_deleted']} alerts deleted")
                
                return purge_stats
                
        except Exception as e:
            logger.error(f"Error during data purge: {e}")
            return purge_stats
    
    def get_database_stats(self) -> Dict:
        """Get database size and record count statistics"""
        try:
            # Get file size
            db_size_bytes = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            db_size_mb = round(db_size_bytes / (1024 * 1024), 2)
            
            with sqlite3.connect(self.db_path) as conn:
                # Get record counts
                tables = ['reports', 'records', 'analyses', 'alert_history']
                counts = {}
                total_records = 0
                
                for table in tables:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    counts[table] = count
                    total_records += count
                
                # Get date range of data
                cursor = conn.execute("""
                    SELECT 
                        MIN(date_begin) as oldest_report,
                        MAX(date_begin) as newest_report,
                        COUNT(*) as total_reports
                    FROM reports
                """)
                result = cursor.fetchone()
                
                oldest_date = None
                newest_date = None
                if result[0] and result[1]:
                    oldest_date = datetime.fromtimestamp(result[0]).strftime('%Y-%m-%d')
                    newest_date = datetime.fromtimestamp(result[1]).strftime('%Y-%m-%d')
                
                return {
                    'database_size_mb': db_size_mb,
                    'database_size_bytes': db_size_bytes,
                    'total_records': total_records,
                    'table_counts': counts,
                    'oldest_report_date': oldest_date,
                    'newest_report_date': newest_date,
                    'total_reports': result[2] if result else 0
                }
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {
                'database_size_mb': 0,
                'total_records': 0,
                'error': str(e)
            }
    
    def migrate_existing_data(self, data_directory: str = "data"):
        """Migrate existing analysis files to database"""
        import glob
        import re
        
        logger.info("Starting migration of existing data...")
        migrated_count = 0
        
        # Find all analysis files
        pattern = os.path.join(data_directory, "dmarc_analysis_*.txt")
        for file_path in glob.glob(pattern):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Extract domain from filename
                filename = os.path.basename(file_path)
                domain_match = re.search(r'_([^_]+\.com)\.txt$', filename)
                if not domain_match:
                    continue
                
                domain = domain_match.group(1)
                
                # This is a simplified migration - in a real scenario, you'd parse the full reports
                # For now, we'll create placeholder entries
                logger.info(f"Migration would process {filename} for domain {domain}")
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
        
        logger.info(f"Migration completed. Processed {migrated_count} files.")
        return migrated_count