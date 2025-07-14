#!/usr/bin/env python3
"""
PasRah - Enhanced Web Dashboard Backend
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os
import requests
from datetime import datetime

# Add core modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigManager
from core.ssh_manager import SSHManager
from core.tunnel_manager import TunnelManager
from core.web_auth import WebAuthManager

# Pydantic models
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
    description: str = ""
    auto_start: bool = True

class LoginRequest(BaseModel):
    username: str
    password: str

# FastAPI app
app = FastAPI(title="PasRah Web Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Global managers
config_manager = ConfigManager()
ssh_manager = SSHManager(config_manager)
tunnel_manager = TunnelManager(config_manager, ssh_manager)
web_auth = WebAuthManager(config_manager)

def get_country_flag(ip):
    """Get country flag emoji for IP address"""
    try:
        if ip.startswith(('192.168.', '10.', '172.')) or ip == '127.0.0.1' or ip == 'localhost':
            return '🖥️'
        
        if ip.startswith('167.172.'):
            return '🇩🇪'
        elif ip.startswith('164.92.'):
            return '🇺🇸'
        elif ip.startswith('46.8.'):
            return '🇩🇪'
        elif ip.startswith('37.32.'):
            return '🇮🇷'
        elif ip.startswith('185.'):
            return '🇪🇺'
        
        return '🌍'
    except:
        return '🌍'

def get_local_ip():
    """Get local server public IP"""
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return 'Unknown'

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token"""
    token = credentials.credentials
    user = web_auth.verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user

