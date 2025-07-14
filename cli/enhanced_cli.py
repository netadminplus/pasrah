#!/usr/bin/env python3
"""
PasRah Complete Enhanced CLI
"""

import os
import sys
import getpass
from time import sleep

# Add core modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigManager
from core.ssh_manager import SSHManager
from core.tunnel_manager import TunnelManager
from core.web_auth import WebAuthManager

def show_logo():
    """Display PasRah ASCII logo"""
    logo = """
 ██████╗  █████╗ ███████╗██████╗  █████╗ ██╗  ██╗
 ██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗██║  ██║
 ██████╔╝███████║███████╗██████╔╝███████║███████║
 ██╔═══╝ ██╔══██║╚════██║██╔══██╗██╔══██║██╔══██║
 ██║     ██║  ██║███████║██║  ██║██║  ██║██║  ██║
 ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
    
    🚇 SSH Tunnel Manager - Making Connections Possible 🌐
    ══════════════════════════════════════════════════════
    Created with ❤️  by Ramtiin | Youtube.com/NetAdminPlus
    ══════════════════════════════════════════════════════
    """
    print(logo)

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name == 'posix' else 'cls')

def change_web_password():
    """Change web dashboard password"""
    config_manager = ConfigManager()
    web_auth = WebAuthManager(config_manager)
    
    print("\n🔐 Change Web Dashboard Password")
    print("=" * 40)
    
    # Get current username
    web_config = config_manager.config.get("web_auth", {})
    current_username = web_config.get("username", "admin")
    
    print(f"Current username: {current_username}")
    
    # Get current password for verification
    current_password = getpass.getpass("Enter current password: ")
    
    # Verify current password
    token = web_auth.authenticate(current_username, current_password)
    if not token:
        print("❌ Current password is incorrect!")
        return False
    
    # Get new password
    new_password = getpass.getpass("Enter new password: ")
    confirm_password = getpass.getpass("Confirm new password: ")
    
    if new_password != confirm_password:
        print("❌ Passwords don't match!")
        return False
    
    if len(new_password) < 4:
        print("❌ Password must be at least 4 characters!")
        return False
    
    # Update password
    success = web_auth.change_password(current_password, new_password)
    if success:
        print("✅ Password changed successfully!")
        print(f"🌐 Web Dashboard: http://YOUR-SERVER-IP:8080")
        print(f"👤 Username: {current_username}")
        print("🔑 Password: [UPDATED]")
        return True
    else:
        print("❌ Failed to change password!")
        return False

def show_web_credentials():
    """Show current web credentials"""
    config_manager = ConfigManager()
    web_config = config_manager.config.get("web_auth", {})
    
    if not web_config:
        print("❌ Web authentication not configured!")
        return
    
    username = web_config.get("username", "Unknown")
    print(f"\n🌐 Web Dashboard Access:")
    print(f"   URL: http://YOUR-SERVER-IP:8080")
    print(f"   Username: {username}")
    print(f"   Password: [Use option 9 to change]")

def add_server():
    """Add a remote server"""
    config_manager = ConfigManager()
    ssh_manager = SSHManager(config_manager)
    
    clear_screen()
    show_logo()
    print("🌐 Add Remote Server")
    print("-" * 30)
    print()
    
    try:
        host = input("Host/IP address: ").strip()
        port = input("SSH Port [22]: ").strip() or "22"
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        
        if not all([host, username, password]):
            print("\n❌ All fields are required!")
            input("Press Enter to continue...")
            return
        
        port = int(port)
        
        print(f"\n🔍 Testing connection to {host}:{port}...")
        success, message = ssh_manager.test_connection(host, port, username, password)
        
        if success:
            print(f"✅ {message}")
            
            # Ask for setup options
            print("\n🔧 Server Setup Options:")
            update_system = input("Update system packages? [y/N]: ").lower().startswith('y')
            install_fail2ban = input("Install fail2ban security? [y/N]: ").lower().startswith('y')
            create_user = input("Create dedicated user? [y/N]: ").lower().startswith('y')
            ssh_hardening = input("Apply SSH hardening? [y/N]: ").lower().startswith('y')
            
            options = {
                "update_system": update_system,
                "install_fail2ban": install_fail2ban,
                "create_user": create_user,
                "ssh_hardening": ssh_hardening
            }
            
            server_id = f"{host}_{port}"
            
            # Add server to config
            config_manager.add_server(server_id, {
                "host": host,
                "port": port,
                "username": username,
                "password": password
            })
            
            print(f"\n🔧 Setting up server '{server_id}'...")
            print("This may take a few minutes...")
            
            setup_success, setup_message = ssh_manager.setup_server(
                server_id, host, port, username, password, options
            )
            
            if setup_success:
                print(f"\n✅ Server '{server_id}' added successfully!")
                print(f"\nSetup details:\n{setup_message}")
            else:
                print(f"\n❌ Server setup failed:\n{setup_message}")
        else:
            print(f"❌ {message}")
            
    except ValueError:
        print("\n❌ Invalid port number!")
    except KeyboardInterrupt:
        print("\n\n🚫 Operation cancelled")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
    
    input("\nPress Enter to continue...")

