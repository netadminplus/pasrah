#!/usr/bin/env python3
"""
PasRah - SSH Tunnel Manager
Enhanced Configuration Manager Module with UDP Support
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import hashlib
from cryptography.fernet import Fernet
import base64

class ConfigManager:
    def __init__(self, base_dir: str = "~/pasrah"):
        self.base_dir = Path(base_dir).expanduser()
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        self.config_file = self.data_dir / "config.json"
        self.db_file = self.data_dir / "pasrah.db"
        
        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Default configuration
        self.default_config = {
            "version": "1.0.0",
            "servers": {},
            "tunnels": {},
            "settings": {
                "theme": "dark",
                "language": "en",
                "auto_backup": True,
                "backup_interval": 24,  # hours
                "max_logs": 1000,
                "ssh_timeout": 30,
                "tunnel_check_interval": 60,  # seconds
                "web_port": 8080,
                "enable_bandwidth_monitoring": True,
                "support_udp_tunnels": True,  # NEW: UDP support flag
                "socat_path": "/usr/bin/socat"  # NEW: Path to socat binary
            },
            "ssh_keys": {
                "private_key_path": str(self.base_dir / ".ssh" / "id_ed25519_pasrah"),
                "public_key_path": str(self.base_dir / ".ssh" / "id_ed25519_pasrah.pub")
            }
        }
        
        # Load or create config
        self.config = self.load_config()
    
    def _init_database(self):
        """Initialize SQLite database for logs and monitoring"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tunnel_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tunnel_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,  -- connect, disconnect, error, data
                message TEXT,
                bytes_sent INTEGER DEFAULT 0,
                bytes_received INTEGER DEFAULT 0,
                tunnel_type TEXT DEFAULT 'tcp'  -- NEW: Track tunnel type
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,  -- connect, disconnect, error, health_check
                message TEXT,
                response_time REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bandwidth_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tunnel_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                bytes_in INTEGER DEFAULT 0,
                bytes_out INTEGER DEFAULT 0,
                duration INTEGER DEFAULT 60,  -- seconds
                tunnel_type TEXT DEFAULT 'tcp'  -- NEW: Track tunnel type
            )
        ''')
        
        # NEW: Table for tunnel process tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tunnel_processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tunnel_id TEXT NOT NULL UNIQUE,
                main_pid INTEGER,
                helper_pids TEXT,  -- JSON array of additional PIDs for UDP tunnels
                tunnel_type TEXT DEFAULT 'tcp',
                status TEXT DEFAULT 'unknown',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def load_config(self) -> Dict:
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Merge with defaults (for new settings)
                merged_config = self.default_config.copy()
                self._deep_merge(merged_config, config)
                return merged_config
            except Exception as e:
                print(f"Error loading config: {e}")
                return self.default_config.copy()
        else:
            return self.default_config.copy()
    
    def _deep_merge(self, base_dict: Dict, update_dict: Dict):
        """Recursively merge dictionaries"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def save_config(self) -> bool:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def add_server(self, server_id: str, server_data: Dict) -> bool:
        """Add a foreign server"""
        self.config["servers"][server_id] = {
            "id": server_id,
            "host": server_data["host"],
            "port": server_data.get("port", 22),
            "username": server_data["username"],
            "password_hash": self._hash_password(server_data.get("password", "")),
            "status": "unknown",
            "added_date": datetime.now().isoformat(),
            "last_check": None,
            "tunnels": [],
            "capabilities": {
                "socat_installed": False,  # NEW: Track if socat is available
                "udp_support": False       # NEW: Track UDP capability
            }
        }
        return self.save_config()
    
    def remove_server(self, server_id: str) -> bool:
        """Remove a foreign server"""
        if server_id in self.config["servers"]:
            del self.config["servers"][server_id]
            return self.save_config()
        return False
    
    def add_tunnel(self, tunnel_id: str, tunnel_data: Dict) -> bool:
        """Add a tunnel configuration with UDP support"""
        self.config["tunnels"][tunnel_id] = {
            "id": tunnel_id,
            "name": tunnel_data["name"],
            "server_id": tunnel_data["server_id"],
            "local_port": tunnel_data["local_port"],
            "remote_port": tunnel_data["remote_port"],
            "remote_host": tunnel_data.get("remote_host", "localhost"),
            "tunnel_type": tunnel_data.get("tunnel_type", "tcp").lower(),  # NEW: tcp or udp
            "status": "inactive",
            "created_date": datetime.now().isoformat(),
            "pid": None,
            "auto_start": tunnel_data.get("auto_start", True),
            "description": tunnel_data.get("description", ""),
            "process_info": {  # NEW: Enhanced process tracking
                "main_pid": None,
                "helper_pids": [],
                "intermediate_ports": []  # For UDP tunnels
            }
        }
        
        # Add tunnel to server's tunnel list
        if tunnel_data["server_id"] in self.config["servers"]:
            self.config["servers"][tunnel_data["server_id"]]["tunnels"].append(tunnel_id)
        
        return self.save_config()
    
    def remove_tunnel(self, tunnel_id: str) -> bool:
        """Remove a tunnel configuration"""
        if tunnel_id in self.config["tunnels"]:
            tunnel = self.config["tunnels"][tunnel_id]
            server_id = tunnel["server_id"]
            
            # Remove from server's tunnel list
            if server_id in self.config["servers"]:
                if tunnel_id in self.config["servers"][server_id]["tunnels"]:
                    self.config["servers"][server_id]["tunnels"].remove(tunnel_id)
            
            # Clean up process tracking
            self._remove_tunnel_process_info(tunnel_id)
            
            del self.config["tunnels"][tunnel_id]
            return self.save_config()
        return False
    
    def get_servers(self) -> Dict:
        """Get all servers"""
        return self.config["servers"]
    
    def get_tunnels(self) -> Dict:
        """Get all tunnels"""
        return self.config["tunnels"]
    
    def get_server(self, server_id: str) -> Optional[Dict]:
        """Get specific server"""
        return self.config["servers"].get(server_id)
    
    def get_tunnel(self, tunnel_id: str) -> Optional[Dict]:
        """Get specific tunnel"""
        return self.config["tunnels"].get(tunnel_id)
    
    def update_tunnel_status(self, tunnel_id: str, status: str, pid: Optional[int] = None):
        """Update tunnel status with enhanced process tracking"""
        if tunnel_id in self.config["tunnels"]:
            self.config["tunnels"][tunnel_id]["status"] = status
            if pid is not None:
                self.config["tunnels"][tunnel_id]["pid"] = pid
                self.config["tunnels"][tunnel_id]["process_info"]["main_pid"] = pid
            
            # Update process table
            self._update_tunnel_process_info(tunnel_id, status, pid)
            self.save_config()
    
    def update_server_status(self, server_id: str, status: str):
        """Update server status"""
        if server_id in self.config["servers"]:
            self.config["servers"][server_id]["status"] = status
            self.config["servers"][server_id]["last_check"] = datetime.now().isoformat()
            self.save_config()
    
    def update_server_capabilities(self, server_id: str, capabilities: Dict):
        """Update server capabilities (e.g., socat availability)"""
        if server_id in self.config["servers"]:
            self.config["servers"][server_id]["capabilities"].update(capabilities)
            self.save_config()
    
    def log_event(self, table: str, **kwargs):
        """Log an event to database with UDP support"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        if table == "tunnel_logs":
            cursor.execute('''
                INSERT INTO tunnel_logs (tunnel_id, event_type, message, bytes_sent, bytes_received, tunnel_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                kwargs.get("tunnel_id"),
                kwargs.get("event_type"),
                kwargs.get("message", ""),
                kwargs.get("bytes_sent", 0),
                kwargs.get("bytes_received", 0),
                kwargs.get("tunnel_type", "tcp")
            ))
        elif table == "server_logs":
            cursor.execute('''
                INSERT INTO server_logs (server_id, event_type, message, response_time)
                VALUES (?, ?, ?, ?)
            ''', (
                kwargs.get("server_id"),
                kwargs.get("event_type"),
                kwargs.get("message", ""),
                kwargs.get("response_time")
            ))
        elif table == "bandwidth_stats":
            cursor.execute('''
                INSERT INTO bandwidth_stats (tunnel_id, bytes_in, bytes_out, duration, tunnel_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                kwargs.get("tunnel_id"),
                kwargs.get("bytes_in", 0),
                kwargs.get("bytes_out", 0),
                kwargs.get("duration", 60),
                kwargs.get("tunnel_type", "tcp")
            ))
        
        conn.commit()
        conn.close()
    
    def _update_tunnel_process_info(self, tunnel_id: str, status: str, pid: Optional[int]):
        """Update tunnel process information in database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        tunnel = self.get_tunnel(tunnel_id)
        if not tunnel:
            conn.close()
            return
        
        tunnel_type = tunnel.get("tunnel_type", "tcp")
        helper_pids = json.dumps(tunnel.get("process_info", {}).get("helper_pids", []))
        
        cursor.execute('''
            INSERT OR REPLACE INTO tunnel_processes 
            (tunnel_id, main_pid, helper_pids, tunnel_type, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (tunnel_id, pid, helper_pids, tunnel_type, status, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def _remove_tunnel_process_info(self, tunnel_id: str):
        """Remove tunnel process information from database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM tunnel_processes WHERE tunnel_id = ?', (tunnel_id,))
        
        conn.commit()
        conn.close()
    
    def get_tunnel_stats(self, tunnel_id: str, hours: int = 24) -> List[Dict]:
        """Get tunnel bandwidth statistics"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, bytes_in, bytes_out, duration, tunnel_type
            FROM bandwidth_stats
            WHERE tunnel_id = ? AND timestamp >= datetime('now', '-{} hours')
            ORDER BY timestamp DESC
        '''.format(hours), (tunnel_id,))
        
        stats = []
        for row in cursor.fetchall():
            stats.append({
                "timestamp": row[0],
                "bytes_in": row[1],
                "bytes_out": row[2],
                "duration": row[3],
                "tunnel_type": row[4]
            })
        
        conn.close()
        return stats
    
    def get_active_processes(self) -> List[Dict]:
        """Get all active tunnel processes"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT tunnel_id, main_pid, helper_pids, tunnel_type, status, updated_at
            FROM tunnel_processes
            WHERE status = 'active'
        ''')
        
        processes = []
        for row in cursor.fetchall():
            processes.append({
                "tunnel_id": row[0],
                "main_pid": row[1],
                "helper_pids": json.loads(row[2]) if row[2] else [],
                "tunnel_type": row[3],
                "status": row[4],
                "updated_at": row[5]
            })
        
        conn.close()
        return processes
    
    def export_config(self, export_path: str, password: Optional[str] = None) -> bool:
        """Export configuration to file"""
        try:
            export_data = {
                "pasrah_version": self.config["version"],
                "export_date": datetime.now().isoformat(),
                "config": self.config,
                "features": {
                    "udp_support": True,
                    "enhanced_monitoring": True
                }
            }
            
            data_json = json.dumps(export_data, indent=2)
            
            if password:
                # Encrypt with password
                key = self._derive_key(password)
                fernet = Fernet(key)
                encrypted_data = fernet.encrypt(data_json.encode())
                
                with open(export_path, 'wb') as f:
                    f.write(encrypted_data)
            else:
                with open(export_path, 'w') as f:
                    f.write(data_json)
            
            return True
        except Exception as e:
            print(f"Export failed: {e}")
            return False
    
    def import_config(self, import_path: str, password: Optional[str] = None) -> bool:
        """Import configuration from file"""
        try:
            if password:
                # Decrypt with password
                key = self._derive_key(password)
                fernet = Fernet(key)
                
                with open(import_path, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = fernet.decrypt(encrypted_data)
                data_json = decrypted_data.decode()
            else:
                with open(import_path, 'r') as f:
                    data_json = f.read()
            
            import_data = json.loads(data_json)
            
            # Backup current config
            backup_path = self.data_dir / f"config_backup_{int(datetime.now().timestamp())}.json"
            self.export_config(str(backup_path))
            
            # Import new config
            self.config = import_data["config"]
            
            # Ensure compatibility with new features
            self._upgrade_config_format()
            
            return self.save_config()
            
        except Exception as e:
            print(f"Import failed: {e}")
            return False
    
    def _upgrade_config_format(self):
        """Upgrade old config format to support new features"""
        # Add UDP support fields to existing tunnels
        for tunnel_id, tunnel in self.config["tunnels"].items():
            if "tunnel_type" not in tunnel:
                tunnel["tunnel_type"] = "tcp"
            if "process_info" not in tunnel:
                tunnel["process_info"] = {
                    "main_pid": tunnel.get("pid"),
                    "helper_pids": [],
                    "intermediate_ports": []
                }
        
        # Add capabilities to existing servers
        for server_id, server in self.config["servers"].items():
            if "capabilities" not in server:
                server["capabilities"] = {
                    "socat_installed": False,
                    "udp_support": False
                }
        
        # Update settings
        if "support_udp_tunnels" not in self.config["settings"]:
            self.config["settings"]["support_udp_tunnels"] = True
        if "socat_path" not in self.config["settings"]:
            self.config["settings"]["socat_path"] = "/usr/bin/socat"
    
    def _hash_password(self, password: str) -> str:
        """Hash password for storage"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password"""
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), b'pasrah_salt', 100000)
        return base64.urlsafe_b64encode(key)

# Example usage
if __name__ == "__main__":
    config = ConfigManager()
    
    # Add a server
    config.add_server("server1", {
        "host": "46.8.233.208",
        "port": 22,
        "username": "root",
        "password": "mypassword"
    })
    
    # Add a UDP tunnel
    config.add_tunnel("udp_tunnel1", {
        "name": "Gaming Tunnel",
        "server_id": "server1",
        "local_port": 7777,
        "remote_port": 7777,
        "tunnel_type": "udp",
        "description": "UDP tunnel for gaming"
    })
    
    print("Enhanced Configuration manager initialized!")
    print(f"Servers: {len(config.get_servers())}")
    print(f"Tunnels: {len(config.get_tunnels())}")
    print(f"UDP Support: {config.config['settings']['support_udp_tunnels']}")