#!/usr/bin/env python3
"""
PasRah - Simple CLI Version
SSH Tunnel Manager
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

class PasRahCLI:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.ssh_manager = SSHManager(self.config_manager)
        self.tunnel_manager = TunnelManager(self.config_manager, self.ssh_manager)
    
    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_header(self):
        print("=" * 60)
        print("🚇 PasRah - SSH Tunnel Manager v1.0")
        print("=" * 60)
        print()
    
    def print_footer(self):
        print()
        print("-" * 60)
        print("Created with ❤️ by Ramtiin | Youtube.com/NetAdminPlus")
        print("-" * 60)
    
    def show_main_menu(self):
        while True:
            self.clear_screen()
            self.print_header()
            
            # Show statistics
            servers = self.config_manager.get_servers()
            tunnels = self.config_manager.get_tunnels()
            active_tunnels = len(self.tunnel_manager.active_tunnels)
            
            print(f"📊 Dashboard:")
            print(f"   🌐 Remote Servers: {len(servers)}")
            print(f"   🚇 Total Tunnels: {len(tunnels)}")
            print(f"   ✅ Active Tunnels: {active_tunnels}")
            print()
            
            # Show servers
            print("🌐 Remote Servers:")
            if servers:
                for server_id, server in servers.items():
                    status = server.get('status', 'unknown')
                    print(f"   • {server_id}: {server['host']}:{server['port']} [{status}]")
            else:
                print("   No servers configured")
            print()
            
            # Show tunnels
            print("🚇 SSH Tunnels:")
            if tunnels:
                for tunnel_id, tunnel in tunnels.items():
                    status = self.tunnel_manager.get_tunnel_status(tunnel_id)
                    print(f"   • {tunnel['name']}: {tunnel['local_port']} -> {tunnel['remote_host']}:{tunnel['remote_port']} [{status['status']}]")
            else:
                print("   No tunnels configured")
            print()
            
            # Menu options
            print("🔄 Options:")
            print("   [1] Add Remote Server")
            print("   [2] Add Tunnel")
            print("   [3] Start/Stop Tunnel")
            print("   [4] Remove Server/Tunnel")
            print("   [5] Refresh Status")
            print("   [6] Export/Import Config")
            print("   [0] Exit")
            print()
            
            self.print_footer()
            
            choice = input("Enter your choice [0-6]: ").strip()
            
            if choice == "1":
                self.add_server()
            elif choice == "2":
                self.add_tunnel()
            elif choice == "3":
                self.manage_tunnels()
            elif choice == "4":
                self.remove_items()
            elif choice == "5":
                self.refresh_status()
            elif choice == "6":
                self.config_management()
            elif choice == "0":
                print("\n👋 Thanks for using PasRah!")
                break
            else:
                print("\n❌ Invalid choice. Press Enter to continue...")
                input()
    
    def add_server(self):
        self.clear_screen()
        self.print_header()
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
            success, message = self.ssh_manager.test_connection(host, port, username, password)
            
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
                self.config_manager.add_server(server_id, {
                    "host": host,
                    "port": port,
                    "username": username,
                    "password": password
                })
                
                print(f"\n🔧 Setting up server '{server_id}'...")
                print("This may take a few minutes...")
                
                setup_success, setup_message = self.ssh_manager.setup_server(
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
    
    def add_tunnel(self):
        self.clear_screen()
        self.print_header()
        print("🚇 Add SSH Tunnel")
        print("-" * 30)
        print()
        
        servers = self.config_manager.get_servers()
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
            success = self.config_manager.add_tunnel(tunnel_id, {
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
                    tunnel_success, tunnel_message = self.tunnel_manager.create_tunnel(tunnel_id)
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
    
    def manage_tunnels(self):
        self.clear_screen()
        self.print_header()
        print("🚇 Start/Stop Tunnels")
        print("-" * 30)
        print()
        
        tunnels = self.config_manager.get_tunnels()
        if not tunnels:
            print("❌ No tunnels configured!")
            input("Press Enter to continue...")
            return
        
        # Show tunnels with status
        tunnel_list = list(tunnels.items())
        for i, (tunnel_id, tunnel) in enumerate(tunnel_list, 1):
            status = self.tunnel_manager.get_tunnel_status(tunnel_id)
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
            status = self.tunnel_manager.get_tunnel_status(tunnel_id)
            
            if status['status'] == 'active':
                print(f"\n🛑 Stopping tunnel '{tunnel['name']}'...")
                success, message = self.tunnel_manager.destroy_tunnel(tunnel_id)
            else:
                print(f"\n🚀 Starting tunnel '{tunnel['name']}'...")
                success, message = self.tunnel_manager.create_tunnel(tunnel_id)
            
            if success:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
                
        except ValueError:
            print("❌ Invalid selection!")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        input("Press Enter to continue...")
    
    def remove_items(self):
        print("🗑️ Remove feature - Coming soon!")
        input("Press Enter to continue...")
    
    def refresh_status(self):
        print("🔄 Refreshing status...")
        sleep(1)
        print("✅ Status refreshed!")
        input("Press Enter to continue...")
    
    def config_management(self):
        print("⚙️ Config management - Coming soon!")
        input("Press Enter to continue...")

if __name__ == "__main__":
    try:
        cli = PasRahCLI()
        cli.show_main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
