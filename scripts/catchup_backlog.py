#!/usr/bin/env python3
"""
One-time catch-up script to process all backlogged DMARC reports (456 reports)
This will process ALL reports in the DMARC Reports folder, ignoring the usual time limits
"""

import os
import sys
from datetime import datetime

# Add src directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_root, 'src'))

# Temporarily rename last_successful_run.txt to force processing all reports
last_run_file = os.path.join(project_root, 'data', 'last_successful_run.txt')
backup_file = os.path.join(project_root, 'data', 'last_successful_run.txt.backup_before_catchup')

def main():
    print("=" * 80)
    print("DMARC REPORTS CATCH-UP - PROCESSING BACKLOG")
    print("=" * 80)

    print("\n📋 This script will:")
    print("   1. Process ALL 456 reports in the DMARC Reports folder")
    print("   2. Generate a comprehensive consolidated report")
    print("   3. Store all results in the database")
    print("   4. Update the timestamp for future runs")

    print("\n⏰ Estimated time: 10-15 minutes (depending on Claude API speed)")

    response = input("\n❓ Do you want to proceed? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("\n❌ Cancelled by user")
        return 1

    print("\n" + "=" * 80)
    print("STEP 1: BACKING UP CURRENT STATE")
    print("=" * 80)

    # Backup the last_successful_run.txt
    if os.path.exists(last_run_file):
        with open(last_run_file, 'r') as f:
            last_run_content = f.read()

        with open(backup_file, 'w') as f:
            f.write(last_run_content)

        print(f"✅ Backed up last run timestamp to: {backup_file}")
        print(f"   Original timestamp: {last_run_content.strip()}")

        # Delete the file to trigger full processing
        os.remove(last_run_file)
        print(f"✅ Removed last_successful_run.txt (will be recreated)")
    else:
        print("   ℹ️  No existing last_successful_run.txt found")

    print("\n" + "=" * 80)
    print("STEP 2: RUNNING MAIN DMARC MONITOR")
    print("=" * 80)
    print("\n🚀 Processing all reports...")
    print("   (This may take 10-15 minutes - please be patient)\n")

    # Import and run the main function
    from dmarc_monitor import main as dmarc_main

    try:
        success = dmarc_main()

        if success:
            print("\n" + "=" * 80)
            print("✅ CATCH-UP COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print("\n📊 All backlogged reports have been processed")
            print("📧 Check your email for the consolidated report")
            print("💾 All data has been stored in the database")

            # Show the new timestamp
            if os.path.exists(last_run_file):
                with open(last_run_file, 'r') as f:
                    new_timestamp = f.read().strip()
                print(f"\n⏰ Updated timestamp: {new_timestamp}")

            print("\n" + "=" * 80)
            print("NEXT STEPS")
            print("=" * 80)
            print("\n1. ✅ Normal cron job operations will resume automatically")
            print("2. ✅ Future runs will only process new reports")
            print("3. 📧 Review the emailed report for any security issues")

            # Clean up backup
            if os.path.exists(backup_file):
                print(f"\n💡 Backup file kept at: {backup_file}")
                print(f"   (You can delete this once you confirm everything works)")

            return 0
        else:
            print("\n❌ Processing completed with some errors")
            print("   Check logs for details: logs/dmarc_monitor.log")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Catch-up interrupted by user!")
        print("   Restoring backup...")

        # Restore backup if interrupted
        if os.path.exists(backup_file):
            with open(backup_file, 'r') as f:
                backup_content = f.read()
            with open(last_run_file, 'w') as f:
                f.write(backup_content)
            print("   ✅ Restored original timestamp")

        return 1

    except Exception as e:
        print(f"\n\n❌ Error during catch-up: {e}")
        print("   Check logs for details: logs/dmarc_monitor.log")

        # Try to restore backup
        if os.path.exists(backup_file) and not os.path.exists(last_run_file):
            try:
                with open(backup_file, 'r') as f:
                    backup_content = f.read()
                with open(last_run_file, 'w') as f:
                    f.write(backup_content)
                print("   ✅ Restored original timestamp")
            except:
                pass

        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