@app.get("/")
async def root():
    """Serve the dashboard"""
    local_ip = get_local_ip()
    local_flag = get_country_flag(local_ip)
    
    return HTMLResponse(f'''
<!DOCTYPE html>
<html>
<head>
    <title>PasRah - SSH Tunnel Manager</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            background: linear-gradient(135deg, #1e3c72, #2a5298); 
            color: white; 
            margin: 0; 
            padding: 20px; 
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
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
        .table {{ width: 100%; border-collapse: collapse; }}
        .table th, .table td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
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
        }}
        .modal {{ 
            display: none; 
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            background: rgba(0,0,0,0.5); 
        }}
        .modal-content {{ 
            background: rgba(30,60,114,0.95); 
            margin: 10% auto; 
            padding: 20px; 
            width: 500px; 
            border-radius: 10px; 
        }}
        .top-bar {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
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
                <div v-if="loginError" style="color: red; margin-top: 10px;">{{{{ loginError }}}}</div>
            </form>
            <div style="margin-top: 20px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; font-size: 14px;">
                <strong>💡 Forgot credentials?</strong><br>
                SSH to server and run: <code>python3 ~/pasrah/cli/simple_cli.py</code>
            </div>
        </div>

        <div v-if="isAuthenticated" class="container">
            <div class="top-bar">
                <div>
                    <span style="font-size: 18px;">{local_flag}</span>
                    <span style="font-weight: bold; margin-left: 10px;">Local Server: {local_ip}</span>
                </div>
                <button @click="logout" class="btn" style="background: #dc3545;">Logout</button>
            </div>

            <div class="section">
                <h1>🚇 PasRah - SSH Tunnel Manager</h1>
                <p>Making Connections Possible Worldwide</p>
            </div>

            <div class="section">
                <h2>📊 Dashboard</h2>
                <p>Servers: {{{{ stats.servers }}}} | Tunnels: {{{{ stats.tunnels }}}} | Active: {{{{ stats.active_tunnels }}}}</p>
                <button @click="showAddServer" class="btn">Add Server</button>
                <button @click="showAddTunnel" class="btn">Add Tunnel</button>
                <button @click="refreshData" class="btn">Refresh</button>
            </div>

            <div class="section">
                <h2>🌐 Servers</h2>
                <table class="table">
                    <thead>
                        <tr><th>#</th><th>Server</th><th>Host:Port</th><th>Status</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                        <tr v-for="(server, index) in servers" :key="server.id">
                            <td>{{{{ index + 1 }}}}</td>
                            <td>{{{{ server.id }}}}</td>
                            <td>{{{{ getCountryFlag(server.host) }}}} {{{{ server.host }}}}:{{{{ server.port }}}}</td>
                            <td>{{{{ server.status || 'active' }}}}</td>
                            <td><button @click="deleteServer(server.id)" class="btn">Delete</button></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>🚇 Tunnels</h2>
                <table class="table">
                    <thead>
                        <tr><th>#</th><th>Name</th><th>Local Port</th><th>Remote</th><th>Status</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                        <tr v-for="(tunnel, index) in tunnels" :key="tunnel.id">
                            <td>{{{{ index + 1 }}}}</td>
                            <td>{{{{ tunnel.name }}}}</td>
                            <td>{{{{ tunnel.local_port }}}}</td>
                            <td>{{{{ getServerHost(tunnel.server_id) }}}}:{{{{ tunnel.remote_port }}}}</td>
                            <td>{{{{ tunnel.status }}}}</td>
                            <td>
                                <button @click="toggleTunnel(tunnel.id)" class="btn">{{{{ tunnel.status === 'active' ? 'Stop' : 'Start' }}}}</button>
                                <button @click="deleteTunnel(tunnel.id)" class="btn">Delete</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Modals -->
        <div id="serverModal" class="modal">
            <div class="modal-content">
                <h3>Add Server</h3>
                <form @submit.prevent="addServer">
                    <div class="form-group">
                        <input type="text" v-model="serverForm.host" placeholder="Host/IP" required>
                    </div>
                    <div class="form-group">
                        <input type="number" v-model="serverForm.port" placeholder="Port" required>
                    </div>
                    <div class="form-group">
                        <input type="text" v-model="serverForm.username" placeholder="Username" required>
                    </div>
                    <div class="form-group">
                        <input type="password" v-model="serverForm.password" placeholder="Password" required>
                    </div>
                    <button type="submit" class="btn">Add</button>
                    <button type="button" @click="closeModal" class="btn">Cancel</button>
                    <div v-if="serverResult">{{{{ serverResult }}}}</div>
                </form>
            </div>
        </div>

        <div id="tunnelModal" class="modal">
            <div class="modal-content">
                <h3>Add Tunnel</h3>
                <form @submit.prevent="addTunnel">
                    <div class="form-group">
                        <input type="text" v-model="tunnelForm.name" placeholder="Tunnel Name" required>
                    </div>
                    <div class="form-group">
                        <select v-model="tunnelForm.server_id" required>
                            <option value="">Select Server</option>
                            <option v-for="server in servers" :key="server.id" :value="server.id">{{{{ server.host }}}}</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <input type="number" v-model="tunnelForm.local_port" placeholder="Local Port" required>
                    </div>
                    <div class="form-group">
                        <input type="number" v-model="tunnelForm.remote_port" placeholder="Remote Port" required>
                    </div>
                    <button type="submit" class="btn">Create</button>
                    <button type="button" @click="closeModal" class="btn">Cancel</button>
                    <div v-if="tunnelResult">{{{{ tunnelResult }}}}</div>
                </form>
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
                stats: {{ servers: 0, tunnels: 0, active_tunnels: 0 }},
                servers: [],
                tunnels: [],
                serverForm: {{ host: '', port: 22, username: '', password: '' }},
                tunnelForm: {{ name: '', server_id: '', local_port: '', remote_port: '' }},
                serverResult: '',
                tunnelResult: ''
            }}}},
            methods: {{
                getCountryFlag(ip) {{
                    if (ip.startsWith('37.32.')) return '🇮🇷';
                    if (ip.startsWith('167.172.')) return '🇩🇪';
                    return '🌍';
                }},
                getServerHost(serverId) {{
                    const server = this.servers.find(s => s.id === serverId);
                    return server ? server.host : 'Unknown';
                }},
                async login() {{
                    try {{
                        const response = await axios.post('/api/login', this.loginForm);
                        this.token = response.data.token;
                        this.isAuthenticated = true;
                        this.loadData();
                    }} catch (error) {{
                        this.loginError = 'Login failed';
                    }}
                }},
                logout() {{ this.isAuthenticated = false; this.token = null; }},
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
                    }} catch (error) {{ console.error(error); }}
                }},
                showAddServer() {{ document.getElementById('serverModal').style.display = 'block'; }},
                showAddTunnel() {{ document.getElementById('tunnelModal').style.display = 'block'; }},
                closeModal() {{ 
                    document.getElementById('serverModal').style.display = 'none';
                    document.getElementById('tunnelModal').style.display = 'none';
                }},
                async addServer() {{
                    try {{
                        await axios.post('/api/servers', this.serverForm, {{ headers: {{ Authorization: `Bearer ${{this.token}}` }} }});
                        this.loadData();
                        this.closeModal();
                    }} catch (error) {{ this.serverResult = 'Failed to add server'; }}
                }},
                async addTunnel() {{
                    try {{
                        await axios.post('/api/tunnels', this.tunnelForm, {{ headers: {{ Authorization: `Bearer ${{this.token}}` }} }});
                        this.loadData();
                        this.closeModal();
                    }} catch (error) {{ this.tunnelResult = 'Failed to create tunnel'; }}
                }},
                async toggleTunnel(id) {{
                    try {{
                        await axios.post(`/api/tunnels/${{id}}/toggle`, {{}}, {{ headers: {{ Authorization: `Bearer ${{this.token}}` }} }});
                        this.loadData();
                    }} catch (error) {{ alert('Failed to toggle tunnel'); }}
                }},
                async deleteServer(id) {{
                    if (confirm('Delete server?')) {{
                        await axios.delete(`/api/servers/${{id}}`, {{ headers: {{ Authorization: `Bearer ${{this.token}}` }} }});
                        this.loadData();
                    }}
                }},
                async deleteTunnel(id) {{
                    if (confirm('Delete tunnel?')) {{
                        await axios.delete(`/api/tunnels/${{id}}`, {{ headers: {{ Authorization: `Bearer ${{this.token}}` }} }});
                        this.loadData();
                    }}
                }},
                async refreshData() {{ this.loadData(); }}
            }}
        }}).mount('#app');
    </script>
</body>
</html>''')

