#!/usr/bin/env python3
"""
Move all processed DMARC reports from 'DMARC Reports' to 'DMARC Processed' folder
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add src directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_root, 'src'))

from dmarc_monitor import OutlookClient, load_config

def move_message(client, message_id, source_folder_id, dest_folder_id):
    """Move a message from source folder to destination folder"""
    if not client.access_token:
        raise Exception("Not authenticated")

    headers = {'Authorization': f'Bearer {client.access_token}'}

    # Use Microsoft Graph API to move message
    move_url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/move"
    body = {'destinationId': dest_folder_id}

    response = requests.post(move_url, headers=headers, json=body)

    if response.status_code in [200, 201]:
        return True
    else:
        print(f"   Warning: Failed to move message {message_id}: {response.status_code}")
        return False

def get_folder_id(client, folder_name):
    """Get folder ID by name"""
    if not client.access_token:
        raise Exception("Not authenticated")

    headers = {'Authorization': f'Bearer {client.access_token}'}
    folders_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
    params = {'includeHiddenFolders': 'true'}

    response = requests.get(folders_url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"Failed to get folders: {response.status_code}")

    for folder in response.json().get('value', []):
        if folder['displayName'] == folder_name:
            return folder['id']

    return None

def get_all_messages(client, folder_id):
    """Get all messages from a folder (with pagination)"""
    if not client.access_token:
        raise Exception("Not authenticated")

    headers = {'Authorization': f'Bearer {client.access_token}'}
    messages_url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/messages"
    params = {
        '$select': 'id,subject,receivedDateTime,hasAttachments',
        '$orderby': 'receivedDateTime desc',
        '$top': 999
    }

    all_messages = []
    while messages_url:
        response = requests.get(messages_url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to get messages: {response.status_code}")

        data = response.json()
        all_messages.extend(data.get('value', []))

        messages_url = data.get('@odata.nextLink')
        params = None  # nextLink includes all parameters

    return all_messages

def main():
    print("=" * 80)
    print("MOVE PROCESSED DMARC REPORTS TO 'DMARC PROCESSED' FOLDER")
    print("=" * 80)

    config = load_config()

    source_folder = config['email'].get('folder_name', 'DMARC Reports')
    dest_folder = config['email'].get('processed_folder', 'DMARC Processed')

    print(f"\n📁 Source Folder: {source_folder}")
    print(f"📁 Destination Folder: {dest_folder}")

    # Initialize client
    client = OutlookClient(config['microsoft'], config['email'])

    print(f"\n🔐 Authenticating...")
    if not client.get_access_token():
        print("❌ Authentication failed!")
        return 1

    print("✅ Authenticated successfully")

    # Get folder IDs
    print(f"\n📂 Finding folders...")
    source_folder_id = get_folder_id(client, source_folder)
    dest_folder_id = get_folder_id(client, dest_folder)

    if not source_folder_id:
        print(f"❌ Source folder '{source_folder}' not found!")
        return 1

    if not dest_folder_id:
        print(f"❌ Destination folder '{dest_folder}' not found!")
        print(f"\n💡 You may need to create the '{dest_folder}' folder in Outlook first.")
        return 1

    print(f"✅ Found both folders")

    # Get all messages from source folder
    print(f"\n📥 Retrieving messages from '{source_folder}'...")
    messages = get_all_messages(client, source_folder_id)

    print(f"✅ Found {len(messages)} messages")

    if len(messages) == 0:
        print(f"\n✅ No messages to move - folder is already clean!")
        return 0

    # Ask for confirmation
    print(f"\n" + "=" * 80)
    print(f"⚠️  WARNING")
    print(f"=" * 80)
    print(f"\nThis will move {len(messages)} messages from:")
    print(f"   '{source_folder}' → '{dest_folder}'")
    print(f"\nThis operation:")
    print(f"   ✓ Can be reversed (messages stay in Outlook)")
    print(f"   ✓ Will clean up your DMARC Reports folder")
    print(f"   ✓ Will preserve all email data")

    response = input(f"\n❓ Do you want to proceed? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("\n❌ Cancelled by user")
        return 1

    # Move messages
    print(f"\n" + "=" * 80)
    print(f"MOVING MESSAGES")
    print(f"=" * 80)

    moved_count = 0
    failed_count = 0

    for i, message in enumerate(messages, 1):
        subject = message.get('subject', 'No Subject')
        received = message.get('receivedDateTime', 'Unknown')

        # Show progress every 50 messages
        if i % 50 == 0 or i == 1:
            print(f"\n[{i}/{len(messages)}] Moving messages...")

        if move_message(client, message['id'], source_folder_id, dest_folder_id):
            moved_count += 1
        else:
            failed_count += 1
            print(f"   ❌ Failed: {subject[:60]}")

    # Summary
    print(f"\n" + "=" * 80)
    print(f"SUMMARY")
    print(f"=" * 80)
    print(f"\n✅ Successfully moved: {moved_count} messages")

    if failed_count > 0:
        print(f"❌ Failed to move: {failed_count} messages")

    print(f"\n📊 Final Status:")
    print(f"   '{source_folder}': Should now be clean (or have only {failed_count} messages)")
    print(f"   '{dest_folder}': Should now have {moved_count} messages")

    print(f"\n💡 You can verify by checking these folders in Outlook")

    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
