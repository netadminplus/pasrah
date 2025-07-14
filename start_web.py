#!/usr/bin/env python3
"""
PasRah Web Dashboard Starter - Improved
"""

import sys
import os
import requests

# Add paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config_manager import ConfigManager
from core.web_auth import WebAuthManager

def get_local_ip():
    """Get local server public IP"""
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return 'Unknown'

def get_country_flag(ip):
    """Get country flag for IP"""
    try:
        if ip.startswith(('192.168.', '10.', '172.')) or ip == '127.0.0.1':
            return '🖥️'
        
        # Simple mapping for common IPs
        if ip.startswith('167.172.'):
            return '🇩🇪'  # DigitalOcean Germany
        elif ip.startswith('164.92.'):
            return '🇺🇸'  # DigitalOcean US
        elif ip.startswith('46.8.'):
            return '🇩🇪'  # Germany
        elif ip.startswith('185.'):
            return '🇪🇺'  # Europe
        
        return '🌍'
    except:
        return '🌍'

def main():
    config_manager = ConfigManager()
    web_auth = WebAuthManager(config_manager)
    
    # Get local IP info
    local_ip = get_local_ip()
    local_flag = get_country_flag(local_ip)
    
    print("=" * 70)
    print("🚇 PasRah - SSH Tunnel Manager v1.0")
    print("=" * 70)
    print()
    
    # Check if web auth is set up
    web_auth_config = config_manager.config.get("web_auth")
    if not web_auth_config:
        print("🔐 PasRah Web Setup Required")
        print("-" * 40)
        print()
        
        username = input("Enter web admin username: ").strip()
        password = input("Enter web admin password: ").strip()
        
        if username and password:
            success = web_auth.setup_web_user(username, password)
            if success:
                print(f"\n✅ Web user '{username}' created successfully!")
            else:
                print("\n❌ Failed to create web user!")
                return
        else:
            print("\n❌ Username and password are required!")
            return
    
    print("🌐 Server Information:")
    print(f"   {local_flag} Local Server IP: {local_ip}")
    print()
    print("🎯 Access Methods:")
    print(f"   🌐 Web Dashboard: http://{local_ip}:8080")
    print(f"   💻 Terminal CLI:  python3 ~/pasrah/cli/simple_cli.py")
    print()
    print("📋 What's Next:")
    print("   1. Open web browser and login to the dashboard")
    print("   2. Add your remote servers")
    print("   3. Create SSH tunnels")
    print("   4. Share your tunnel access with users")
    print()
    print("🚀 Starting web server...")
    print("=" * 70)
    
    # Import and run the web app
    import uvicorn
    uvicorn.run(
        "web.backend.app:app", 
        host="0.0.0.0", 
        port=config_manager.config["settings"]["web_port"],
        reload=False
    )

if __name__ == "__main__":
    main()
