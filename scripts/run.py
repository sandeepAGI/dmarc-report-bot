#!/usr/bin/env python3
"""
Runner script for DMARC Monitor
"""

import sys
import os
from pathlib import Path

# Add src directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Change to project directory
os.chdir(project_root)

# Import and run
try:
    from dmarc_monitor import main
    main()
except ImportError as e:
    print(f"Error importing dmarc_monitor: {e}")
    print("Make sure you're in the correct directory and dependencies are installed")
    sys.exit(1)
except Exception as e:
    print(f"Error running DMARC monitor: {e}")
    sys.exit(1)
