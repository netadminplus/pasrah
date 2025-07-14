#!/usr/bin/env python3
"""
PasRah - SSH Tunnel Manager
Tunnel Manager Module
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
        """Create an SSH tunnel"""
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
                        message=f"Tunnel created: {bind_address}:{tunnel['local_port']} -> {server['host']}:{tunnel['remote_port']}"
                    )
                    
                    return True, f"✅ Tunnel created successfully on port {tunnel['local_port']}"
                else:
                    # Port not listening, kill process
                    self._kill_process(process)
                    return False, f"❌ Tunnel failed to bind to port {tunnel['local_port']}"
            else:
                # Process died immediately
                stderr_output = process.stderr.read().decode() if process.stderr else ""
                return False, f"❌ Tunnel process failed: {stderr_output}"
                
        except Exception as e:
            return False, f"❌ Failed to create tunnel: {str(e)}"
    
    def destroy_tunnel(self, tunnel_id: str) -> Tuple[bool, str]:
        """Destroy an SSH tunnel"""
        if tunnel_id not in self.active_tunnels:
            return False, "❌ Tunnel is not active"
        
        try:
            tunnel_info = self.active_tunnels[tunnel_id]
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
                message="Tunnel destroyed by user"
            )
            
            return True, "✅ Tunnel destroyed successfully"
            
        except Exception as e:
            return False, f"❌ Failed to destroy tunnel: {str(e)}"
    
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
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('127.0.0.1', tunnel["local_port"]))
            sock.close()
            
            if result == 0:
                return True, "✅ Tunnel is responding"
            else:
                return False, "❌ Tunnel is not responding"
                
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
        
        try:
            # Test latency
            start_time = time.time()
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
                    process = tunnel_info["process"]
                    
                    # Check if process is still alive
                    if process.poll() is not None:
                        # Process died
                        dead_tunnels.append(tunnel_id)
                        continue
                    
                    # Check if port is still listening
                    if not self._is_port_in_use(tunnel_info["local_port"]):
                        # Port not listening, process might be stuck
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
    
    print("✅ Tunnel Manager initialized")
    print(f"Active tunnels: {len(tunnel_manager.active_tunnels)}")