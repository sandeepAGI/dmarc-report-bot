#!/usr/bin/env python3
"""
Database Maintenance Utility for DMARC Monitor
Provides tools for database cleanup, statistics, and optimization
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import DMARCDatabase
import json

def show_database_stats(db: DMARCDatabase):
    """Display comprehensive database statistics"""
    print("📊 Database Statistics")
    print("=" * 50)
    
    stats = db.get_database_stats()
    
    print(f"Database File Size: {stats['database_size_mb']} MB ({stats['database_size_bytes']:,} bytes)")
    print(f"Total Records: {stats['total_records']:,}")
    print()
    
    print("Table Counts:")
    for table, count in stats['table_counts'].items():
        print(f"  • {table}: {count:,}")
    print()
    
    if stats['oldest_report_date'] and stats['newest_report_date']:
        print(f"Data Range: {stats['oldest_report_date']} to {stats['newest_report_date']}")
        
        # Calculate data span
        oldest = datetime.strptime(stats['oldest_report_date'], '%Y-%m-%d')
        newest = datetime.strptime(stats['newest_report_date'], '%Y-%m-%d')
        span_days = (newest - oldest).days
        print(f"Data Span: {span_days} days")
    else:
        print("Data Range: No reports found")
    
    # Check for potential cleanup opportunities
    if stats['database_size_mb'] > 50:
        print("\n⚠️  Database is large (>50MB) - consider purging old data")
    elif stats['database_size_mb'] > 100:
        print("\n🚨 Database is very large (>100MB) - purging recommended")
    
    if stats['total_reports'] > 500:
        print(f"⚠️  Large number of reports ({stats['total_reports']}) - consider reducing retention period")

def purge_old_data(db: DMARCDatabase, retention_days: int, dry_run: bool = False):
    """Purge old data with optional dry run"""
    print(f"🗑️  Database Cleanup ({'DRY RUN' if dry_run else 'LIVE RUN'})")
    print("=" * 50)
    
    if dry_run:
        print(f"Simulating purge of data older than {retention_days} days...")
        # For dry run, just count what would be deleted
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM reports WHERE date_begin < ?", (cutoff_timestamp,))
            old_reports = cursor.fetchone()[0]
            
            if old_reports == 0:
                print("✅ No old data found to purge")
                return
            
            # Get report IDs for counting related records
            cursor = conn.execute("SELECT id FROM reports WHERE date_begin < ?", (cutoff_timestamp,))
            old_report_ids = [row[0] for row in cursor.fetchall()]
            
            if old_report_ids:
                placeholders = ','.join('?' * len(old_report_ids))
                
                cursor = conn.execute(f"SELECT COUNT(*) FROM records WHERE report_id IN ({placeholders})", old_report_ids)
                old_records = cursor.fetchone()[0]
                
                cursor = conn.execute(f"SELECT COUNT(*) FROM analyses WHERE report_id IN ({placeholders})", old_report_ids)
                old_analyses = cursor.fetchone()[0]
            else:
                old_records = old_analyses = 0
            
            alert_cutoff = cutoff_date.isoformat()
            cursor = conn.execute("SELECT COUNT(*) FROM alert_history WHERE created_at < ?", (alert_cutoff,))
            old_alerts = cursor.fetchone()[0]
            
            print(f"📋 Data that would be deleted:")
            print(f"  • Reports: {old_reports:,}")
            print(f"  • Records: {old_records:,}")
            print(f"  • Analyses: {old_analyses:,}")
            print(f"  • Alerts: {old_alerts:,}")
            print(f"\n⚠️  Use --confirm to perform actual deletion")
    else:
        print(f"Purging data older than {retention_days} days...")
        purge_stats = db.purge_old_data(retention_days)
        
        print(f"✅ Purge completed:")
        print(f"  • Reports deleted: {purge_stats['reports_deleted']:,}")
        print(f"  • Records deleted: {purge_stats['records_deleted']:,}")
        print(f"  • Analyses deleted: {purge_stats['analyses_deleted']:,}")
        print(f"  • Alerts deleted: {purge_stats['alerts_deleted']:,}")
        
        if purge_stats['reports_deleted'] > 0:
            print(f"\n📈 Database has been optimized (VACUUM performed)")

def export_database_info(db: DMARCDatabase, output_file: str):
    """Export database information to JSON file"""
    print(f"📤 Exporting database info to {output_file}")
    print("=" * 50)
    
    stats = db.get_database_stats()
    
    # Add some additional analysis
    export_data = {
        'export_timestamp': datetime.now().isoformat(),
        'database_stats': stats,
        'maintenance_recommendations': []
    }
    
    # Generate recommendations
    if stats['database_size_mb'] > 50:
        export_data['maintenance_recommendations'].append(
            f"Consider purging data older than 30 days (current size: {stats['database_size_mb']}MB)"
        )
    
    if stats['total_reports'] > 500:
        export_data['maintenance_recommendations'].append(
            f"Large number of reports ({stats['total_reports']}) - consider reducing retention period"
        )
    
    # Get recent activity summary
    try:
        recent_issues = db.get_recent_issues(hours_back=168)  # Last week
        export_data['recent_activity'] = {
            'issues_last_week': len(recent_issues),
            'summary_stats': db.get_summary_stats(hours_back=168)
        }
    except Exception as e:
        export_data['recent_activity'] = {'error': str(e)}
    
    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"✅ Database information exported to {output_file}")

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description='DMARC Monitor Database Maintenance Utility')
    parser.add_argument('--db-path', default='data/dmarc_monitor.db', 
                       help='Path to SQLite database file (default: data/dmarc_monitor.db)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    # Purge command
    purge_parser = subparsers.add_parser('purge', help='Purge old data')
    purge_parser.add_argument('--days', type=int, default=30,
                             help='Retention period in days (default: 30)')
    purge_parser.add_argument('--dry-run', action='store_true',
                             help='Show what would be deleted without actually deleting')
    purge_parser.add_argument('--confirm', action='store_true',
                             help='Confirm deletion (required for actual purge)')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export database info to JSON')
    export_parser.add_argument('--output', default='database_info.json',
                              help='Output file path (default: database_info.json)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Check if database exists
    if not os.path.exists(args.db_path):
        print(f"❌ Database file not found: {args.db_path}")
        print("Run the main DMARC monitor script first to create the database.")
        return
    
    # Initialize database
    db = DMARCDatabase(args.db_path)
    
    try:
        if args.command == 'stats':
            show_database_stats(db)
            
        elif args.command == 'purge':
            if not args.dry_run and not args.confirm:
                print("❌ Purge requires --confirm flag for safety")
                print("Use --dry-run to see what would be deleted")
                return
            
            purge_old_data(db, args.days, dry_run=args.dry_run)
            
        elif args.command == 'export':
            export_database_info(db, args.output)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()