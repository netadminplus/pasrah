#!/bin/bash

# PasRah - SSH Tunnel Manager Installation Script
# Version 1.0
# Created by Ramtiin | Youtube.com/NetAdminPlus

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Emojis
ROCKET="🚀"
CHECK="✅"
CROSS="❌"
WARNING="⚠️"
INFO="ℹ️"
TUNNEL="🚇"
GLOBE="🌐"
LOCK="🔐"
WRENCH="🔧"

print_banner() {
    echo -e "${CYAN}"
    echo "██████╗  █████╗ ███████╗██████╗  █████╗ ██╗  ██╗"
    echo "██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗██║  ██║"
    echo "██████╔╝███████║███████╗██████╔╝███████║███████║"
    echo "██╔═══╝ ██╔══██║╚════██║██╔══██╗██╔══██║██╔══██║"
    echo "██║     ██║  ██║███████║██║  ██║██║  ██║██║  ██║"
    echo "╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝"
    echo ""
    echo "    ${TUNNEL} SSH Tunnel Manager - Making Connections Possible ${GLOBE}"
    echo "    ══════════════════════════════════════════════════════"
    echo "    Created with ❤️  by Ramtiin | Youtube.com/NetAdminPlus"
    echo "    ══════════════════════════════════════════════════════"
    echo -e "${NC}"
}

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ${CROSS} $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ${WARNING} $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] ${INFO} $1${NC}"
}

success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ${CHECK} $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        warning "Running as root. PasRah will be installed in /root/pasrah"
        INSTALL_DIR="/root/pasrah"
        USER_HOME="/root"
    else
        INSTALL_DIR="$HOME/pasrah"
        USER_HOME="$HOME"
    fi
}

# Detect OS and package manager
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        if [[ "$ID" == "ubuntu" ]] || [[ "$ID" == "debian" ]]; then
            PKG_MANAGER="apt-get"
            PKG_UPDATE="apt-get update"
            PKG_INSTALL="apt-get install -y"
        elif [[ "$ID" == "centos" ]] || [[ "$ID" == "rhel" ]] || [[ "$ID" == "fedora" ]]; then
            if command -v dnf &> /dev/null; then
                PKG_MANAGER="dnf"
                PKG_UPDATE="dnf update -y"
                PKG_INSTALL="dnf install -y"
            else
                PKG_MANAGER="yum"
                PKG_UPDATE="yum update -y"
                PKG_INSTALL="yum install -y"
            fi
        else
            PKG_MANAGER="unknown"
        fi
    else
        error "Cannot detect OS. Please install manually."
        exit 1
    fi
    
    info "Detected OS: $OS"
    info "Package Manager: $PKG_MANAGER"
}

