#!/usr/bin/env python3
"""
Setup script for DMARC Monitor
"""

import os
import json
import sys
from pathlib import Path

def main():
    """Setup the DMARC Monitor project"""
    project_root = Path(__file__).parent.parent
    config_file = project_root / "config" / "config.json"
    config_template = project_root / "config" / "config.json.template"
    
    print("DMARC Monitor Setup")
    print("==================")
    
    # Check if config exists
    if config_file.exists():
        print(f"✓ Configuration file already exists: {config_file}")
        
        # Validate config
        try:
            with open(config_file) as f:
                config = json.load(f)
            
            required_fields = [
                "microsoft.client_id",
                "microsoft.client_secret", 
                "microsoft.tenant_id",
                "claude.api_key"
            ]
            
            missing_fields = []
            for field in required_fields:
                keys = field.split('.')
                value = config
                try:
                    for key in keys:
                        value = value[key]
                    if not value or value.startswith("YOUR_"):
                        missing_fields.append(field)
                except (KeyError, TypeError):
                    missing_fields.append(field)
            
            if missing_fields:
                print("⚠️  Missing configuration values:")
                for field in missing_fields:
                    print(f"   - {field}")
                print(f"\nPlease edit {config_file} and fill in the required values.")
            else:
                print("✓ Configuration appears complete")
                
        except json.JSONDecodeError:
            print(f"❌ Configuration file is invalid JSON: {config_file}")
            return False
            
    else:
        print(f"Creating configuration file from template...")
        if not config_template.exists():
            print(f"❌ Template file not found: {config_template}")
            return False
            
        # Copy template
        import shutil
        shutil.copy2(config_template, config_file)
        print(f"✓ Created {config_file}")
        print(f"📝 Please edit {config_file} and fill in your actual credentials")
    
    # Create directories
    directories = ["logs", "data"]
    for dir_name in directories:
        dir_path = project_root / dir_name
        dir_path.mkdir(exist_ok=True)
        print(f"✓ Directory ready: {dir_path}")
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("⚠️  Python 3.7+ recommended")
    else:
        print(f"✓ Python version: {sys.version}")
    
    print("\nSetup complete!")
    print("Next steps:")
    print("1. Edit config/config.json with your credentials")
    print("2. Run: python src/dmarc_monitor.py")
    
    return True

if __name__ == "__main__":
    main()
