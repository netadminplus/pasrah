#!/usr/bin/env python3
"""
PasRah - SSH Tunnel Manager
Full Terminal Interface
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, Input, Label, DataTable, TextArea, Checkbox, Select
from textual.screen import Screen
from textual import work
import sys
import os

# Add core modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigManager
from core.ssh_manager import SSHManager
from core.tunnel_manager import TunnelManager

class AddServerScreen(Screen):
    """Screen for adding remote servers"""
    
    CSS = """
    .title {
        text-align: center;
        text-style: bold;
        color: cyan;
        margin: 1;
    }
    
    .label {
        width: 15;
        text-align: right;
        margin: 0 1;
    }
    
    .input-row {
        height: 3;
        margin: 1;
    }
    
    .button-row {
        height: 3;
        margin: 1;
        align: center middle;
    }
    
    .result-area {
        margin: 1;
        min-height: 8;
    }
    """
    
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+t", "test", "Test Connection"),
        ("ctrl+s", "save", "Add Server"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("🌐 Add Remote Server", classes="title"),
            Horizontal(
                Label("Host/IP:", classes="label"),
                Input(placeholder="46.8.233.208", id="host_input"),
                classes="input-row"
            ),
            Horizontal(
                Label("SSH Port:", classes="label"),
                Input(placeholder="22", id="port_input", value="22"),
                classes="input-row"
            ),
            Horizontal(
                Label("Username:", classes="label"),
                Input(placeholder="root", id="username_input"),
                classes="input-row"
            ),
            Horizontal(
                Label("Password:", classes="label"),
                Input(placeholder="password", password=True, id="password_input"),
                classes="input-row"
            ),
            Static("🔧 Server Setup Options"),
            Checkbox("Update system packages", id="update_system"),
            Checkbox("Install fail2ban security", id="install_fail2ban"),
            Checkbox("Create dedicated user", id="create_user"),
            Checkbox("SSH security hardening", id="ssh_hardening"),
            Horizontal(
                Button("Test (Ctrl+T)", id="test_btn", variant="primary"),
                Button("Add Server (Ctrl+S)", id="add_btn", variant="success"),
                Button("Cancel (Esc)", id="cancel_btn", variant="error"),
                classes="button-row"
            ),
            TextArea("Enter server details above and test connection...", id="result_area", read_only=True, classes="result-area"),
        )
        yield Footer()
    
    def on_mount(self) -> None:
        """Focus first input"""
        self.query_one("#host_input", Input).focus()
    
    def action_cancel(self) -> None:
        """Cancel and go back"""
        self.app.pop_screen()
    
    def action_test(self) -> None:
        """Test connection"""
        self.test_connection()
    
    def action_save(self) -> None:
        """Add server"""
        self.add_server()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "test_btn":
            self.test_connection()
        elif event.button.id == "add_btn":
            self.add_server()
        elif event.button.id == "cancel_btn":
            self.app.pop_screen()
    
    @work(exclusive=True)
    async def test_connection(self):
        """Test SSH connection to server"""
        host = self.query_one("#host_input", Input).value
        port = int(self.query_one("#port_input", Input).value or "22")
        username = self.query_one("#username_input", Input).value
        password = self.query_one("#password_input", Input).value
        
        if not all([host, username, password]):
            result_area = self.query_one("#result_area", TextArea)
            result_area.text = "❌ Please fill in Host, Username, and Password first."
            return
        
        result_area = self.query_one("#result_area", TextArea)
        result_area.text = "�� Testing connection to server...\nPlease wait..."
        
        # Test connection
        success, message = self.app.ssh_manager.test_connection(host, port, username, password)
        
        if success:
            result_area.text = f"✅ {message}\n\nRemote server is reachable and credentials are valid.\nYou can now add this server."
        else:
            result_area.text = f"❌ {message}\n\nPlease check your connection details and try again."
    
    @work(exclusive=True)
    async def add_server(self):
        """Add server with configuration"""
        host = self.query_one("#host_input", Input).value
        port = int(self.query_one("#port_input", Input).value or "22")
        username = self.query_one("#username_input", Input).value
        password = self.query_one("#password_input", Input).value
        
        if not all([host, username, password]):
            result_area = self.query_one("#result_area", TextArea)
            result_area.text = "❌ Please fill in all required fields (Host, Username, Password)."
            return
        
        # Get options
        options = {
            "update_system": self.query_one("#update_system", Checkbox).value,
            "install_fail2ban": self.query_one("#install_fail2ban", Checkbox).value,
            "create_user": self.query_one("#create_user", Checkbox).value,
            "ssh_hardening": self.query_one("#ssh_hardening", Checkbox).value,
        }
        
        result_area = self.query_one("#result_area", TextArea)
        result_area.text = f"🔧 Setting up remote server {host}...\nThis may take a few minutes..."
        
        # Generate server ID
        server_id = f"{host}_{port}"
        
        # Add server to config
        self.app.config_manager.add_server(server_id, {
            "host": host,
            "port": port,
            "username": username,
            "password": password
        })
        
        # Setup server
        success, message = self.app.ssh_manager.setup_server(
            server_id, host, port, username, password, options
        )
        
        if success:
            result_area.text = f"✅ Server '{server_id}' added successfully!\n\n{message}\n\nYou can now create tunnels to this server.\nPress Esc to return to main screen."
        else:
            result_area.text = f"❌ Server setup failed:\n\n{message}\n\nPlease check the details and try again."

class AddTunnelScreen(Screen):
    """Screen for adding tunnels"""
    
    CSS = """
    .title {
        text-align: center;
        text-style: bold;
        color: cyan;
        margin: 1;
    }
    
    .label {
        width: 15;
        text-align: right;
        margin: 0 1;
    }
    
    .input-row {
        height: 3;
        margin: 1;
    }
    
    .button-row {
        height: 3;
        margin: 1;
        align: center middle;
    }
    
    .result-area {
        margin: 1;
        min-height: 8;
    }
    """
    
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+c", "create", "Create Tunnel"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("🚇 Add SSH Tunnel", classes="title"),
            Horizontal(
                Label("Tunnel Name:", classes="label"),
                Input(placeholder="My Tunnel", id="name_input"),
                classes="input-row"
            ),
            Horizontal(
                Label("Remote Server:", classes="label"),
                Select([], id="server_select"),
                classes="input-row"
            ),
            Horizontal(
                Label("Local Port:", classes="label"),
                Input(placeholder="444", id="local_port_input"),
                classes="input-row"
            ),
            Horizontal(
                Label("Remote Port:", classes="label"),
                Input(placeholder="444", id="remote_port_input"),
                classes="input-row"
            ),
            Horizontal(
                Label("Remote Host:", classes="label"),
                Input(placeholder="localhost", id="remote_host_input", value="localhost"),
                classes="input-row"
            ),
            Horizontal(
                Label("Description:", classes="label"),
                Input(placeholder="Optional description", id="description_input"),
                classes="input-row"
            ),
            Checkbox("Auto-start tunnel", id="auto_start", value=True),
            Horizontal(
                Button("Create (Ctrl+C)", id="create_btn", variant="success"),
                Button("Cancel (Esc)", id="cancel_btn", variant="error"),
                classes="button-row"
            ),
            TextArea("Select a remote server and configure tunnel settings...", id="result_area", read_only=True, classes="result-area"),
        )
        yield Footer()
    
    def on_mount(self) -> None:
        """Populate server dropdown and focus first input"""
        server_select = self.query_one("#server_select", Select)
        servers = self.app.config_manager.get_servers()
        
        options = []
        for server_id, server in servers.items():
            options.append((f"{server['host']}:{server['port']}", server_id))
        
        if options:
            server_select.set_options(options)
            self.query_one("#name_input", Input).focus()
        else:
            result_area = self.query_one("#result_area", TextArea)
            result_area.text = "❌ No remote servers found.\n\nPlease add a server first using 'a' from the main screen."
    
    def action_cancel(self) -> None:
        """Cancel and go back"""
        self.app.pop_screen()
    
    def action_create(self) -> None:
        """Create tunnel"""
        self.create_tunnel()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create_btn":
            self.create_tunnel()
        elif event.button.id == "cancel_btn":
            self.app.pop_screen()
    
    @work(exclusive=True)
    async def create_tunnel(self):
        """Create new tunnel"""
        name = self.query_one("#name_input", Input).value
        server_id = self.query_one("#server_select", Select).value
        local_port = self.query_one("#local_port_input", Input).value
        remote_port = self.query_one("#remote_port_input", Input).value
        remote_host = self.query_one("#remote_host_input", Input).value
        description = self.query_one("#description_input", Input).value
        auto_start = self.query_one("#auto_start", Checkbox).value
        
        if not all([name, server_id, local_port, remote_port]):
            result_area = self.query_one("#result_area", TextArea)
            result_area.text = "❌ Please fill in all required fields:\nTunnel Name, Remote Server, Local Port, Remote Port"
            return
        
        try:
            local_port = int(local_port)
            remote_port = int(remote_port)
        except ValueError:
            result_area = self.query_one("#result_area", TextArea)
            result_area.text = "❌ Ports must be valid numbers."
            return
        
        result_area = self.query_one("#result_area", TextArea)
        result_area.text = f"🚇 Creating tunnel '{name}'...\nLocal port: {local_port}\nRemote: {remote_host}:{remote_port}"
        
        # Generate tunnel ID
        tunnel_id = f"{name}_{local_port}".replace(" ", "_").lower()
        
        # Add tunnel to config
        success = self.app.config_manager.add_tunnel(tunnel_id, {
            "name": name,
            "server_id": server_id,
            "local_port": local_port,
            "remote_port": remote_port,
            "remote_host": remote_host,
            "description": description,
            "auto_start": auto_start
        })
        
        if success:
            # Start tunnel if auto_start is enabled
            if auto_start:
                tunnel_success, tunnel_message = self.app.tunnel_manager.create_tunnel(tunnel_id)
                if tunnel_success:
                    result_area.text = f"✅ Tunnel '{name}' created and started!\n\n{tunnel_message}\n\nUsers can now connect to:\nLocal Server IP:{local_port}\n\nPress Esc to return to main screen."
                else:
                    result_area.text = f"✅ Tunnel '{name}' created but failed to start:\n\n{tunnel_message}\n\nYou can try starting it manually from the main screen."
            else:
                result_area.text = f"✅ Tunnel '{name}' created successfully!\n\nUse 's' from main screen to start the tunnel.\nPress Esc to return to main screen."
        else:
            result_area.text = "❌ Failed to create tunnel configuration.\nPlease try again."

class MainScreen(Screen):
    """Main application screen"""
    
    CSS = """
    .title {
        text-align: center;
        text-style: bold;
        color: cyan;
        background: black;
        margin: 1;
    }
    
    .button-row {
        height: 3;
        margin: 1;
    }
    
    .stats {
        text-align: center;
        color: green;
        background: black;
        margin: 1;
    }
    
    Container {
        background: black;
    }
    
    DataTable {
        margin: 1;
    }
    """
    
    BINDINGS = [
        ("a", "add_server", "Add Server"),
        ("t", "add_tunnel", "Add Tunnel"), 
        ("r", "refresh", "Refresh"),
        ("s", "start_tunnel", "Start/Stop Tunnel"),
        ("d", "delete_item", "Delete"),
        ("q", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("🚇 PasRah - SSH Tunnel Manager v1.0", classes="title"),
            Static("", id="blank1"),
            Static("📊 Dashboard", classes="title"),
            Static(f"🌐 Remote Servers: 0", id="server_stat", classes="stats"),
            Static(f"🚇 Active Tunnels: 0", id="tunnel_stat", classes="stats"),
            Static("", id="blank2"),
            Static("🔄 Quick Actions", classes="title"),
            Horizontal(
                Button("Add Server (A)", id="add_server", variant="primary"),
                Button("Add Tunnel (T)", id="add_tunnel", variant="success"),
                Button("Refresh (R)", id="refresh", variant="default"),
                Button("Start/Stop (S)", id="start_stop", variant="warning"),
                Button("Quit (Q)", id="quit_btn", variant="error"),
                classes="button-row"
            ),
            Static("", id="blank3"),
            Static("🌐 Remote Servers", classes="title"),
            DataTable(id="servers_table"),
            Static("", id="blank4"),
            Static("🚇 SSH Tunnels", classes="title"), 
            DataTable(id="tunnels_table"),
            Static("", id="blank5"),
            Static("Use Arrow Keys to navigate tables | A=Add Server | T=Add Tunnel | R=Refresh | S=Start/Stop | Q=Quit", classes="stats"),
            Static("Created with ❤️ by Ramtiin | Youtube.com/NetAdminPlus", classes="stats"),
        )
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize app"""
        self.title = "PasRah v1.0"
        self.refresh_all()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks"""
        if event.button.id == "add_server":
            self.action_add_server()
        elif event.button.id == "add_tunnel":
            self.action_add_tunnel()
        elif event.button.id == "refresh":
            self.action_refresh()
        elif event.button.id == "start_stop":
            self.action_start_tunnel()
        elif event.button.id == "quit_btn":
            self.exit()
    
    def action_add_server(self) -> None:
        """Add server action"""
        self.app.push_screen(AddServerScreen())
    
    def action_add_tunnel(self) -> None:
        """Add tunnel action"""
        self.app.push_screen(AddTunnelScreen())
    
    def action_refresh(self) -> None:
        """Refresh action"""
        self.refresh_all()
    
    def action_start_tunnel(self) -> None:
        """Start/stop tunnel action"""
        self.bell()  # Just a placeholder for now
    
    def action_delete_item(self) -> None:
        """Delete selected item"""
        self.bell()  # Just a placeholder for now
    
    def refresh_all(self):
        """Refresh all data"""
        self.refresh_servers_table()
        self.refresh_tunnels_table()
        self.refresh_stats()
    
    def refresh_servers_table(self):
        """Refresh servers table"""
        table = self.query_one("#servers_table", DataTable)
        table.clear(columns=True)
        table.add_columns("Server ID", "Host:Port", "Status", "Tunnels")
        
        servers = self.app.config_manager.get_servers()
        if servers:
            for server_id, server in servers.items():
                tunnel_count = len(server.get('tunnels', []))
                table.add_row(
                    server_id,
                    f"{server['host']}:{server['port']}", 
                    server.get('status', 'unknown'),
                    str(tunnel_count)
                )
        else:
            table.add_row("No servers", "Press 'A' to add", "a server", "0")
    
    def refresh_tunnels_table(self):
        """Refresh tunnels table"""
        table = self.query_one("#tunnels_table", DataTable)
        table.clear(columns=True)
        table.add_columns("Tunnel Name", "Local Port", "Remote", "Status")
        
        tunnels = self.app.config_manager.get_tunnels()
        if tunnels:
            for tunnel_id, tunnel in tunnels.items():
                status = self.app.tunnel_manager.get_tunnel_status(tunnel_id)
                table.add_row(
                    tunnel['name'],
                    str(tunnel['local_port']),
                    f"{tunnel['remote_host']}:{tunnel['remote_port']}",
                    status['status']
                )
        else:
            table.add_row("No tunnels", "Press 'T' to add", "a tunnel", "inactive")
    
    def refresh_stats(self):
        """Refresh dashboard statistics"""
        servers_count = len(self.app.config_manager.get_servers())
        tunnels_count = len(self.app.tunnel_manager.active_tunnels)
        
        self.query_one("#server_stat", Static).update(f"🌐 Remote Servers: {servers_count}")
        self.query_one("#tunnel_stat", Static).update(f"🚇 Active Tunnels: {tunnels_count}")

class PasRahApp(App):
    """Main PasRah application"""
    
    TITLE = "PasRah - SSH Tunnel Manager"
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.ssh_manager = SSHManager(self.config_manager)
        self.tunnel_manager = TunnelManager(self.config_manager, self.ssh_manager)
    
    def compose(self) -> ComposeResult:
        yield MainScreen()
    
    def on_mount(self) -> None:
        """App initialization"""
        self.title = "PasRah v1.0"
        self.sub_title = "SSH Tunnel Manager"

if __name__ == "__main__":
    app = PasRahApp()
    app.run()