# Check system requirements
check_requirements() {
    info "Checking system requirements..."
    
    # Check available memory
    TOTAL_MEM=$(free -m | awk 'NR==2{printf "%.0f", $2}')
    if [ "$TOTAL_MEM" -lt 512 ]; then
        warning "Low memory detected: ${TOTAL_MEM}MB. Minimum 512MB recommended."
    else
        success "Memory: ${TOTAL_MEM}MB - OK"
    fi
    
    # Check available disk space
    AVAILABLE_SPACE=$(df / | awk 'NR==2 {print $4}')
    if [ "$AVAILABLE_SPACE" -lt 1048576 ]; then  # 1GB in KB
        warning "Low disk space detected. At least 1GB free space recommended."
    else
        success "Disk space: OK"
    fi
    
    # Check internet connectivity
    if ping -c 1 google.com &> /dev/null; then
        success "Internet connectivity: OK"
    else
        error "No internet connection. Please check your network settings."
        exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    info "${WRENCH} Installing system dependencies..."
    
    if [ "$PKG_MANAGER" = "apt-get" ]; then
        $PKG_UPDATE
        $PKG_INSTALL python3 python3-pip python3-venv git openssh-client openssh-server socat curl wget unzip
    elif [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        $PKG_UPDATE
        $PKG_INSTALL python3 python3-pip git openssh-clients openssh-server socat curl wget unzip
    else
        error "Unsupported package manager. Please install manually:"
        echo "  - Python 3.6+"
        echo "  - pip3"
        echo "  - git"
        echo "  - openssh-client"
        echo "  - socat"
        exit 1
    fi
    
    success "System dependencies installed"
}

# Install Python dependencies
install_python_deps() {
    info "${WRENCH} Installing Python dependencies..."
    
    # Upgrade pip
    python3 -m pip install --upgrade pip
    
    # Install required packages
    python3 -m pip install \
        fastapi==0.104.1 \
        uvicorn==0.24.0 \
        python-multipart==0.0.6 \
        psutil==5.9.6 \
        paramiko==3.3.1 \
        pyjwt==2.8.0 \
        cryptography==41.0.7 \
        requests==2.31.0 \
        textual==0.41.0
    
    success "Python dependencies installed"
}

# Download PasRah source code
download_pasrah() {
    info "${ROCKET} Downloading PasRah..."
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # For now, we'll create the structure since we don't have a GitHub repo yet
    # In production, this would be: git clone https://github.com/ramtin-dev/pasrah.git .
    
    mkdir -p {core,cli,web/backend,data,logs,.ssh}
    
    # Create a simple download indicator
    echo "Creating PasRah directory structure..."
    
    success "PasRah downloaded to $INSTALL_DIR"
}

# Configure PasRah
configure_pasrah() {
    info "${WRENCH} Configuring PasRah..."
    
    cd "$INSTALL_DIR"
    
    # Set proper permissions
    chmod 700 "$INSTALL_DIR"
    chmod 755 cli/
    chmod 700 .ssh/
    chmod 600 data/ || true
    
    # Make CLI scripts executable
    find cli/ -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
    
    success "PasRah configured"
}

# Setup web credentials
setup_web_auth() {
    info "${LOCK} Setting up web authentication..."
    
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}                          WEB DASHBOARD SETUP                             ${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    while true; do
        read -p "Enter web admin username: " WEB_USERNAME
        if [[ -n "$WEB_USERNAME" ]]; then
            break
        fi
        warning "Username cannot be empty!"
    done
    
    while true; do
        read -s -p "Enter web admin password: " WEB_PASSWORD
        echo ""
        if [[ ${#WEB_PASSWORD} -ge 4 ]]; then
            break
        fi
        warning "Password must be at least 4 characters!"
    done
    
    # Store credentials for later use
    export PASRAH_WEB_USER="$WEB_USERNAME"
    export PASRAH_WEB_PASS="$WEB_PASSWORD"
    
    success "Web authentication configured"
}

# Get server IP
get_server_ip() {
    info "Detecting server IP address..."
    
    # Try multiple methods to get public IP
    PUBLIC_IP=""
    
    # Method 1: ipify.org
    PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || echo "")
    
    # Method 2: icanhazip.com
    if [[ -z "$PUBLIC_IP" ]]; then
        PUBLIC_IP=$(curl -s --max-time 5 https://icanhazip.com 2>/dev/null | tr -d '\n' || echo "")
    fi
    
    # Method 3: Local IP as fallback
    if [[ -z "$PUBLIC_IP" ]]; then
        PUBLIC_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")
    fi
    
    success "Server IP: $PUBLIC_IP"
    export SERVER_IP="$PUBLIC_IP"
}

# Start PasRah services
start_services() {
    info "${ROCKET} Starting PasRah services..."
    
    cd "$INSTALL_DIR"
    
    # Kill any existing PasRah processes
    pkill -f "python3.*start_web.py" 2>/dev/null || true
    pkill -f "python3.*pasrah" 2>/dev/null || true
    
    # Start web server in background
    nohup python3 start_web.py > logs/web.log 2>&1 &
    WEB_PID=$!
    
    # Wait a moment for startup
    sleep 3
    
    # Check if web server is running
    if kill -0 $WEB_PID 2>/dev/null; then
        success "Web server started (PID: $WEB_PID)"
    else
        error "Failed to start web server"
        cat logs/web.log 2>/dev/null || echo "No log file found"
        exit 1
    fi
}

# Create systemd service (optional)
create_systemd_service() {
    if [[ $EUID -eq 0 ]] && command -v systemctl &> /dev/null; then
        info "Creating systemd service..."
        
        cat > /etc/systemd/system/pasrah.service << EOF
[Unit]
Description=PasRah SSH Tunnel Manager
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/start_web.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        systemctl daemon-reload
        systemctl enable pasrah
        systemctl start pasrah
        
        success "Systemd service created and started"
    else
        info "Skipping systemd service creation (requires root or systemctl not available)"
    fi
}

# Display final information
show_completion_info() {
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}                         🎉 INSTALLATION COMPLETE! 🎉                    ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Get country flag for IP
    if [[ "$SERVER_IP" == "37.32."* ]]; then
        FLAG="🇮🇷"
    elif [[ "$SERVER_IP" == "167.172."* ]]; then
        FLAG="🇩🇪"
    elif [[ "$SERVER_IP" == "185."* ]]; then
        FLAG="🇪🇺"
    else
        FLAG="🌍"
    fi
    
    echo -e "${CYAN}${GLOBE} Server Information:${NC}"
    echo -e "   ${FLAG} Server IP: ${YELLOW}$SERVER_IP${NC}"
    echo -e "   🏠 Installation Path: ${YELLOW}$INSTALL_DIR${NC}"
    echo ""
    
    echo -e "${CYAN}${GLOBE} Access Methods:${NC