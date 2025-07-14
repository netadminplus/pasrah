# 🚇 PasRah - SSH Tunnel Manager

**Making Connections Possible Worldwide**

PasRah is a professional SSH tunnel management system that helps you create secure connections to bypass network restrictions and access blocked services.

📖 **[Persian/فارسی](README-fa.md)** | **English**

## 🚀 Quick Installation

```bash
# Install PasRah on your server
curl -sSL https://raw.githubusercontent.com/ramtin-dev/pasrah/main/install.sh | bash

# Or manual installation
git clone https://github.com/ramtin-dev/pasrah.git
cd pasrah
sudo bash install.sh
```

## 💡 What is PasRah?

PasRah creates secure SSH tunnels between your local server and remote servers, allowing users to:

- **Bypass internet filtering and censorship**
- **Access blocked websites and services** 
- **Secure internet browsing** through encrypted tunnels
- **Share internet access** with friends and family

## 🎯 Use Cases

- **Personal VPN**: Create your own VPN service
- **Bypass Restrictions**: Access blocked social media, news, streaming
- **Secure Browsing**: Encrypt your internet traffic
- **Business Access**: Connect to international services
- **Gaming**: Reduce ping and access geo-blocked games

## 🖥️ How to Use

### 1. Web Dashboard (Recommended)
```bash
# Access via browser
http://YOUR-SERVER-IP:8080

# Login with credentials you set during installation
```

### 2. Terminal Interface
```bash
# Command line management
python3 ~/pasrah/cli/simple_cli.py
```

## 📋 Basic Setup

1. **Install PasRah** on your local server (VPS, home server, etc.)
2. **Add remote servers** with SSH access 
3. **Create tunnels** between local and remote servers
4. **Share access** - give users your `LOCAL-IP:PORT`
5. **Users connect** via proxy/SOCKS settings in their apps

## 🔧 Management Features

- ✅ **Web Dashboard** - Beautiful browser interface
- ✅ **Terminal CLI** - Command line management
- ✅ **Multiple Servers** - Manage unlimited remote servers
- ✅ **Auto-Reconnect** - Automatic tunnel recovery
- ✅ **Real-time Status** - Live monitoring
- ✅ **Security Features** - SSH key management
- ⏳ **Bandwidth Monitor** - Traffic statistics (coming soon)
- ⏳ **Backup/Restore** - Configuration backup (coming soon)

## 🌐 Example Usage

```bash
# User in Iran wants to access Instagram
# Your server: 37.32.12.176 (Iran)
# Remote server: 167.172.165.40 (Germany)
# Create tunnel: 37.32.12.176:443 → 167.172.165.40:443

# User configures proxy in phone/browser:
# Proxy: 37.32.12.176:443
# Now user's traffic routes through Germany
```

## 🛡️ Security Notes

- Uses **SSH encryption** for all connections
- Automatic **SSH key generation**
- **Password-protected** web interface
- **Server hardening** options available
- Regular **security updates**

## 🆘 Support

- **Forgot web password?** Run: `python3 ~/pasrah/cli/simple_cli.py`
- **Change password**: Use CLI change password feature
- **Backup config**: Use web backup/restore feature
- **Issues**: Check logs in `~/pasrah/logs/`

## 👨‍💻 Created by

**Ramtiin** | 🎥 [Youtube.com/NetAdminPlus](https://youtube.com/NetAdminPlus)

## 📄 License

MIT License - Free for personal and commercial use

---

**⚡ Quick Start:** `curl -sSL https://get.pasrah.io | bash`