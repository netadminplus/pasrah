#!/usr/bin/env python3
"""
PasRah - SSH Tunnel Manager
SSH Manager Module
"""

import paramiko
import socket
import time
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading
import io

class SSHManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.ssh_connections = {}  # server_id -> SSHClient
        self.ssh_key_path = Path(config_manager.config["ssh_keys"]["private_key_path"])
        self.ssh_pub_path = Path(config_manager.config["ssh_keys"]["public_key_path"])
        
        # Ensure SSH keys exist
        self._ensure_ssh_keys()
    
    def _ensure_ssh_keys(self):
        """Ensure SSH keys exist for PasRah"""
        ssh_dir = self.ssh_key_path.parent
        ssh_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.ssh_key_path.exists() or not self.ssh_pub_path.exists():
            print("🔑 Generating PasRah SSH keys...")
            self._generate_ssh_keys()
    
    def _generate_ssh_keys(self):
        """Generate new SSH key pair"""
        try:
            # Generate ed25519 key
            result = subprocess.run([
                'ssh-keygen', '-t', 'ed25519', 
                '-f', str(self.ssh_key_path),
                '-N', '',  # No passphrase
                '-C', 'PasRah-SSH-Manager'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Set proper permissions
                os.chmod(self.ssh_key_path, 0o600)
                os.chmod(self.ssh_pub_path, 0o644)
                print("✅ SSH keys generated successfully")
                return True
            else:
                print(f"❌ Failed to generate SSH keys: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error generating SSH keys: {e}")
            return False
    
    def test_connection(self, host: str, port: int, username: str, password: str) -> Tuple[bool, str]:
        """Test SSH connection to a server"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            start_time = time.time()
            ssh.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=self.config_manager.config["settings"]["ssh_timeout"]
            )
            
            # Test a simple command
            stdin, stdout, stderr = ssh.exec_command('echo "PasRah Connection Test"')
            output = stdout.read().decode().strip()
            
            ssh.close()
            
            response_time = round((time.time() - start_time) * 1000, 2)
            
            if "PasRah Connection Test" in output:
                self.config_manager.log_event(
                    "server_logs",
                    server_id=f"{host}:{port}",
                    event_type="connect",
                    message="Connection test successful",
                    response_time=response_time
                )
                return True, f"✅ Connection successful ({response_time}ms)"
            else:
                return False, "❌ Command execution failed"
                
        except paramiko.AuthenticationException:
            return False, "❌ Authentication failed - Invalid credentials"
        except paramiko.SSHException as e:
            return False, f"❌ SSH Error: {str(e)}"
        except socket.timeout:
            return False, "❌ Connection timeout"
        except Exception as e:
            return False, f"❌ Connection failed: {str(e)}"
    
    def setup_server(self, server_id: str, host: str, port: int, username: str, password: str, 
                    options: Dict = None) -> Tuple[bool, str]:
        """Setup a foreign server with SSH key and configuration"""
        options = options or {}
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to server
            ssh.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=self.config_manager.config["settings"]["ssh_timeout"]
            )
            
            setup_steps = []
            
            # Step 1: Copy SSH public key
            if self._copy_ssh_key(ssh, username):
                setup_steps.append("✅ SSH key copied")
            else:
                setup_steps.append("❌ Failed to copy SSH key")
                ssh.close()
                return False, "\n".join(setup_steps)
            
            # Step 2: Create non-root user if requested
            if options.get("create_user") and username == "root":
                if self._create_pasrah_user(ssh):
                    setup_steps.append("✅ PasRah user created")
                else:
                    setup_steps.append("⚠️ Failed to create PasRah user")
            
            # Step 3: Update system if requested
            if options.get("update_system"):
                if self._update_system(ssh):
                    setup_steps.append("✅ System updated")
                else:
                    setup_steps.append("⚠️ System update failed")
            
            # Step 4: Install fail2ban if requested
            if options.get("install_fail2ban"):
                if self._install_fail2ban(ssh):
                    setup_steps.append("✅ Fail2ban installed")
                else:
                    setup_steps.append("⚠️ Fail2ban installation failed")
            
            # Step 5: Configure SSH hardening
            if options.get("ssh_hardening"):
                if self._configure_ssh_hardening(ssh):
                    setup_steps.append("✅ SSH hardening applied")
                else:
                    setup_steps.append("⚠️ SSH hardening failed")
            
            ssh.close()
            
            # Update server status
            self.config_manager.update_server_status(server_id, "active")
            self.config_manager.log_event(
                "server_logs",
                server_id=server_id,
                event_type="setup",
                message="Server setup completed"
            )
            
            return True, "\n".join(setup_steps)
            
        except Exception as e:
            return False, f"❌ Server setup failed: {str(e)}"
    
    def _copy_ssh_key(self, ssh: paramiko.SSHClient, username: str) -> bool:
        """Copy SSH public key to remote server"""
        try:
            # Read public key
            with open(self.ssh_pub_path, 'r') as f:
                public_key = f.read().strip()
            
            # Create .ssh directory and authorized_keys
            commands = [
                f"mkdir -p ~/.ssh",
                f"chmod 700 ~/.ssh",
                f"echo '{public_key}' >> ~/.ssh/authorized_keys",
                f"chmod 600 ~/.ssh/authorized_keys",
                f"sort ~/.ssh/authorized_keys | uniq > ~/.ssh/authorized_keys.tmp",
                f"mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys"
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if stderr.channel.recv_exit_status() != 0:
                    error = stderr.read().decode().strip()
                    if error:  # Only log if there's actual error content
                        print(f"Warning in SSH key setup: {error}")
            
            # Test key-based authentication
            return self._test_key_auth(ssh.get_transport().getpeername()[0], username)
            
        except Exception as e:
            print(f"Error copying SSH key: {e}")
            return False
    
    def _test_key_auth(self, host: str, username: str) -> bool:
        """Test SSH key-based authentication"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=host,
                username=username,
                key_filename=str(self.ssh_key_path),
                timeout=10
            )
            
            stdin, stdout, stderr = ssh.exec_command('echo "Key auth test"')
            result = stdout.read().decode().strip()
            ssh.close()
            
            return "Key auth test" in result
        except:
            return False
    
    def _create_pasrah_user(self, ssh: paramiko.SSHClient) -> bool:
        """Create a dedicated PasRah user"""
        try:
            commands = [
                "useradd -m -s /bin/bash pasrah",
                "usermod -aG sudo pasrah",
                "mkdir -p /home/pasrah/.ssh",
                "cp ~/.ssh/authorized_keys /home/pasrah/.ssh/",
                "chown -R pasrah:pasrah /home/pasrah/.ssh",
                "chmod 700 /home/pasrah/.ssh",
                "chmod 600 /home/pasrah/.ssh/authorized_keys"
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                exit_status = stderr.channel.recv_exit_status()
                if exit_status != 0:
                    error = stderr.read().decode().strip()
                    # User might already exist, that's ok
                    if "already exists" not in error and error:
                        return False
            
            return True
        except:
            return False
    
    def _update_system(self, ssh: paramiko.SSHClient) -> bool:
        """Update system packages"""
        try:
            # Detect package manager and update
            stdin, stdout, stderr = ssh.exec_command("which apt-get")
            if stdout.channel.recv_exit_status() == 0:
                # Ubuntu/Debian
                update_cmd = "apt-get update && apt-get upgrade -y"
            else:
                # CentOS/RHEL
                update_cmd = "yum update -y"
            
            stdin, stdout, stderr = ssh.exec_command(update_cmd, timeout=300)
            return stderr.channel.recv_exit_status() == 0
        except:
            return False
    
    def _install_fail2ban(self, ssh: paramiko.SSHClient) -> bool:
        """Install and configure fail2ban"""
        try:
            # Detect package manager and install
            stdin, stdout, stderr = ssh.exec_command("which apt-get")
            if stdout.channel.recv_exit_status() == 0:
                install_cmd = "apt-get install -y fail2ban"
            else:
                install_cmd = "yum install -y fail2ban"
            
            stdin, stdout, stderr = ssh.exec_command(install_cmd)
            if stderr.channel.recv_exit_status() != 0:
                return False
            
            # Enable and start fail2ban
            stdin, stdout, stderr = ssh.exec_command("systemctl enable fail2ban && systemctl start fail2ban")
            return stderr.channel.recv_exit_status() == 0
        except:
            return False
    
    def _configure_ssh_hardening(self, ssh: paramiko.SSHClient) -> bool:
        """Apply SSH security hardening"""
        try:
            hardening_config = """
# PasRah SSH Hardening
PermitRootLogin yes
PasswordAuthentication yes
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
PermitEmptyPasswords no
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding no
PrintMotd no
TCPKeepAlive yes
ClientAliveInterval 60
ClientAliveCountMax 3
MaxStartups 10:30:100
"""
            
            # Backup original config
            stdin, stdout, stderr = ssh.exec_command("cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup")
            
            # Apply hardening (append to avoid breaking existing config)
            stdin, stdout, stderr = ssh.exec_command(f"echo '{hardening_config}' >> /etc/ssh/sshd_config")
            
            # Restart SSH service
            stdin, stdout, stderr = ssh.exec_command("systemctl restart ssh || systemctl restart sshd")
            
            return stderr.channel.recv_exit_status() == 0
        except:
            return False
    
    def connect_with_key(self, server_id: str) -> Optional[paramiko.SSHClient]:
        """Connect to server using SSH key"""
        server = self.config_manager.get_server(server_id)
        if not server:
            return None
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=server["host"],
                port=server["port"],
                username=server["username"],
                key_filename=str(self.ssh_key_path),
                timeout=self.config_manager.config["settings"]["ssh_timeout"]
            )
            
            self.ssh_connections[server_id] = ssh
            self.config_manager.update_server_status(server_id, "connected")
            
            return ssh
        except Exception as e:
            self.config_manager.update_server_status(server_id, "error")
            self.config_manager.log_event(
                "server_logs",
                server_id=server_id,
                event_type="error",
                message=f"Connection failed: {str(e)}"
            )
            return None
    
    def disconnect(self, server_id: str):
        """Disconnect from server"""
        if server_id in self.ssh_connections:
            try:
                self.ssh_connections[server_id].close()
                del self.ssh_connections[server_id]
                self.config_manager.update_server_status(server_id, "disconnected")
            except:
                pass
    
    def execute_command(self, server_id: str, command: str) -> Tuple[bool, str, str]:
        """Execute command on remote server"""
        ssh = self.ssh_connections.get(server_id)
        if not ssh:
            ssh = self.connect_with_key(server_id)
            if not ssh:
                return False, "", "Not connected to server"
        
        try:
            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            exit_status = stderr.channel.recv_exit_status()
            
            return exit_status == 0, output, error
        except Exception as e:
            return False, "", str(e)
    
    def check_server_health(self, server_id: str) -> Dict:
        """Check server health and gather system info"""
        ssh = self.connect_with_key(server_id)
        if not ssh:
            return {"status": "unreachable", "error": "Cannot connect"}
        
        health_data = {"status": "healthy", "metrics": {}}
        
        try:
            # System uptime
            success, output, _ = self.execute_command(server_id, "uptime")
            if success:
                health_data["metrics"]["uptime"] = output
            
            # Memory usage
            success, output, _ = self.execute_command(server_id, "free -h")
            if success:
                health_data["metrics"]["memory"] = output
            
            # Disk usage
            success, output, _ = self.execute_command(server_id, "df -h /")
            if success:
                health_data["metrics"]["disk"] = output
            
            # CPU load
            success, output, _ = self.execute_command(server_id, "cat /proc/loadavg")
            if success:
                health_data["metrics"]["load"] = output
            
            # Network connectivity
            start_time = time.time()
            success, output, _ = self.execute_command(server_id, "ping -c 1 8.8.8.8")
            if success:
                response_time = round((time.time() - start_time) * 1000, 2)
                health_data["metrics"]["network"] = f"OK ({response_time}ms)"
            else:
                health_data["metrics"]["network"] = "Failed"
                health_data["status"] = "degraded"
            
        except Exception as e:
            health_data["status"] = "error"
            health_data["error"] = str(e)
        
        return health_data
    
    def get_public_key(self) -> str:
        """Get the public key content"""
        try:
            with open(self.ssh_pub_path, 'r') as f:
                return f.read().strip()
        except:
            return ""

# Example usage
if __name__ == "__main__":
    from config_manager import ConfigManager
    
    config = ConfigManager()
    ssh_manager = SSHManager(config)
    
    # Test connection
    success, message = ssh_manager.test_connection(
        "46.8.233.208", 22, "root", "your_password"
    )
    print(f"Connection test: {message}")
    
    if success:
        # Setup server
        success, setup_message = ssh_manager.setup_server(
            "server1", "46.8.233.208", 22, "root", "your_password",
            {"update_system": False, "install_fail2ban": False}
        )
        print(f"Server setup: {setup_message}")