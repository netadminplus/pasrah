#!/usr/bin/env python3
"""
PasRah - Working SSH Tunnel Manager
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button, Input, DataTable, TextArea
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual import work
import sys
import os
import asyncio

# Add core modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigManager
from core.ssh_manager import SSHManager
from core.tunnel_manager import TunnelManager

class AddServerScreen(Screen):
    """Screen for adding servers"""
    
    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Add Remote Server"),
            Static(""),
            Static("Host/IP:"),
            Input(placeholder="46.8.233.208", id="host"),
            Static("Port:"),
            Input(value="22", id="port"),
            Static("Username:"),
            Input(placeholder="root", id="username"),
            Static("Password:"),
            Input(password=True, id="password"),
            Static(""),
            Horizontal(
                Button("Test Connection", id="test"),
                Button("Add Server", id="add"),
                Button("Back", id="back"),
            ),
            Static(""),
            TextArea("Enter server details above...", id="result", read_only=True),
        )
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "test":
            self.test_connection()
        elif event.button.id == "add":
            self.add_server()
        elif event.button.id == "back":
            self.app.pop_screen()
    
    @work(exclusive=True)
    async def test_connection(self):
        host = self.query_one("#host", Input).value
        port = int(self.query_one("#port", Input).value or "22")
        username = self.query_one("#username", Input).value
        password = self.query_one("#password", Input).value
        
        result = self.query_one("#result", TextArea)
        
        if not all([host, username, password]):
            result.text = "Please fill in Host, Username, and Password"
            return
        
        result.text = "Testing connection..."
        
        success, message = self.app.ssh_manager.test_connection(host, port, username, password)
        
        if success:
            result.text = f"SUCCESS: {message}"
        else:
            result.text = f"FAILED: {message}"
    
    @work(exclusive=True)
    async def add_server(self):
        host = self.query_one("#host", Input).value
        port = int(self.query_one("#port", Input).value or "22")
        username = self.query_one("#username", Input).value
        password = self.query_one("#password", Input).value
        
        result = self.query_one("#result", TextArea)
        
        if not all([host, username, password]):
            result.text = "Please fill in all fields"
            return
        
        result.text = "Adding server..."
        
        server_id = f"{host}_{port}"
        
        # Add to config
        self.app.config_manager.add_server(server_id, {
            "host": host,
            "port": port,
            "username": username,
            "password": password
        })
        
        # Setup server
        success, message = self.app.ssh_manager.setup_server(
            server_id, host, port, username, password, {}
        )
        
        if success:
            result.text = f"SUCCESS: Server {server_id} added!\n\n{message}"
        else:
            result.text = f"FAILED: {message}"

class MainScreen(Screen):
    """Main screen"""
    
    BINDINGS = [
        ("a", "add_server", "Add Server"),
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("PasRah - SSH Tunnel Manager v1.0"),
            Static(""),
            Static("Dashboard:"),
            Static("Servers: 0", id="server_count"),
            Static("Tunnels: 0", id="tunnel_count"),
            Static(""),
            Horizontal(
                Button("Add Server (A)", id="add_server"),
                Button("Refresh (R)", id="refresh"),
                Button("Quit (Q)", id="quit"),
            ),
            Static(""),
            Static("Remote Servers:"),
            DataTable(id="servers"),
            Static(""),
            Static("SSH Tunnels:"),
            DataTable(id="tunnels"),
            Static(""),
            Static("Keys: A=Add Server | R=Refresh | Q=Quit | Esc=Back"),
            Static("Created with ❤️ by Ramtiin | Youtube.com/NetAdminPlus"),
        )
        yield Footer()
    
    def on_mount(self) -> None:
        self.refresh_data()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add_server":
            self.app.push_screen(AddServerScreen())
        elif event.button.id == "refresh":
            self.refresh_data()
        elif event.button.id == "quit":
            self.app.exit()
    
    def action_add_server(self) -> None:
        self.app.push_screen(AddServerScreen())
    
    def action_refresh(self) -> None:
        self.refresh_data()
    
    def action_quit(self) -> None:
        self.app.exit()
    
    def refresh_data(self):
        # Update counts
        servers = self.app.config_manager.get_servers()
        tunnels = self.app.config_manager.get_tunnels()
        
        self.query_one("#server_count", Static).update(f"Servers: {len(servers)}")
        self.query_one("#tunnel_count", Static).update(f"Tunnels: {len(tunnels)}")
        
        # Update servers table
        servers_table = self.query_one("#servers", DataTable)
        servers_table.clear(columns=True)
        servers_table.add_columns("ID", "Host:Port", "Status")
        
        if servers:
            for server_id, server in servers.items():
                servers_table.add_row(
                    server_id,
                    f"{server['host']}:{server['port']}",
                    server.get('status', 'unknown')
                )
        else:
            servers_table.add_row("No servers", "Press A to add", "one")
        
        # Update tunnels table
        tunnels_table = self.query_one("#tunnels", DataTable)
        tunnels_table.clear(columns=True)
        tunnels_table.add_columns("Name", "Local Port", "Status")
        
        if tunnels:
            for tunnel_id, tunnel in tunnels.items():
                status = self.app.tunnel_manager.get_tunnel_status(tunnel_id)
                tunnels_table.add_row(
                    tunnel['name'],
                    str(tunnel['local_port']),
                    status['status']
                )
        else:
            tunnels_table.add_row("No tunnels", "Add server first", "inactive")

class PasRahApp(App):
    """Main app"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.ssh_manager = SSHManager(self.config_manager)
        self.tunnel_manager = TunnelManager(self.config_manager, self.ssh_manager)
    
    def compose(self) -> ComposeResult:
        yield MainScreen()

if __name__ == "__main__":
    app = PasRahApp()
    app.run()
