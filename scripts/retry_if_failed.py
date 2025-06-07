#!/usr/bin/env python3
"""
DMARC Monitor Retry Script
Only runs if the morning job failed or didn't run
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

def should_retry():
    """Check if we should retry based on last successful run and failed run times"""
    
    # Get project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    last_success_file = project_root / "data" / "last_successful_run.txt"
    last_failed_file = project_root / "data" / "last_failed_run.txt"
    
    now = datetime.now()
    today_morning = now.replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Check if morning job ran successfully today
    if last_success_file.exists():
        try:
            with open(last_success_file, 'r') as f:
                last_success = datetime.fromisoformat(f.read().strip())
            
            # If successful run was after this morning's scheduled time, don't retry
            if last_success >= today_morning:
                print(f"✅ Morning job completed successfully at {last_success.strftime('%H:%M')}")
                return False
                
        except Exception as e:
            print(f"⚠️  Could not read last success time: {e}")
    
    # Check if there was a failure today
    failed_today = False
    if last_failed_file.exists():
        try:
            with open(last_failed_file, 'r') as f:
                last_failed = datetime.fromisoformat(f.read().strip())
            
            # If failure was after this morning's scheduled time
            if last_failed >= today_morning:
                failed_today = True
                print(f"❌ Morning job failed at {last_failed.strftime('%H:%M')}")
                
        except Exception as e:
            print(f"⚠️  Could not read last failure time: {e}")
    
    # Check if no run at all today
    no_run_today = True
    if last_success_file.exists():
        try:
            with open(last_success_file, 'r') as f:
                last_success = datetime.fromisoformat(f.read().strip())
            
            if last_success >= today_morning:
                no_run_today = False
                
        except:
            pass
    
    if no_run_today and not failed_today:
        print("❓ No morning job detected today")
        return True
    
    if failed_today:
        print("🔄 Retrying failed morning job")
        return True
    
    return False

def main():
    """Main retry logic"""
    print(f"DMARC Monitor Retry Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    if not should_retry():
        print("✅ No retry needed - morning job completed successfully")
        return 0
    
    print("🚀 Running DMARC monitor retry...")
    
    # Get paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    main_script = project_root / "src" / "dmarc_monitor.py"
    
    # Change to project directory
    os.chdir(project_root)
    
    # Run the main script
    import subprocess
    result = subprocess.run([sys.executable, str(main_script)], 
                          capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    if result.returncode == 0:
        print("✅ Retry completed successfully")
        return 0
    else:
        print(f"❌ Retry failed with exit code {result.returncode}")
        return result.returncode

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)