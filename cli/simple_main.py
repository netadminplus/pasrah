#!/usr/bin/env python3
"""
PasRah - SSH Tunnel Manager
Simple Terminal Interface
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, Input, Label, DataTable
from textual.screen import Screen
import sys
import os

# Add core modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_manager import ConfigManager
from core.ssh_manager import SSHManager
from core.tunnel_manager import TunnelManager

class PasRahApp(App):
    """Simple PasRah application"""
    
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
    """
    
    BINDINGS = [
        ("f2", "add_server", "Add Server"),
        ("f3", "add_tunnel", "Add Tunnel"), 
        ("f5", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.ssh_manager = SSHManager(self.config_manager)
        self.tunnel_manager = TunnelManager(self.config_manager, self.ssh_manager)
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("🚇 PasRah - SSH Tunnel Manager v1.0", classes="title"),
            Static("", id="blank1"),
            Static("📊 Dashboard", classes="title"),
            Static(f"🌐 Remote Servers: {len(self.config_manager.get_servers())}", classes="stats"),
            Static(f"🚇 Active Tunnels: {len(self.tunnel_manager.active_tunnels)}", classes="stats"),
            Static("", id="blank2"),
            Static("🔄 Quick Actions", classes="title"),
            Horizontal(
                Button("Add Server (F2)", id="add_server", variant="primary"),
                Button("Add Tunnel (F3)", id="add_tunnel", variant="success"),
                Button("Refresh (F5)", id="refresh", variant="default"),
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
            Static("Created with ❤️ by Ramtiin | Youtube.com/NetAdminPlus", classes="stats"),
        )
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize app"""
        self.title = "PasRah v1.0"
        self.refresh_tables()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks"""
        if event.button.id == "add_server":
            self.action_add_server()
        elif event.button.id == "add_tunnel":
            self.action_add_tunnel()
        elif event.button.id == "refresh":
            self.action_refresh()
        elif event.button.id == "quit_btn":
            self.exit()
    
    def action_add_server(self) -> None:
        """Add server action"""
        self.bell()
        # For now, just show a message
        servers_table = self.query_one("#servers_table", DataTable)
        if not servers_table.columns:
            servers_table.add_columns("Message")
        servers_table.add_row("Press F2 to add servers (feature coming soon)")
    
    def action_add_tunnel(self) -> None:
        """Add tunnel action"""
        self.bell()
        tunnels_table = self.query_one("#tunnels_table", DataTable)
        if not tunnels_table.columns:
            tunnels_table.add_columns("Message")
        tunnels_table.add_row("Press F3 to add tunnels (feature coming soon)")
    
    def action_refresh(self) -> None:
        """Refresh action"""
        self.bell()
        self.refresh_tables()
    
    def refresh_tables(self):
        """Refresh data tables"""
        # Servers table
        servers_table = self.query_one("#servers_table", DataTable)
        servers_table.clear(columns=True)
        servers_table.add_columns("Server ID", "Host:Port", "Status")
        
        servers = self.config_manager.get_servers()
        if servers:
            for server_id, server in servers.items():
                servers_table.add_row(
                    server_id,
                    f"{server['host']}:{server['port']}", 
                    server.get('status', 'unknown')
                )
        else:
            servers_table.add_row("No servers", "Add a server", "with F2")
        
        # Tunnels table
        tunnels_table = self.query_one("#tunnels_table", DataTable)
        tunnels_table.clear(columns=True)
        tunnels_table.add_columns("Tunnel Name", "Local Port", "Status")
        
        tunnels = self.config_manager.get_tunnels()
        if tunnels:
            for tunnel_id, tunnel in tunnels.items():
                status = self.tunnel_manager.get_tunnel_status(tunnel_id)
                tunnels_table.add_row(
                    tunnel['name'],
                    str(tunnel['local_port']),
                    status['status']
                )
        else:
            tunnels_table.add_row("No tunnels", "Add tunnel", "with F3")

if __name__ == "__main__":
    app = PasRahApp()
    app.run()