def add_tunnel():
    """Add an SSH tunnel"""
    config_manager = ConfigManager()
    tunnel_manager = TunnelManager(config_manager, SSHManager(config_manager))
    
    clear_screen()
    show_logo()
    print("🚇 Add SSH Tunnel")
    print("-" * 30)
    print()
    
    servers = config_manager.get_servers()
    if not servers:
        print("❌ No remote servers configured!")
        print("Please add a server first.")
        input("Press Enter to continue...")
        return
    
    # Show available servers
    print("Available servers:")
    server_list = list(servers.items())
    for i, (server_id, server) in enumerate(server_list, 1):
        print(f"   [{i}] {server_id}: {server['host']}:{server['port']}")
    print()
    
    try:
        choice = input(f"Select server [1-{len(server_list)}]: ").strip()
        server_index = int(choice) - 1
        
        if server_index < 0 or server_index >= len(server_list):
            print("❌ Invalid server selection!")
            input("Press Enter to continue...")
            return
        
        selected_server_id = server_list[server_index][0]
        
        # Get tunnel details
        name = input("Tunnel name: ").strip()
        local_port = input("Local port: ").strip()
        remote_port = input("Remote port: ").strip()
        remote_host = input("Remote host [localhost]: ").strip() or "localhost"
        description = input("Description (optional): ").strip()
        auto_start = input("Auto-start tunnel? [Y/n]: ").lower() != 'n'
        
        if not all([name, local_port, remote_port]):
            print("\n❌ Name, local port, and remote port are required!")
            input("Press Enter to continue...")
            return
        
        local_port = int(local_port)
        remote_port = int(remote_port)
        
        tunnel_id = f"{name}_{local_port}".replace(" ", "_").lower()
        
        # Add tunnel to config
        success = config_manager.add_tunnel(tunnel_id, {
            "name": name,
            "server_id": selected_server_id,
            "local_port": local_port,
            "remote_port": remote_port,
            "remote_host": remote_host,
            "description": description,
            "auto_start": auto_start
        })
        
        if success:
            print(f"\n✅ Tunnel '{name}' created successfully!")
            
            if auto_start:
                print("🚇 Starting tunnel...")
                tunnel_success, tunnel_message = tunnel_manager.create_tunnel(tunnel_id)
                if tunnel_success:
                    print(f"✅ {tunnel_message}")
                    print(f"\n🌐 Users can now connect to:")
                    print(f"   Local Server IP:{local_port}")
                else:
                    print(f"❌ Failed to start tunnel: {tunnel_message}")
        else:
            print("❌ Failed to create tunnel configuration!")
            
    except ValueError:
        print("❌ Invalid port number!")
    except KeyboardInterrupt:
        print("\n\n🚫 Operation cancelled")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    input("Press Enter to continue...")

