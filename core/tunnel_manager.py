#!/usr/bin/env python3
"""
PasRah - SSH Tunnel Manager
Enhanced Tunnel Manager Module with UDP Support
"""

import subprocess
import psutil
import time
import socket
import threading
import signal
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

class TunnelManager:
    def __init__(self, config_manager, ssh_manager):
        self.config_manager = config_manager
        self.ssh_manager = ssh_manager
        self.active_tunnels = {}  # tunnel_id -> process info
        self.monitoring_thread = None
        self.monitoring_active = False
        
        # Start monitoring thread
        self.start_monitoring()
    
    def create_tunnel(self, tunnel_id: str, bind_address: str = "0.0.0.0") -> Tuple[bool, str]:
        """Create an SSH tunnel (TCP or UDP)"""
        tunnel = self.config_manager.get_tunnel(tunnel_id)
        if not tunnel:
            return False, "❌ Tunnel configuration not found"
        
        server = self.config_manager.get_server(tunnel["server_id"])
        if not server:
            return False, "❌ Remote server configuration not found"
        
        # Check if local port is available
        if self._is_port_in_use(tunnel["local_port"]):
            return False, f"❌ Local port {tunnel['local_port']} is already in use"
        
        # Test remote server connectivity first
        connectivity_check = self._test_remote_connectivity(server["host"], server["port"])
        if not connectivity_check[0]:
            return False, f"❌ Remote server unreachable: {connectivity_check[1]}"
        
        try:
            tunnel_type = tunnel.get("tunnel_type", "tcp").lower()
            
            if tunnel_type == "udp":
                return self._create_udp_tunnel(tunnel_id, tunnel, server, bind_address)
            else:
                return self._create_tcp_tunnel(tunnel_id, tunnel, server, bind_address)
                
        except Exception as e:
            return False, f"❌ Failed to create tunnel: {str(e)}"
    
    def _create_tcp_tunnel(self, tunnel_id: str, tunnel: Dict, server: Dict, bind_address: str) -> Tuple[bool, str]:
        """Create a TCP SSH tunnel"""
        try:
            # Build SSH command
            ssh_key_path = self.config_manager.config["ssh_keys"]["private_key_path"]
            
            ssh_cmd = [
                "ssh",
                "-N",  # No command execution
                "-L", f"{bind_address}:{tunnel['local_port']}:{tunnel['remote_host']}:{tunnel['remote_port']}",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-i", ssh_key_path,
                "-p", str(server["port"]),
                f"{server['username']}@{server['host']}"
            ]
            
            # Start SSH tunnel process
            process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Wait a moment and check if process is still running
            time.sleep(2)
            
            if process.poll() is None:
                # Process is running, check if port is listening
                if self._wait_for_port(tunnel["local_port"], timeout=10):
                    self.active_tunnels[tunnel_id] = {
                        "process": process,
                        "pid": process.pid,
                        "started_at": time.time(),
                        "local_port": tunnel["local_port"],
                        "remote_host": tunnel["remote_host"],
                        "remote_port": tunnel["remote_port"],
                        "server_id": tunnel["server_id"],
                        "tunnel_type": "tcp",
                        "bytes_sent": 0,
                        "bytes_received": 0
                    }
                    
                    # Update config
                    self.config_manager.update_tunnel_status(tunnel_id, "active", process.pid)
                    
                    # Log event
                    self.config_manager.log_event(
                        "tunnel_logs",
                        tunnel_id=tunnel_id,
                        event_type="connect",
                        message=f"TCP tunnel created: {bind_address}:{tunnel['local_port']} -> {server['host']}:{tunnel['remote_port']}"
                    )
                    
                    return True, f"✅ TCP tunnel created successfully on port {tunnel['local_port']}"
                else:
                    # Port not listening, kill process
                    self._kill_process(process)
                    return False, f"❌ TCP tunnel failed to bind to port {tunnel['local_port']}"
            else:
                # Process died immediately
                stderr_output = process.stderr.read().decode() if process.stderr else ""
                return False, f"❌ TCP tunnel process failed: {stderr_output}"
                
        except Exception as e:
            return False, f"❌ Failed to create TCP tunnel: {str(e)}"
    
    def _create_udp_tunnel(self, tunnel_id: str, tunnel: Dict, server: Dict, bind_address: str) -> Tuple[bool, str]:
        """Create a UDP tunnel using socat bridges"""
        try:
            # First ensure socat is installed on remote server
            ssh = self.ssh_manager.connect_with_key(tunnel["server_id"])
            if not ssh:
                return False, "❌ Cannot connect to remote server"
            
            # Install socat if not present
            install_success = self._ensure_socat_installed(ssh)
            if not install_success:
                return False, "❌ Failed to install socat on remote server"
            
            # Find available intermediate TCP port on remote server
            intermediate_port = self._find_available_port(ssh, 10000, 20000)
            if not intermediate_port:
                return False, "❌ Cannot find available intermediate port on remote server"
            
            # Step 1: Create remote socat bridge (TCP -> UDP)
            remote_socat_cmd = f"socat TCP-LISTEN:{intermediate_port},fork,reuseaddr UDP:{tunnel['remote_host']}:{tunnel['remote_port']}"
            
            remote_process = self._start_remote_process(ssh, remote_socat_cmd)
            if not remote_process:
                return False, "❌ Failed to start remote socat bridge"
            
            # Step 2: Create SSH tunnel for the intermediate TCP connection
            ssh_key_path = self.config_manager.config["ssh_keys"]["private_key_path"]
            
            ssh_cmd = [
                "ssh",
                "-N",
                "-L", f"{bind_address}:{tunnel['local_port']}:localhost:{intermediate_port}",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-i", ssh_key_path,
                "-p", str(server["port"]),
                f"{server['username']}@{server['host']}"
            ]
            
            ssh_process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            time.sleep(2)
            
            if ssh_process.poll() is not None:
                return False, "❌ SSH tunnel process failed"
            
            # Step 3: Create local socat bridge (UDP -> TCP)
            local_socat_cmd = [
                "socat",
                f"UDP-LISTEN:{tunnel['local_port']},fork,reuseaddr",
                f"TCP:127.0.0.1:{tunnel['local_port']}"
            ]
            
            # We need to use a different local port for the socat connection
            local_tcp_port = self._find_local_available_port(tunnel['local_port'] + 1000, tunnel['local_port'] + 2000)
            if not local_tcp_port:
                self._kill_process(ssh_process)
                return False, "❌ Cannot find available local TCP port"
            
            # Update SSH tunnel to use the local TCP port
            self._kill_process(ssh_process)
            
            # Restart SSH tunnel with correct local TCP port
            ssh_cmd[2] = f"{bind_address}:{local_tcp_port}:localhost:{intermediate_port}"
            
            ssh_process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            time.sleep(2)
            
            if ssh_process.poll() is not None:
                return False, "❌ SSH tunnel process failed on retry"
            
            # Now create local socat bridge
            local_socat_cmd = [
                "socat",
                f"UDP-LISTEN:{tunnel['local_port']},fork,reuseaddr",
                f"TCP:127.0.0.1:{local_tcp_port}"
            ]
            
            local_socat_process = subprocess.Popen(
                local_socat_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            time.sleep(1)
            
            if local_socat_process.poll() is not None:
                self._kill_process(ssh_process)
                return False, "❌ Local socat bridge failed"
            
            # Store all processes for this UDP tunnel
            self.active_tunnels[tunnel_id] = {
                "ssh_process": ssh_process,
                "local_socat_process": local_socat_process,
                "remote_process_info": remote_process,
                "ssh_connection": ssh,
                "pid": ssh_process.pid,
                "started_at": time.time(),
                "local_port": tunnel["local_port"],
                "remote_host": tunnel["remote_host"],
                "remote_port": tunnel["remote_port"],
                "server_id": tunnel["server_id"],
                "tunnel_type": "udp",
                "intermediate_port": intermediate_port,
                "local_tcp_port": local_tcp_port,
                "bytes_sent": 0,
                "bytes_received": 0
            }
            
            # Update config
            self.config_manager.update_tunnel_status(tunnel_id, "active", ssh_process.pid)
            
            # Log event
            self.config_manager.log_event(
                "tunnel_logs",
                tunnel_id=tunnel_id,
                event_type="connect",
                message=f"UDP tunnel created: {bind_address}:{tunnel['local_port']} -> {server['host']}:{tunnel['remote_port']}"
            )
            
            return True, f"✅ UDP tunnel created successfully on port {tunnel['local_port']}"
            
        except Exception as e:
            return False, f"❌ Failed to create UDP tunnel: {str(e)}"
    
    def _ensure_socat_installed(self, ssh) -> bool:
        """Ensure socat is installed on remote server"""
        try:
            # Check if socat exists
            stdin, stdout, stderr = ssh.exec_command("which socat")
            if stdout.channel.recv_exit_status() == 0:
                return True
            
            # Try to install socat
            stdin, stdout, stderr = ssh.exec_command("which apt-get")
            if stdout.channel.recv_exit_status() == 0:
                # Ubuntu/Debian
                install_cmd = "apt-get update && apt-get install -y socat"
            else:
                # CentOS/RHEL
                install_cmd = "yum install -y socat || dnf install -y socat"
            
            stdin, stdout, stderr = ssh.exec_command(install_cmd)
            return stderr.channel.recv_exit_status() == 0
            
        except:
            return False
    
    def _find_available_port(self, ssh, start_port: int, end_port: int) -> Optional[int]:
        """Find an available port on remote server"""
        try:
            for port in range(start_port, end_port):
                stdin, stdout, stderr = ssh.exec_command(f"netstat -ln | grep :{port}")
                if stdout.channel.recv_exit_status() != 0:  # Port not in use
                    return port
            return None
        except:
            return None
    
    def _find_local_available_port(self, start_port: int, end_port: int) -> Optional[int]:
        """Find an available port on local machine"""
        for port in range(start_port, end_port):
            if not self._is_port_in_use(port):
                return port
        return None
    
    def _start_remote_process(self, ssh, command: str) -> Optional[Dict]:
        """Start a background process on remote server"""
        try:
            # Start process in background and get PID
            bg_command = f"nohup {command} > /dev/null 2>&1 & echo $!"
            stdin, stdout, stderr = ssh.exec_command(bg_command)
            
            pid_output = stdout.read().decode().strip()
            if pid_output.isdigit():
                pid = int(pid_output)
                return {"pid": pid, "command": command}
            
            return None
        except:
            return None
    
    def destroy_tunnel(self, tunnel_id: str) -> Tuple[bool, str]:
        """Destroy an SSH tunnel (TCP or UDP)"""
        if tunnel_id not in self.active_tunnels:
            return False, "❌ Tunnel is not active"
        
        try:
            tunnel_info = self.active_tunnels[tunnel_id]
            tunnel_type = tunnel_info.get("tunnel_type", "tcp")
            
            if tunnel_type == "udp":
                return self._destroy_udp_tunnel(tunnel_id, tunnel_info)
            else:
                return self._destroy_tcp_tunnel(tunnel_id, tunnel_info)
                
        except Exception as e:
            return False, f"❌ Failed to destroy tunnel: {str(e)}"
    
    def _destroy_tcp_tunnel(self, tunnel_id: str, tunnel_info: Dict) -> Tuple[bool, str]:
        """Destroy a TCP tunnel"""
        try:
            process = tunnel_info["process"]
            
            # Kill the process group
            self._kill_process(process)
            
            # Remove from active tunnels
            del self.active_tunnels[tunnel_id]
            
            # Update config
            self.config_manager.update_tunnel_status(tunnel_id, "inactive", None)
            
            # Log event
            self.config_manager.log_event(
                "tunnel_logs",
                tunnel_id=tunnel_id,
                event_type="disconnect",
                message="TCP tunnel destroyed by user"
            )
            
            return True, "✅ TCP tunnel destroyed successfully"
            
        except Exception as e:
            return False, f"❌ Failed to destroy TCP tunnel: {str(e)}"
    
    def _destroy_udp_tunnel(self, tunnel_id: str, tunnel_info: Dict) -> Tuple[bool, str]:
        """Destroy a UDP tunnel"""
        try:
            # Kill local socat process
            if "local_socat_process" in tunnel_info:
                self._kill_process(tunnel_info["local_socat_process"])
            
            # Kill SSH process
            if "ssh_process" in tunnel_info:
                self._kill_process(tunnel_info["ssh_process"])
            
            # Kill remote socat process
            if "remote_process_info" in tunnel_info and "ssh_connection" in tunnel_info:
                try:
                    ssh = tunnel_info["ssh_connection"]
                    remote_pid = tunnel_info["remote_process_info"]["pid"]
                    ssh.exec_command(f"kill {remote_pid}")
                except:
                    pass  # Best effort
            
            # Close SSH connection
            if "ssh_connection" in tunnel_info:
                try:
                    tunnel_info["ssh_connection"].close()
                except:
                    pass
            
            # Remove from active tunnels
            del self.active_tunnels[tunnel_id]
            
            # Update config
            self.config_manager.update_tunnel_status(tunnel_id, "inactive", None)
            
            # Log event
            self.config_manager.log_event(
                "tunnel_logs",
                tunnel_id=tunnel_id,
                event_type="disconnect",
                message="UDP tunnel destroyed by user"
            )
            
            return True, "✅ UDP tunnel destroyed successfully"
            
        except Exception as e:
            return False, f"❌ Failed to destroy UDP tunnel: {str(e)}"
    
    def restart_tunnel(self, tunnel_id: str) -> Tuple[bool, str]:
        """Restart an SSH tunnel"""
        # First destroy if active
        if tunnel_id in self.active_tunnels:
            destroy_result = self.destroy_tunnel(tunnel_id)
            if not destroy_result[0]:
                return destroy_result
        
        # Wait a moment
        time.sleep(1)
        
        # Then create
        return self.create_tunnel(tunnel_id)
    
    def get_tunnel_status(self, tunnel_id: str) -> Dict:
        """Get detailed tunnel status"""
        if tunnel_id not in self.active_tunnels:
            return {
                "status": "inactive",
                "message": "Tunnel is not running"
            }
        
        tunnel_info = self.active_tunnels[tunnel_id]
        tunnel_type = tunnel_info.get("tunnel_type", "tcp")
        
        if tunnel_type == "udp":
            return self._get_udp_tunnel_status(tunnel_id, tunnel_info)
        else:
            return self._get_tcp_tunnel_status(tunnel_id, tunnel_info)
    
    def _get_tcp_tunnel_status(self, tunnel_id: str, tunnel_info: Dict) -> Dict:
        """Get TCP tunnel status"""
        process = tunnel_info["process"]
        
        # Check if process is still alive
        if process.poll() is None:
            # Process is running, check port
            if self._is_port_in_use(tunnel_info["local_port"]):
                uptime = time.time() - tunnel_info["started_at"]
                return {
                    "status": "active",
                    "pid": tunnel_info["pid"],
                    "uptime": uptime,
                    "local_port": tunnel_info["local_port"],
                    "remote_endpoint": f"{tunnel_info['remote_host']}:{tunnel_info['remote_port']}",
                    "tunnel_type": "tcp",
                    "bytes_sent": tunnel_info["bytes_sent"],
                    "bytes_received": tunnel_info["bytes_received"]
                }
            else:
                return {
                    "status": "error",
                    "message": "Process running but port not listening"
                }
        else:
            # Process died
            return {
                "status": "dead",
                "message": "Tunnel process died unexpectedly"
            }
    
    def _get_udp_tunnel_status(self, tunnel_id: str, tunnel_info: Dict) -> Dict:
        """Get UDP tunnel status"""
        ssh_process = tunnel_info.get("ssh_process")
        local_socat_process = tunnel_info.get("local_socat_process")
        
        # Check if both processes are still alive
        ssh_alive = ssh_process and ssh_process.poll() is None
        socat_alive = local_socat_process and local_socat_process.poll() is None
        
        if ssh_alive and socat_alive:
            uptime = time.time() - tunnel_info["started_at"]
            return {
                "status": "active",
                "pid": tunnel_info["pid"],
                "uptime": uptime,
                "local_port": tunnel_info["local_port"],
                "remote_endpoint": f"{tunnel_info['remote_host']}:{tunnel_info['remote_port']}",
                "tunnel_type": "udp",
                "bytes_sent": tunnel_info["bytes_sent"],
                "bytes_received": tunnel_info["bytes_received"]
            }
        else:
            return {
                "status": "dead",
                "message": f"UDP tunnel components failed (SSH: {ssh_alive}, Socat: {socat_alive})"
            }
    
    def get_all_tunnels_status(self) -> Dict:
        """Get status of all tunnels"""
        status = {}
        all_tunnels = self.config_manager.get_tunnels()
        
        for tunnel_id in all_tunnels:
            status[tunnel_id] = self.get_tunnel_status(tunnel_id)
        
        return status
    
    def test_tunnel_connectivity(self, tunnel_id: str) -> Tuple[bool, str]:
        """Test if tunnel is working by connecting to local port"""
        tunnel = self.config_manager.get_tunnel(tunnel_id)
        if not tunnel:
            return False, "Tunnel configuration not found"
        
        tunnel_type = tunnel.get("tunnel_type", "tcp").lower()
        
        try:
            if tunnel_type == "tcp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('127.0.0.1', tunnel["local_port"]))
                sock.close()
                
                if result == 0:
                    return True, "✅ TCP tunnel is responding"
                else:
                    return False, "❌ TCP tunnel is not responding"
            else:
                # UDP test - send a test packet
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                sock.sendto(b"test", ('127.0.0.1', tunnel["local_port"]))
                sock.close()
                return True, "✅ UDP tunnel is responding"
                
        except Exception as e:
            return False, f"❌ Connection test failed: {str(e)}"
    
    def measure_tunnel_speed(self, tunnel_id: str) -> Dict:
        """Measure tunnel speed and latency"""
        tunnel = self.config_manager.get_tunnel(tunnel_id)
        if not tunnel:
            return {"error": "Tunnel not found"}
        
        server = self.config_manager.get_server(tunnel["server_id"])
        if not server:
            return {"error": "Remote server not found"}
        
        results = {}
        tunnel_type = tunnel.get("tunnel_type", "tcp").lower()
        
        try:
            # Test latency
            start_time = time.time()
            
            if tunnel_type == "tcp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('127.0.0.1', tunnel["local_port"]))
                sock.close()
                
                if result == 0:
                    latency = round((time.time() - start_time) * 1000, 2)
                    results["latency_ms"] = latency
                    results["status"] = "✅ Active"
                else:
                    results["status"] = "❌ Inactive"
                    results["latency_ms"] = None
            else:
                # UDP latency test
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                try:
                    sock.sendto(b"ping", ('127.0.0.1', tunnel["local_port"]))
                    latency = round((time.time() - start_time) * 1000, 2)
                    results["latency_ms"] = latency
                    results["status"] = "✅ Active"
                except:
                    results["status"] = "❌ Inactive"
                    results["latency_ms"] = None
                finally:
                    sock.close()
            
            # Get bandwidth statistics from logs
            stats = self.config_manager.get_tunnel_stats(tunnel_id, hours=1)
            if stats:
                total_in = sum(s["bytes_in"] for s in stats)
                total_out = sum(s["bytes_out"] for s in stats)
                results["bandwidth"] = {
                    "bytes_in": total_in,
                    "bytes_out": total_out,
                    "total": total_in + total_out
                }
            else:
                results["bandwidth"] = {
                    "bytes_in": 0,
                    "bytes_out": 0,
                    "total": 0
                }
            
            results["tunnel_type"] = tunnel_type.upper()
            
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    def start_monitoring(self):
        """Start tunnel monitoring thread"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitor_tunnels, daemon=True)
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop tunnel monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
    
    def _monitor_tunnels(self):
        """Monitor tunnel health and restart if needed"""
        while self.monitoring_active:
            try:
                # Check each active tunnel
                dead_tunnels = []
                
                for tunnel_id, tunnel_info in self.active_tunnels.items():
                    tunnel_type = tunnel_info.get("tunnel_type", "tcp")
                    
                    if tunnel_type == "tcp":
                        process = tunnel_info["process"]
                        
                        # Check if process is still alive
                        if process.poll() is not None:
                            dead_tunnels.append(tunnel_id)
                            continue
                        
                        # Check if port is still listening
                        if not self._is_port_in_use(tunnel_info["local_port"]):
                            dead_tunnels.append(tunnel_id)
                            continue
                    else:
                        # UDP tunnel monitoring
                        ssh_process = tunnel_info.get("ssh_process")
                        local_socat_process = tunnel_info.get("local_socat_process")
                        
                        ssh_alive = ssh_process and ssh_process.poll() is None
                        socat_alive = local_socat_process and local_socat_process.poll() is None
                        
                        if not (ssh_alive and socat_alive):
                            dead_tunnels.append(tunnel_id)
                            continue
                    
                    # Update bandwidth stats
                    self._update_bandwidth_stats(tunnel_id, tunnel_info)
                
                # Restart dead tunnels if auto_start is enabled
                for tunnel_id in dead_tunnels:
                    tunnel_config = self.config_manager.get_tunnel(tunnel_id)
                    if tunnel_config and tunnel_config.get("auto_start", True):
                        print(f"🔄 Restarting dead tunnel: {tunnel_id}")
                        
                        # Clean up dead tunnel
                        if tunnel_id in self.active_tunnels:
                            del self.active_tunnels[tunnel_id]
                        
                        # Log event
                        self.config_manager.log_event(
                            "tunnel_logs",
                            tunnel_id=tunnel_id,
                            event_type="reconnect",
                            message="Auto-restarting dead tunnel"
                        )
                        
                        # Restart tunnel
                        self.create_tunnel(tunnel_id)
                
                # Sleep before next check
                time.sleep(self.config_manager.config["settings"]["tunnel_check_interval"])
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(30)  # Wait longer on error
    
    def _test_remote_connectivity(self, host: str, port: int) -> Tuple[bool, str]:
        """Test if remote server is reachable"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return True, "✅ Remote server is reachable"
            else:
                return False, f"❌ Cannot reach {host}:{port}"
                
        except Exception as e:
            return False, f"❌ Connectivity test failed: {str(e)}"
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _wait_for_port(self, port: int, timeout: int = 10) -> bool:
        """Wait for port to become available"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_port_in_use(port):
                return True
            time.sleep(0.5)
        return False
    
    def _kill_process(self, process):
        """Kill a process and its children"""
        try:
            # Kill process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if not responding
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
        except:
            # Fallback to direct process kill
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
    
    def _update_bandwidth_stats(self, tunnel_id: str, tunnel_info: Dict):
        """Update bandwidth statistics for a tunnel"""
        try:
            # Get network stats (simplified - in real implementation, 
            # you'd monitor the specific network interface)
            
            # For now, just log a bandwidth entry every minute
            current_time = time.time()
            if not hasattr(tunnel_info, 'last_bandwidth_update'):
                tunnel_info['last_bandwidth_update'] = current_time
                return
            
            if current_time - tunnel_info['last_bandwidth_update'] >= 60:
                # Log bandwidth stats (placeholder values)
                self.config_manager.log_event(
                    "bandwidth_stats",
                    tunnel_id=tunnel_id,
                    bytes_in=tunnel_info.get("bytes_received", 0),
                    bytes_out=tunnel_info.get("bytes_sent", 0),
                    duration=60
                )
                tunnel_info['last_bandwidth_update'] = current_time
        except:
            pass
    
    def cleanup(self):
        """Cleanup all tunnels and stop monitoring"""
        self.stop_monitoring()
        
        # Kill all active tunnels
        for tunnel_id in list(self.active_tunnels.keys()):
            self.destroy_tunnel(tunnel_id)

# Example usage
if __name__ == "__main__":
    from config_manager import ConfigManager
    from ssh_manager import SSHManager
    
    config = ConfigManager()
    ssh_manager = SSHManager(config)
    tunnel_manager = TunnelManager(config, ssh_manager)
    
    print("✅ Enhanced Tunnel Manager initialized with UDP support")
    print(f"Active tunnels: {len(tunnel_manager.active_tunnels)}")