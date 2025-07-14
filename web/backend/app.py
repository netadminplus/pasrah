#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os
import requests
import tempfile
import json
import psutil
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigManager
from core.ssh_manager import SSHManager
from core.tunnel_manager import TunnelManager
from core.web_auth import WebAuthManager

class ServerCreate(BaseModel):
    host: str
    port: int = 22
    username: str
    password: str
    update_system: bool = False
    install_fail2ban: bool = False
    create_user: bool = False
    ssh_hardening: bool = False

class TunnelCreate(BaseModel):
    name: str
    server_id: str
    local_port: int
    remote_port: int
    remote_host: str = "localhost"
    tunnel_type: str = "tcp"  # tcp or udp
    description: str = ""
    auto_start: bool = True

class LoginRequest(BaseModel):
    username: str
    password: str

app = FastAPI(title="PasRah Web Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

config_manager = ConfigManager()
ssh_manager = SSHManager(config_manager)
tunnel_manager = TunnelManager(config_manager, ssh_manager)
web_auth = WebAuthManager(config_manager)

def get_country_flag(ip):
    try:
        if ip.startswith(('192.168.', '10.', '172.')) or ip == '127.0.0.1' or ip == 'localhost':
            return '🖥️'
        if ip.startswith('167.172.'):
            return '🇩🇪'
        elif ip.startswith('37.32.'):
            return '🇮🇷'
        elif ip.startswith('185.'):
            return '🇪🇺'
        return '🌍'
    except:
        return '🌍'

def get_local_ip():
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return 'Unknown'

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user = web_auth.verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user

@app.get("/")
async def root():
    local_ip = get_local_ip()
    local_flag = get_country_flag(local_ip)
    
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <title>PasRah - SSH Tunnel Manager</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <script src="https://unpkg.com/chart.js"></script>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            background: linear-gradient(135deg, #1e3c72, #2a5298); 
            color: white; 
            margin: 0; 
            padding: 20px; 
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .top-bar {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .section {{ 
            background: rgba(255,255,255,0.1); 
            padding: 20px; 
            margin: 20px 0; 
            border-radius: 15px; 
        }}
        .btn {{ 
            background: linear-gradient(45deg, #667eea, #764ba2); 
            color: white; 
            border: none; 
            padding: 10px 20px; 
            border-radius: 25px; 
            cursor: pointer; 
            margin: 5px; 
        }}
        .btn-success {{ background: linear-gradient(45deg, #28a745, #20c997); }}
        .btn-danger {{ background: linear-gradient(45deg, #dc3545, #fd7e14); }}
        .btn-info {{ background: linear-gradient(45deg, #17a2b8, #6610f2); }}
        .btn-warning {{ background: linear-gradient(45deg, #ffc107, #fd7e14); }}
        .btn-small {{ padding: 5px 10px; font-size: 12px; }}
        .table {{ width: 100%; border-collapse: collapse; }}
        .table th, .table td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }}
        .login-box {{ 
            max-width: 400px; 
            margin: 100px auto; 
            background: rgba(255,255,255,0.1); 
            padding: 30px; 
            border-radius: 10px; 
        }}
        .form-group {{ margin-bottom: 15px; }}
        .form-group input, .form-group select {{ 
            width: 100%; 
            padding: 8px; 
            border: 1px solid #ddd; 
            border-radius: 4px; 
            color: #333;
        }}
        .form-group label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
        .modal {{ 
            display: none; 
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            background: rgba(0,0,0,0.5); 
            z-index: 1000;
        }}
        .modal-content {{ 
            background: rgba(30,60,114,0.95); 
            margin: 5% auto; 
            padding: 20px; 
            width: 500px; 
            border-radius: 10px; 
            color: white;
            max-height: 80vh;
            overflow-y: auto;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.15);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-number {{ font-size: 2em; font-weight: bold; }}
        .help-note {{
            background: rgba(255,255,255,0.1);
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
            font-size: 14px;
        }}
        .tunnel-type-badge {{
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .tcp-badge {{ background: #007bff; }}
        .udp-badge {{ background: #28a745; }}
        .status-badge {{
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }}
        .status-active {{ background: #28a745; }}
        .status-inactive {{ background: #6c757d; }}
        .status-error {{ background: #dc3545; }}
        .radio-group {{
            display: flex;
            gap: 15px;
            margin: 10px 0;
        }}
        .radio-item {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .error-message {{
            color: #ff6b6b;
            background: rgba(255,107,107,0.1);
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .success-message {{
            color: #51cf66;
            background: rgba(81,207,102,0.1);
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div id="app">
        <div v-if="!isAuthenticated" class="login-box">
            <h2>🚇 PasRah Login</h2>
            <form @submit.prevent="login">
                <div class="form-group">
                    <input type="text" v-model="loginForm.username" placeholder="Username" required>
                </div>
                <div class="form-group">
                    <input type="password" v-model="loginForm.password" placeholder="Password" required>
                </div>
                <button type="submit" class="btn" style="width: 100%;">Login</button>
                <div v-if="loginError" class="error-message">{{{{ loginError }}}}</div>
            </form>
            <div class="help-note">
                <strong>💡 Forgot credentials?</strong><br>
                SSH to server and run: <code>python3 ~/pasrah/cli/enhanced_cli.py</code><br>
                Then use option [9] to change password
            </div>
        </div>

        <div v-if="isAuthenticated" class="container">
            <div class="top-bar">
                <div>
                    <span style="font-size: 18px;">{local_flag}</span>
                    <span style="font-weight: bold; margin-left: 10px;">Local Server: {local_ip}</span>
                </div>
                <button @click="logout" class="btn btn-danger">Logout</button>
            </div>

            <div class="section">
                <h1>🚇 PasRah - SSH Tunnel Manager v1.0</h1>
                <p>Making Connections Possible Worldwide | TCP & UDP Support</p>
            </div>

            <div class="section">
                <h2>📊 Dashboard Overview</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">{{{{ stats.servers }}}}</div>
                        <div>Remote Servers</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{{{{ stats.tunnels }}}}</div>
                        <div>Total Tunnels</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{{{{ stats.active_tunnels }}}}</div>
                        <div>Active Tunnels</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{{{{ formatBytes(stats.total_bandwidth || 0) }}}}</div>
                        <div>Total Bandwidth</div>
                    </div>
                </div>
                <button @click="showAddServer" class="btn">➕ Add Server</button>
                <button @click="showAddTunnel" class="btn btn-success">🚇 Add Tunnel</button>
                <button @click="showBandwidthMonitor" class="btn btn-info">📊 Monitor</button>
                <button @click="showBackupRestore" class="btn btn-warning">💾 Backup</button>
                <button @click="refreshData" class="btn">🔄 Refresh</button>
            </div>

            <div class="section">
                <h2>🌐 Remote Servers</h2>
                <table class="table">
                    <thead>
                        <tr><th>#</th><th>Server ID</th><th>Host:Port</th><th>Status</th><th>Tunnels</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                        <tr v-for="(server, index) in servers" :key="server.id">
                            <td>{{{{ index + 1 }}}}</td>
                            <td>{{{{ server.id }}}}</td>
                            <td>{{{{ getCountryFlag(server.host) }}}} {{{{ server.host }}}}:{{{{ server.port }}}}</td>
                            <td><span :class="'status-badge status-' + (server.status || 'active')">{{{{ server.status || 'active' }}}}</span></td>
                            <td>{{{{ getServerTunnelCount(server.id) }}}}</td>
                            <td><button @click="deleteServer(server.id)" class="btn btn-danger btn-small">Delete</button></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>🚇 SSH Tunnels (TCP/UDP)</h2>
                <table class="table">
                    <thead>
                        <tr><th>#</th><th>Name</th><th>Type</th><th>Local Port</th><th>Remote</th><th>Status</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                        <tr v-for="(tunnel, index) in tunnels" :key="tunnel.id">
                            <td>{{{{ index + 1 }}}}</td>
                            <td>{{{{ tunnel.name }}}}</td>
                            <td><span :class="'tunnel-type-badge ' + (tunnel.tunnel_type || 'tcp') + '-badge'">{{{{ (tunnel.tunnel_type || 'tcp').toUpperCase() }}}}</span></td>
                            <td>{{{{ tunnel.local_port }}}}</td>
                            <td>{{{{ getServerHost(tunnel.server_id) }}}}:{{{{ tunnel.remote_port }}}}</td>
                            <td><span :class="'status-badge status-' + tunnel.status">{{{{ tunnel.status }}}}</span></td>
                            <td>
                                <button @click="toggleTunnel(tunnel.id)" :class="tunnel.status === 'active' ? 'btn btn-warning btn-small' : 'btn btn-success btn-small'">
                                    {{{{ tunnel.status === 'active' ? 'Stop' : 'Start' }}}}
                                </button>
                                <button @click="testTunnel(tunnel.id)" class="btn btn-info btn-small">Test</button>
                                <button @click="deleteTunnel(tunnel.id)" class="btn btn-danger btn-small">Delete</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>📖 Quick Usage Guide</h2>
                <div class="help-note">
                    <h4>🎯 How to Use PasRah Tunnels:</h4>
                    <strong>TCP Tunnels:</strong> Perfect for HTTP, HTTPS, SSH, databases<br>
                    <strong>UDP Tunnels:</strong> Ideal for VPN, gaming, DNS, video streaming<br><br>
                    
                    <strong>📱 For Users:</strong><br>
                    • Set proxy to: <code>YOUR-SERVER-IP:LOCAL-PORT</code><br>
                    • Example: <code>{local_ip}:4444</code> (if you created a tunnel on port 4444)<br><br>
                    
                    <strong>🎮 Gaming/VPN:</strong><br>
                    • Use UDP tunnels for better performance<br>
                    • Point your game/VPN client to the local port<br><br>
                    
                    <strong>🌐 Web Browsing:</strong><br>
                    • Use TCP tunnels with SOCKS proxy settings<br>
                    • Configure browser proxy: SOCKS5 → Your-IP:Port
                </div>
            </div>
        </div>

        <!-- Add Server Modal -->
        <div id="serverModal" class="modal">
            <div class="modal-content">
                <h3>➕ Add Remote Server</h3>
                <form @submit.prevent="addServer">
                    <div class="form-group">
                        <label>Host/IP Address:</label>
                        <input type="text" v-model="serverForm.host" placeholder="46.8.233.208" required>
                    </div>
                    <div class="form-group">
                        <label>SSH Port:</label>
                        <input type="number" v-model="serverForm.port" placeholder="22" required>
                    </div>
                    <div class="form-group">
                        <label>Username:</label>
                        <input type="text" v-model="serverForm.username" placeholder="root" required>
                    </div>
                    <div class="form-group">
                        <label>Password:</label>
                        <input type="password" v-model="serverForm.password" placeholder="Password" required>
                    </div>
                    
                    <h4>🔧 Server Setup Options:</h4>
                    <div class="form-group">
                        <label><input type="checkbox" v-model="serverForm.update_system"> Update system packages</label>
                    </div>
                    <div class="form-group">
                        <label><input type="checkbox" v-model="serverForm.install_fail2ban"> Install fail2ban security</label>
                    </div>
                    <div class="form-group">
                        <label><input type="checkbox" v-model="serverForm.ssh_hardening"> Apply SSH hardening</label>
                    </div>
                    
                    <button type="submit" class="btn btn-success">Add Server</button>
                    <button type="button" @click="closeModal" class="btn btn-danger">Cancel</button>
                    <div v-if="serverResult" :class="serverResult.includes('success') ? 'success-message' : 'error-message'">{{{{ serverResult }}}}</div>
                </form>
            </div>
        </div>

        <!-- Add Tunnel Modal -->
        <div id="tunnelModal" class="modal">
            <div class="modal-content">
                <h3>🚇 Create New Tunnel</h3>
                <form @submit.prevent="addTunnel">
                    <div class="form-group">
                        <label>Tunnel Name:</label>
                        <input type="text" v-model="tunnelForm.name" placeholder="My Tunnel" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Tunnel Type:</label>
                        <div class="radio-group">
                            <div class="radio-item">
                                <input type="radio" v-model="tunnelForm.tunnel_type" value="tcp" id="tcp-radio">
                                <label for="tcp-radio">TCP (Web, SSH, Database)</label>
                            </div>
                            <div class="radio-item">
                                <input type="radio" v-model="tunnelForm.tunnel_type" value="udp" id="udp-radio">
                                <label for="udp-radio">UDP (Gaming, VPN, DNS)</label>
                            </div>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Remote Server:</label>
                        <select v-model="tunnelForm.server_id" required>
                            <option value="">Select Server</option>
                            <option v-for="server in servers" :key="server.id" :value="server.id">{{{{ server.host }}}} ({{{{ server.id }}}})</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>Local Port (Your Server):</label>
                        <input type="number" v-model="tunnelForm.local_port" placeholder="4444" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Remote Port (Target):</label>
                        <input type="number" v-model="tunnelForm.remote_port" placeholder="443" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Remote Host:</label>
                        <input type="text" v-model="tunnelForm.remote_host" placeholder="localhost">
                    </div>
                    
                    <div class="form-group">
                        <label>Description (Optional):</label>
                        <input type="text" v-model="tunnelForm.description" placeholder="What this tunnel is for">
                    </div>
                    
                    <div class="form-group">
                        <label><input type="checkbox" v-model="tunnelForm.auto_start"> Auto-start tunnel</label>
                    </div>
                    
                    <button type="submit" class="btn btn-success">Create Tunnel</button>
                    <button type="button" @click="closeModal" class="btn btn-danger">Cancel</button>
                    <div v-if="tunnelResult" :class="tunnelResult.includes('success') ? 'success-message' : 'error-message'">{{{{ tunnelResult }}}}</div>
                </form>
            </div>
        </div>

        <!-- Bandwidth Monitor Modal -->
        <div id="bandwidthModal" class="modal">
            <div class="modal-content" style="width: 800px;">
                <h3>📊 Bandwidth Monitor</h3>
                <div style="height: 400px; background: #f0f0f0; border-radius: 10px; margin: 20px 0;">
                    <canvas id="bandwidthChart"></canvas>
                </div>
                <button @click="closeModal" class="btn btn-danger">Close</button>
            </div>
        </div>

        <!-- Backup & Restore Modal -->
        <div id="backupModal" class="modal">
            <div class="modal-content">
                <h3>💾 Backup & Restore</h3>
                <div style="margin: 20px 0;">
                    <h4>Create Backup</h4>
                    <p>Download your complete PasRah configuration</p>
                    <button @click="createBackup" class="btn btn-success">📥 Create & Download Backup</button>
                    <div v-if="backupResult" :class="backupResult.includes('success') || backupResult.includes('downloaded') ? 'success-message' : 'error-message'">{{{{ backupResult }}}}</div>
                </div>
                <div style="margin: 20px 0;">
                    <h4>Restore Backup</h4>
                    <p>Upload and restore a previous backup</p>
                    <input type="file" @change="selectBackupFile" accept=".tar.gz,.json">
                    <button @click="restoreBackup" class="btn btn-warning" :disabled="!selectedFile">📤 Restore Backup</button>
                    <div v-if="restoreResult" :class="restoreResult.includes('success') || restoreResult.includes('completed') ? 'success-message' : 'error-message'">{{{{ restoreResult }}}}</div>
                </div>
                <button @click="closeModal" class="btn btn-danger">Close</button>
            </div>
        </div>
    </div>

    <script>
        const {{ createApp }} = Vue;
        createApp({{
            data() {{ return {{
                isAuthenticated: false,
                token: null,
                loginForm: {{ username: '', password: '' }},
                loginError: '',
                stats: {{ servers: 0, tunnels: 0, active_tunnels: 0, total_bandwidth: 0 }},
                servers: [],
                tunnels: [],
                serverForm: {{ 
                    host: '', 
                    port: 22, 
                    username: '', 
                    password: '',
                    update_system: false,
                    install_fail2ban: false,
                    ssh_hardening: false
                }},
                tunnelForm: {{ 
                    name: '', 
                    server_id: '', 
                    local_port: '', 
                    remote_port: '', 
                    remote_host: 'localhost',
                    tunnel_type: 'tcp',
                    description: '',
                    auto_start: true
                }},
                serverResult: '',
                tunnelResult: '',
                backupResult: '',
                restoreResult: '',
                selectedFile: null
            }}}},
            methods: {{
                formatBytes(bytes) {{
                    if (bytes === 0) return '0 B';
                    const k = 1024;
                    const sizes = ['B', 'KB', 'MB', 'GB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
                }},
                getCountryFlag(ip) {{
                    if (ip.startsWith('37.32.')) return '🇮🇷';
                    if (ip.startsWith('167.172.')) return '🇩🇪';
                    if (ip.startsWith('185.')) return '🇪🇺';
                    return '🌍';
                }},
                getServerHost(serverId) {{
                    const server = this.servers.find(s => s.id === serverId);
                    return server ? server.host : 'Unknown';
                }},
                getServerTunnelCount(serverId) {{
                    return this.tunnels.filter(t => t.server_id === serverId).length;
                }},
                async login() {{
                    try {{
                        const response = await axios.post('/api/login', this.loginForm);
                        this.token = response.data.token;
                        this.isAuthenticated = true;
                        this.loginError = '';
                        await this.loadData();
                    }} catch (error) {{
                        this.loginError = 'Login failed - check your credentials';
                    }}
                }},
                logout() {{ 
                    this.isAuthenticated = false; 
                    this.token = null; 
                    this.loginError = '';
                }},
                async loadData() {{
                    const headers = {{ Authorization: `Bearer ${{this.token}}` }};
                    try {{
                        const [stats, servers, tunnels] = await Promise.all([
                            axios.get('/api/stats', {{ headers }}),
                            axios.get('/api/servers', {{ headers }}),
                            axios.get('/api/tunnels', {{ headers }})
                        ]);
                        this.stats = stats.data;
                        this.servers = Object.values(servers.data);
                        this.tunnels = Object.values(tunnels.data);
                    }} catch (error) {{ 
                        console.error('Failed to load data:', error);
                        if (error.response?.status === 401) {{
                            this.logout();
                        }}
                    }}
                }},
                showAddServer() {{ 
                    this.serverResult = '';
                    document.getElementById('serverModal').style.display = 'block'; 
                }},
                showAddTunnel() {{ 
                    this.tunnelResult = '';
                    document.getElementById('tunnelModal').style.display = 'block'; 
                }},
                showBandwidthMonitor() {{ document.getElementById('bandwidthModal').style.display = 'block'; }},
                showBackupRestore() {{ 
                    this.backupResult = '';
                    this.restoreResult = '';
                    document.getElementById('backupModal').style.display = 'block'; 
                }},
                closeModal() {{ 
                    document.getElementById('serverModal').style.display = 'none';
                    document.getElementById('tunnelModal').style.display = 'none';
                    document.getElementById('bandwidthModal').style.display = 'none';
                    document.getElementById('backupModal').style.display = 'none';
                }},
                async addServer() {{
                    this.serverResult = 'Testing connection...';
                    try {{
                        const response = await axios.post('/api/servers', this.serverForm, {{ 
                            headers: {{ Authorization: `Bearer ${{this.token}}` }} 
                        }});
                        this.serverResult = 'Server added successfully!';
                        await this.loadData();
                        setTimeout(() => this.closeModal(), 2000);
                    }} catch (error) {{ 
                        this.serverResult = error.response?.data?.detail || 'Failed to add server';
                    }}
                }},
                async addTunnel() {{
                    this.tunnelResult = 'Creating tunnel...';
                    try {{
                        const response = await axios.post('/api/tunnels', this.tunnelForm, {{ 
                            headers: {{ Authorization: `Bearer ${{this.token}}` }} 
                        }});
                        this.tunnelResult = 'Tunnel created successfully!';
                        await this.loadData();
                        setTimeout(() => this.closeModal(), 2000);
                    }} catch (error) {{ 
                        this.tunnelResult = error.response?.data?.detail || 'Failed to create tunnel';
                    }}
                }},
                async toggleTunnel(id) {{
                    try {{
                        await axios.post(`/api/tunnels/${{id}}/toggle`, {{}}, {{ 
                            headers: {{ Authorization: `Bearer ${{this.token}}` }} 
                        }});
                        await this.loadData();
                    }} catch (error) {{ 
                        alert('Failed to toggle tunnel: ' + (error.response?.data?.detail || 'Unknown error'));
                    }}
                }},
                async testTunnel(id) {{
                    try {{
                        const response = await axios.post(`/api/tunnels/${{id}}/test`, {{}}, {{ 
                            headers: {{ Authorization: `Bearer ${{this.token}}` }} 
                        }});
                        alert(response.data.message || 'Test completed');
                    }} catch (error) {{ 
                        alert('Test failed: ' + (error.response?.data?.detail || 'Unknown error'));
                    }}
                }},
                async deleteServer(id) {{
                    if (confirm('Delete this server? This will also delete all its tunnels.')) {{
                        try {{
                            await axios.delete(`/api/servers/${{id}}`, {{ 
                                headers: {{ Authorization: `Bearer ${{this.token}}` }} 
                            }});
                            await this.loadData();
                        }} catch (error) {{
                            alert('Failed to delete server');
                        }}
                    }}
                }},
                async deleteTunnel(id) {{
                    if (confirm('Delete this tunnel?')) {{
                        try {{
                            await axios.delete(`/api/tunnels/${{id}}`, {{ 
                                headers: {{ Authorization: `Bearer ${{this.token}}` }} 
                            }});
                            await this.loadData();
                        }} catch (error) {{
                            alert('Failed to delete tunnel');
                        }}
                    }}
                }},
                async createBackup() {{
                    this.backupResult = 'Creating backup...';
                    try {{
                        const response = await axios.post('/api/backup/create', {{}}, {{ 
                            headers: {{ Authorization: `Bearer ${{this.token}}` }}, 
                            responseType: 'blob' 
                        }});
                        
                        const url = window.URL.createObjectURL(new Blob([response.data]));
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = `pasrah_backup_${{new Date().toISOString().slice(0,10)}}.tar.gz`;
                        link.click();
                        window.URL.revokeObjectURL(url);
                        
                        this.backupResult = 'Backup downloaded successfully!';
                    }} catch (error) {{ 
                        this.backupResult = 'Backup failed: ' + (error.response?.data?.detail || 'Unknown error');
                    }}
                }},
                selectBackupFile(event) {{ 
                    this.selectedFile = event.target.files[0]; 
                    this.restoreResult = this.selectedFile ? `Selected: ${{this.selectedFile.name}}` : '';
                }},
                async restoreBackup() {{
                    if (!this.selectedFile) {{
                        this.restoreResult = 'Please select a backup file first';
                        return;
                    }}
                    
                    this.restoreResult = 'Restoring backup...';
                    try {{
                        const formData = new FormData();
                        formData.append('backup_file', this.selectedFile);
                        
                        await axios.post('/api/backup/restore', formData, {{ 
                            headers: {{ 
                                'Authorization': `Bearer ${{this.token}}`,
                                'Content-Type': 'multipart/form-data'
                            }} 
                        }});
                        
                        this.restoreResult = 'Backup restored successfully!';
                        await this.loadData();
                    }} catch (error) {{ 
                        this.restoreResult = 'Restore failed: ' + (error.response?.data?.detail || 'Unknown error');
                    }}
                }},
                async refreshData() {{ 
                    await this.loadData(); 
                }}
            }},
            mounted() {{
                // Check if user is already logged in (optional token persistence)
                const savedToken = localStorage.getItem('pasrah_token');
                if (savedToken) {{
                    this.token = savedToken;
                    this.isAuthenticated = true;
                    this.loadData().catch(() => {{
                        localStorage.removeItem('pasrah_token');
                        this.logout();
                    }});
                }}
            }},
            watch: {{
                token(newToken) {{
                    if (newToken) {{
                        localStorage.setItem('pasrah_token', newToken);
                    }} else {{
                        localStorage.removeItem('pasrah_token');
                    }}
                }}
            }}
        }}).mount('#app');
    </script>
</body>
</html>
    """)

@app.post("/api/login")
async def login(request: LoginRequest):
    token = web_auth.authenticate(request.username, request.password)
    if token:
        return {"token": token}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    servers = config_manager.get_servers()
    tunnels = config_manager.get_tunnels()
    active_tunnels = len(tunnel_manager.active_tunnels)
    return {
        "servers": len(servers), 
        "tunnels": len(tunnels), 
        "active_tunnels": active_tunnels, 
        "total_bandwidth": 1024*1024
    }

@app.get("/api/servers")
async def get_servers(user: dict = Depends(get_current_user)):
    servers = config_manager.get_servers()
    for server_id, server in servers.items():
        server["id"] = server_id
    return servers

@app.post("/api/servers")
async def add_server(server: ServerCreate, user: dict = Depends(get_current_user)):
    try:
        # Test connection first
        success, message = ssh_manager.test_connection(
            server.host, server.port, server.username, server.password
        )
        if not success:
            raise HTTPException(status_code=400, detail=f"Connection test failed: {message}")
        
        # Setup server
        server_id = f"{server.host}_{server.port}"
        config_manager.add_server(server_id, {
            "host": server.host, 
            "port": server.port, 
            "username": server.username, 
            "password": server.password
        })
        
        # Configure server with options
        options = {
            "update_system": server.update_system,
            "install_fail2ban": server.install_fail2ban,
            "create_user": server.create_user,
            "ssh_hardening": server.ssh_hardening
        }
        
        setup_success, setup_message = ssh_manager.setup_server(
            server_id, server.host, server.port, server.username, server.password, options
        )
        
        if setup_success:
            return {"message": f"Server added and configured successfully! {setup_message}"}
        else:
            return {"message": f"Server added but setup had issues: {setup_message}"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tunnels")
async def get_tunnels(user: dict = Depends(get_current_user)):
    tunnels = config_manager.get_tunnels()
    for tunnel_id, tunnel in tunnels.items():
        status = tunnel_manager.get_tunnel_status(tunnel_id)
        tunnel["status"] = status["status"]
        tunnel["id"] = tunnel_id
        # Ensure tunnel_type is set (default to tcp for backwards compatibility)
        if "tunnel_type" not in tunnel:
            tunnel["tunnel_type"] = "tcp"
    return tunnels

@app.post("/api/tunnels")
async def add_tunnel(tunnel: TunnelCreate, user: dict = Depends(get_current_user)):
    try:
        tunnel_id = f"{tunnel.name}_{tunnel.local_port}".replace(" ", "_").lower()
        
        # Add tunnel configuration
        config_manager.add_tunnel(tunnel_id, {
            "name": tunnel.name,
            "server_id": tunnel.server_id,
            "local_port": tunnel.local_port,
            "remote_port": tunnel.remote_port,
            "remote_host": tunnel.remote_host,
            "tunnel_type": tunnel.tunnel_type,
            "description": tunnel.description,
            "auto_start": tunnel.auto_start
        })
        
        # Start tunnel if auto_start is enabled
        if tunnel.auto_start:
            success, message = tunnel_manager.create_tunnel(tunnel_id)
            if success:
                return {"message": f"Tunnel created and started successfully! {message}"}
            else:
                return {"message": f"Tunnel created but failed to start: {message}"}
        else:
            return {"message": "Tunnel created successfully! Use the Start button to activate it."}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tunnels/{tunnel_id}/toggle")
async def toggle_tunnel(tunnel_id: str, user: dict = Depends(get_current_user)):
    try:
        status = tunnel_manager.get_tunnel_status(tunnel_id)
        if status["status"] == "active":
            success, message = tunnel_manager.destroy_tunnel(tunnel_id)
        else:
            success, message = tunnel_manager.create_tunnel(tunnel_id)
        
        if success:
            return {"message": message}
        else:
            raise HTTPException(status_code=500, detail=message)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tunnels/{tunnel_id}/test")
async def test_tunnel(tunnel_id: str, user: dict = Depends(get_current_user)):
    try:
        success, message = tunnel_manager.test_tunnel_connectivity(tunnel_id)
        return {"success": success, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tunnels/{tunnel_id}")
async def delete_tunnel(tunnel_id: str, user: dict = Depends(get_current_user)):
    try:
        # Stop tunnel if running
        if tunnel_id in tunnel_manager.active_tunnels:
            tunnel_manager.destroy_tunnel(tunnel_id)
        
        # Remove from config
        config_manager.remove_tunnel(tunnel_id)
        return {"message": "Tunnel deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/servers/{server_id}")
async def delete_server(server_id: str, user: dict = Depends(get_current_user)):
    try:
        # Stop all tunnels for this server
        tunnels = config_manager.get_tunnels()
        for tunnel_id, tunnel in tunnels.items():
            if tunnel["server_id"] == server_id:
                if tunnel_id in tunnel_manager.active_tunnels:
                    tunnel_manager.destroy_tunnel(tunnel_id)
                config_manager.remove_tunnel(tunnel_id)
        
        # Remove server
        config_manager.remove_server(server_id)
        return {"message": "Server and all its tunnels deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backup/create")
async def create_backup_endpoint(user: dict = Depends(get_current_user)):
    try:
        # Create backup data
        backup_data = {
            "backup_date": datetime.now().isoformat(),
            "pasrah_version": "1.0.0",
            "servers": config_manager.get_servers(),
            "tunnels": config_manager.get_tunnels(),
            "settings": config_manager.config.get("settings", {})
        }
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        temp_file.write(json.dumps(backup_data, indent=2).encode())
        temp_file.close()
        
        return FileResponse(
            temp_file.name, 
            media_type='application/json', 
            filename=f'pasrah_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backup/restore")
async def restore_backup_endpoint(backup_file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    try:
        # Read backup file
        content = await backup_file.read()
        backup_data = json.loads(content.decode())
        
        # Validate backup format
        if "servers" not in backup_data or "tunnels" not in backup_data:
            raise HTTPException(status_code=400, detail="Invalid backup file format")
        
        # Stop all current tunnels
        for tunnel_id in list(tunnel_manager.active_tunnels.keys()):
            tunnel_manager.destroy_tunnel(tunnel_id)
        
        # Restore servers
        for server_id, server_data in backup_data["servers"].items():
            config_manager.add_server(server_id, server_data)
        
        # Restore tunnels
        for tunnel_id, tunnel_data in backup_data["tunnels"].items():
            config_manager.add_tunnel(tunnel_id, tunnel_data)
        
        return {"message": "Backup restored successfully!"}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in backup file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)