def manage_tunnels():
    """Start/Stop tunnels"""
    config_manager = ConfigManager()
    tunnel_manager = TunnelManager(config_manager, SSHManager(config_manager))
    
    clear_screen()
    show_logo()
    print("🚇 Start/Stop Tunnels")
    print("-" * 30)
    print()
    
    tunnels = config_manager.get_tunnels()
    if not tunnels:
        print("❌ No tunnels configured!")
        input("Press Enter to continue...")
        return
    
    # Show tunnels with status
    tunnel_list = list(tunnels.items())
    for i, (tunnel_id, tunnel) in enumerate(tunnel_list, 1):
        status = tunnel_manager.get_tunnel_status(tunnel_id)
        print(f"   [{i}] {tunnel['name']}: {tunnel['local_port']} -> {tunnel['remote_host']}:{tunnel['remote_port']} [{status['status']}]")
    print()
    
    try:
        choice = input(f"Select tunnel [1-{len(tunnel_list)}]: ").strip()
        tunnel_index = int(choice) - 1
        
        if tunnel_index < 0 or tunnel_index >= len(tunnel_list):
            print("❌ Invalid tunnel selection!")
            input("Press Enter to continue...")
            return
        
        tunnel_id = tunnel_list[tunnel_index][0]
        tunnel = tunnels[tunnel_id]
        status = tunnel_manager.get_tunnel_status(tunnel_id)
        
        if status['status'] == 'active':
            print(f"\n🛑 Stopping tunnel '{tunnel['name']}'...")
            success, message = tunnel_manager.destroy_tunnel(tunnel_id)
        else:
            print(f"\n🚀 Starting tunnel '{tunnel['name']}'...")
            success, message = tunnel_manager.create_tunnel(tunnel_id)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            
    except ValueError:
        print("❌ Invalid selection!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    input("Press Enter to continue...")

def remove_items():
    """Remove servers or tunnels"""
    clear_screen()
    show_logo()
    print("🗑️ Remove Items")
    print("-" * 20)
    print()
    print("   [1] Remove Server")
    print("   [2] Remove Tunnel")
    print("   [0] Back to Main Menu")
    print()
    
    choice = input("Enter your choice [0-2]: ").strip()
    
    if choice == "1":
        remove_server()
    elif choice == "2":
        remove_tunnel()
    elif choice == "0":
        return
    else:
        print("❌ Invalid choice!")
        input("Press Enter to continue...")

def remove_server():
    """Remove a server"""
    config_manager = ConfigManager()
    
    servers = config_manager.get_servers()
    if not servers:
        print("❌ No servers configured!")
        input("Press Enter to continue...")
        return
    
    print("\nAvailable servers:")
    server_list = list(servers.items())
    for i, (server_id, server) in enumerate(server_list, 1):
        print(f"   [{i}] {server_id}: {server['host']}:{server['port']}")
    print()
    
    try:
        choice = input(f"Select server to remove [1-{len(server_list)}]: ").strip()
        server_index = int(choice) - 1
        
        if server_index < 0 or server_index >= len(server_list):
            print("❌ Invalid server selection!")
            input("Press Enter to continue...")
            return
        
        server_id = server_list[server_index][0]
        
        confirm = input(f"Are you sure you want to remove '{server_id}'? [y/N]: ").lower()
        if confirm.startswith('y'):
            success = config_manager.remove_server(server_id)
            if success:
                print(f"✅ Server '{server_id}' removed successfully!")
            else:
                print(f"❌ Failed to remove server '{server_id}'")
        else:
            print("🚫 Operation cancelled")
            
    except ValueError:
        print("❌ Invalid selection!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    input("Press Enter to continue...")

def remove_tunnel():
    """Remove a tunnel"""
    config_manager = ConfigManager()
    tunnel_manager = TunnelManager(config_manager, SSHManager(config_manager))
    
    tunnels = config_manager.get_tunnels()
    if not tunnels:
        print("❌ No tunnels configured!")
        input("Press Enter to continue...")
        return
    
    print("\nAvailable tunnels:")
    tunnel_list = list(tunnels.items())
    for i, (tunnel_id, tunnel) in enumerate(tunnel_list, 1):
        print(f"   [{i}] {tunnel['name']}: {tunnel['local_port']} -> {tunnel['remote_host']}:{tunnel['remote_port']}")
    print()
    
    try:
        choice = input(f"Select tunnel to remove [1-{len(tunnel_list)}]: ").strip()
        tunnel_index = int(choice) - 1
        
        if tunnel_index < 0 or tunnel_index >= len(tunnel_list):
            print("❌ Invalid tunnel selection!")
            input("Press Enter to continue...")
            return
        
        tunnel_id = tunnel_list[tunnel_index][0]
        tunnel = tunnels[tunnel_id]
        
        confirm = input(f"Are you sure you want to remove '{tunnel['name']}'? [y/N]: ").lower()
        if confirm.startswith('y'):
            # Stop tunnel if running
            status = tunnel_manager.get_tunnel_status(tunnel_id)
            if status['status'] == 'active':
                tunnel_manager.destroy_tunnel(tunnel_id)
            
            success = config_manager.remove_tunnel(tunnel_id)
            if success:
                print(f"✅ Tunnel '{tunnel['name']}' removed successfully!")
            else:
                print(f"❌ Failed to remove tunnel '{tunnel['name']}'")
        else:
            print("🚫 Operation cancelled")
            
    except ValueError:
        print("❌ Invalid selection!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    input("Press Enter to continue...")

def show_status():
    """Show system status"""
    config_manager = ConfigManager()
    tunnel_manager = TunnelManager(config_manager, SSHManager(config_manager))
    
    clear_screen()
    show_logo()
    print("📊 System Status")
    print("-" * 20)
    print()
    
    # Show servers
    servers = config_manager.get_servers()
    print(f"🌐 Remote Servers: {len(servers)}")
    for server_id, server in servers.items():
        print(f"   • {server_id}: {server['host']}:{server['port']} [active]")
    print()
    
    # Show tunnels
    tunnels = config_manager.get_tunnels()
    print(f"🚇 SSH Tunnels: {len(tunnels)}")
    active_count = 0
    for tunnel_id, tunnel in tunnels.items():
        status = tunnel_manager.get_tunnel_status(tunnel_id)
        if status['status'] == 'active':
            active_count += 1
        print(f"   • {tunnel['name']}: {tunnel['local_port']} -> {tunnel['remote_host']}:{tunnel['remote_port']} [{status['status']}]")
    
    print(f"\n✅ Active Tunnels: {active_count}")
    
    input("\nPress Enter to continue...")

def enhanced_cli_menu():
    """Enhanced CLI menu with logo and all features"""
    
    while True:
        clear_screen()
        show_logo()
        
        print("\n📋 PasRah Management Menu:")
        print("   [1] 🌐 Add Remote Server")
        print("   [2] 🚇 Add SSH Tunnel")
        print("   [3] ▶️  Start/Stop Tunnel")
        print("   [4] 🗑️  Remove Server/Tunnel")
        print("   [5] 📊 Show Status")
        print("   [6] 💾 Backup/Export Config")
        print("   [7] 🌐 Show Web Credentials")
        print("   [8] 🔄 Restart Web Server")
        print("   [9] 🔐 Change Web Password")
        print("   [0] 🚪 Exit")
        
        show_web_credentials()
        print("\n" + "="*60)
        
        choice = input("Enter your choice [0-9]: ").strip()
        
        if choice == "1":
            add_server()
        elif choice == "2":
            add_tunnel()
        elif choice == "3":
            manage_tunnels()
        elif choice == "4":
            remove_items()
        elif choice == "5":
            show_status()
        elif choice == "6":
            print("💾 Backup feature - Use web interface for full backup functionality")
            input("Press Enter to continue...")
        elif choice == "7":
            clear_screen()
            show_logo()
            show_web_credentials()
            input("\nPress Enter to continue...")
        elif choice == "8":
            print("🔄 Restarting web server...")
            os.system("pkill -f 'python3.*start_web.py'")
            os.system("cd ~/pasrah && nohup python3 start_web.py > /dev/null 2>&1 &")
            print("✅ Web server restarted!")
            sleep(2)
        elif choice == "9":
            clear_screen()
            show_logo()
            change_web_password()
            input("\nPress Enter to continue...")
        elif choice == "0":
            print("\n👋 Thanks for using PasRah!")
            break
        else:
            print("❌ Invalid choice!")
            input("Press Enter to continue...")

if __name__ == "__main__":
    try:
        enhanced_cli_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")