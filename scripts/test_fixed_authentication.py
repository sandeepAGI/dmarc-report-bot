#!/usr/bin/env python3
"""
Test that authentication now works with member@aileron-group.com account
"""

import os
import sys
import json
import base64

# Add src directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_root, 'src'))

from dmarc_monitor import OutlookClient, load_config
import requests

def main():
    print("=" * 80)
    print("TESTING FIXED AUTHENTICATION")
    print("=" * 80)

    config = load_config()

    print(f"\n✅ Config loaded")
    print(f"   Configured mailbox: {config['email'].get('mailbox_account', 'NOT SET')}")

    # Initialize client with email config
    client = OutlookClient(config['microsoft'], config['email'])

    print(f"\n🔐 Authenticating...")
    print(f"   This should prompt you to log in as: {config['email'].get('mailbox_account')}")

    if not client.get_access_token():
        print("\n❌ Authentication failed!")
        return 1

    print("\n✅ Authentication successful!")

    # Check which account we're authenticated as
    token_file = 'outlook_token.json'
    with open(token_file, 'r') as f:
        token_data = json.load(f)

    # Decode token to see user
    token_parts = token_data['access_token'].split('.')
    payload = token_parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += '=' * padding
    decoded = json.loads(base64.urlsafe_b64decode(payload))

    authenticated_as = decoded.get('unique_name', decoded.get('upn', 'Unknown'))

    print(f"\n📧 Authenticated as: {authenticated_as}")

    if authenticated_as.lower() == config['email'].get('mailbox_account', '').lower():
        print(f"   ✅ CORRECT! This matches the configured mailbox account")
    else:
        print(f"   ❌ WRONG! Should be: {config['email'].get('mailbox_account')}")
        return 1

    # Now test folder access
    print(f"\n📁 Testing folder access...")
    headers = {'Authorization': f'Bearer {client.access_token}'}

    folders_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
    params = {'includeHiddenFolders': 'true'}
    response = requests.get(folders_url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"❌ Failed to list folders: {response.status_code}")
        return 1

    folders = response.json().get('value', [])
    print(f"\n✅ Found {len(folders)} folders:")

    dmarc_reports_found = False
    dmarc_processed_found = False

    for folder in folders:
        name = folder['displayName']
        count = folder.get('totalItemCount', 0)

        marker = ""
        if name == 'DMARC Reports':
            dmarc_reports_found = True
            marker = " ⭐⭐⭐ FOUND IT!"
        elif name == 'DMARC Processed':
            dmarc_processed_found = True
            marker = " ⭐⭐⭐ FOUND IT!"

        print(f"   - {name} ({count} items){marker}")

    print(f"\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    if dmarc_reports_found and dmarc_processed_found:
        print(f"\n🎉 SUCCESS! Both folders are now accessible!")
        print(f"\n✅ DMARC Reports folder: FOUND")
        print(f"✅ DMARC Processed folder: FOUND")
        print(f"\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print(f"\n1. Run the main script to process the 419 reports:")
        print(f"   python src/dmarc_monitor.py")
        print(f"\n2. Check that reports are processed successfully")
        print(f"\n3. Monitor the cron job to ensure it continues working")
        return 0
    elif dmarc_reports_found:
        print(f"\n✅ DMARC Reports folder found!")
        print(f"⚠️  DMARC Processed folder NOT found")
        print(f"\nThe 'DMARC Processed' folder may need to be created.")
        print(f"The script should still work for reading reports.")
        return 0
    else:
        print(f"\n❌ DMARC Reports folder still NOT found")
        print(f"\nThis means the folders are in a different account or location.")
        print(f"Please verify which account has the DMARC Reports folder.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