# API endpoints
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
    return {"servers": len(servers), "tunnels": len(tunnels), "active_tunnels": active_tunnels}

@app.get("/api/servers")
async def get_servers(user: dict = Depends(get_current_user)):
    servers = config_manager.get_servers()
    for server_id, server in servers.items():
        server["id"] = server_id
    return servers

@app.post("/api/servers")
async def add_server(server: ServerCreate, user: dict = Depends(get_current_user)):
    try:
        success, message = ssh_manager.test_connection(server.host, server.port, server.username, server.password)
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        server_id = f"{server.host}_{server.port}"
        config_manager.add_server(server_id, {"host": server.host, "port": server.port, "username": server.username, "password": server.password})
        
        options = {"update_system": server.update_system, "install_fail2ban": server.install_fail2ban, "create_user": server.create_user, "ssh_hardening": server.ssh_hardening}
        ssh_manager.setup_server(server_id, server.host, server.port, server.username, server.password, options)
        
        return {"message": f"Server added successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tunnels")
async def get_tunnels(user: dict = Depends(get_current_user)):
    tunnels = config_manager.get_tunnels()
    for tunnel_id, tunnel in tunnels.items():
        status = tunnel_manager.get_tunnel_status(tunnel_id)
        tunnel["status"] = status["status"]
        tunnel["id"] = tunnel_id
    return tunnels

@app.post("/api/tunnels")
async def add_tunnel(tunnel: TunnelCreate, user: dict = Depends(get_current_user)):
    try:
        tunnel_id = f"{tunnel.name}_{tunnel.local_port}".replace(" ", "_").lower()
        config_manager.add_tunnel(tunnel_id, {"name": tunnel.name, "server_id": tunnel.server_id, "local_port": tunnel.local_port, "remote_port": tunnel.remote_port, "remote_host": tunnel.remote_host, "description": tunnel.description, "auto_start": tunnel.auto_start})
        
        if tunnel.auto_start:
            tunnel_manager.create_tunnel(tunnel_id)
        
        return {"message": "Tunnel created successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tunnels/{tunnel_id}/toggle")
async def toggle_tunnel(tunnel_id: str, user: dict = Depends(get_current_user)):
    try:
        status = tunnel_manager.get_tunnel_status(tunnel_id)
        if status["status"] == "active":
            tunnel_manager.destroy_tunnel(tunnel_id)
        else:
            tunnel_manager.create_tunnel(tunnel_id)
        return {"message": "Tunnel toggled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tunnels/{tunnel_id}")
async def delete_tunnel(tunnel_id: str, user: dict = Depends(get_current_user)):
    try:
        tunnel_manager.destroy_tunnel(tunnel_id)
        config_manager.remove_tunnel(tunnel_id)
        return {"message": "Tunnel deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/servers/{server_id}")
async def delete_server(server_id: str, user: dict = Depends(get_current_user)):
    config_manager.remove_server(server_id)
    return {"message": "Server deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
