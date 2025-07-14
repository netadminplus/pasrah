#!/usr/bin/env python3
"""
PasRah - Minimal Working Version
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Container, Vertical
import sys
import os

# Add core modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class PasRahApp(App):
    """Minimal PasRah application"""
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("PasRah - SSH Tunnel Manager")
        yield Static("Press 'q' or 'escape' to quit")
        yield Static("This is a test to ensure the app works")
        yield Button("Click me!", id="test_btn")
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "test_btn":
            self.bell()
            self.exit("Button clicked - app working!")

if __name__ == "__main__":
    app = PasRahApp()
    app.run()
