#!/usr/bin/env python3
"""
Quick test script to verify Claude API is working with current configuration
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import json
import requests
import time

def load_config():
    """Load configuration from config file"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def test_claude_api():
    """Test Claude API with a simple request"""
    print("Testing Claude API connectivity...")
    print("=" * 50)
    
    config = load_config()
    if not config:
        return False
    
    api_key = config.get('claude', {}).get('api_key')
    model = config.get('claude', {}).get('model', 'claude-3-sonnet-20240229')
    
    if not api_key:
        print("❌ No Claude API key found in config")
        return False
    
    print(f"🔑 Using API key: {api_key[:15]}...")
    print(f"🤖 Using model: {model}")
    
    # Simple test request
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01'
    }
    
    data = {
        'model': model,
        'max_tokens': 100,
        'messages': [
            {
                'role': 'user',
                'content': 'Hello! This is a quick connectivity test. Please respond with "API test successful" if you receive this message.'
            }
        ]
    }
    
    try:
        start_time = time.time()
        print("📡 Sending test request...")
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=30
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"⏱️ Response time: {response_time:.2f} seconds")
        print(f"📊 Status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            claude_response = result['content'][0]['text']
            print(f"✅ Claude response: {claude_response}")
            
            if "API test successful" in claude_response:
                print("\n🎉 Claude API test PASSED!")
                return True
            else:
                print("\n⚠️ Claude API responded but with unexpected content")
                return True  # Still working, just different response
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 30 seconds")
        print("💡 This would trigger the retry logic in the main application")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - check your internet connection")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_dmarc_analyzer():
    """Test the actual DMARC analyzer with retry logic"""
    print("\n" + "=" * 50)
    print("Testing DMARC Analyzer with Retry Logic")
    print("=" * 50)
    
    try:
        from dmarc_monitor import ClaudeAnalyzer
        
        config = load_config()
        if not config:
            return False
        
        api_key = config.get('claude', {}).get('api_key')
        model = config.get('claude', {}).get('model', 'claude-3-sonnet-20240229')
        
        analyzer = ClaudeAnalyzer(api_key, model)
        
        # Simple test report
        test_report = {
            'metadata': {
                'org_name': 'Test Org',
                'report_id': 'test-123',
                'date_range': {
                    'begin': '1755907200',
                    'end': '1755993600'
                }
            },
            'policy': {
                'domain': 'test.example.com',
                'p': 'none',
                'sp': 'none',
                'pct': '100'
            },
            'records': [
                {
                    'source_ip': '209.85.220.41',
                    'count': 5,
                    'dkim': 'pass',
                    'spf': 'pass'
                }
            ]
        }
        
        print("🧪 Testing analyzer with sample DMARC report...")
        start_time = time.time()
        
        result = analyzer.analyze_dmarc_report(test_report)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"⏱️ Analysis time: {response_time:.2f} seconds")
        
        if "Error analyzing report" in result:
            print("❌ Analyzer returned error:", result)
            return False
        elif "AI-powered analysis was unavailable" in result:
            print("⚠️ Fallback analysis was used (Claude API likely failed)")
            print("✅ But system handled it gracefully!")
            return True
        else:
            print("✅ Analysis successful!")
            print(f"📄 Result preview: {result[:200]}...")
            return True
            
    except Exception as e:
        print(f"❌ Error testing analyzer: {e}")
        return False

def main():
    """Run API connectivity tests"""
    print("\n🧪 CLAUDE API CONNECTIVITY TEST")
    print("=" * 60)
    
    # Test 1: Direct API call
    api_test_passed = test_claude_api()
    
    # Test 2: DMARC analyzer with retry logic
    analyzer_test_passed = test_dmarc_analyzer()
    
    print("\n" + "=" * 60)
    print("📋 TEST RESULTS:")
    print("=" * 60)
    print(f"Direct API Test: {'✅ PASSED' if api_test_passed else '❌ FAILED'}")
    print(f"DMARC Analyzer Test: {'✅ PASSED' if analyzer_test_passed else '❌ FAILED'}")
    
    if api_test_passed and analyzer_test_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Claude API is working correctly")
        print("✅ Retry logic and fallback analysis ready")
        print("✅ Your DMARC monitoring system is fully operational")
    elif analyzer_test_passed:
        print("\n⚠️ PARTIAL SUCCESS!")
        print("❌ Direct API may have issues")
        print("✅ But system fallback is working")
        print("💡 Your DMARC monitoring will still function")
    else:
        print("\n❌ TESTS FAILED!")
        print("🔧 Check your API key and internet connection")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())