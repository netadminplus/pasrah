#!/usr/bin/env python3
"""
PasRah - SSH Tunnel Manager
Web Authentication Manager
"""

import hashlib
import secrets
import time
from typing import Optional, Dict
import jwt
import os

class WebAuthManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.secret_key = self._get_or_create_secret_key()
        self.active_sessions = {}  # session_id -> user_info
    
    def _get_or_create_secret_key(self) -> str:
        """Get or create JWT secret key"""
        key_file = self.config_manager.base_dir / "data" / "jwt_secret"
        
        if key_file.exists():
            with open(key_file, 'r') as f:
                return f.read().strip()
        else:
            # Generate new secret key
            secret = secrets.token_hex(32)
            with open(key_file, 'w') as f:
                f.write(secret)
            os.chmod(key_file, 0o600)
            return secret
    
    def setup_web_user(self, username: str, password: str) -> bool:
        """Setup web panel user during installation"""
        try:
            password_hash = self._hash_password(password)
            
            # Store in config
            self.config_manager.config["web_auth"] = {
                "username": username,
                "password_hash": password_hash,
                "created_at": time.time()
            }
            
            return self.config_manager.save_config()
        except Exception as e:
            print(f"Error setting up web user: {e}")
            return False
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return JWT token"""
        web_auth = self.config_manager.config.get("web_auth")
        if not web_auth:
            return None
        
        # Check credentials
        if (username == web_auth["username"] and 
            self._verify_password(password, web_auth["password_hash"])):
            
            # Generate JWT token
            payload = {
                "username": username,
                "exp": time.time() + 3600,  # 1 hour expiration
                "iat": time.time()
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm="HS256")
            
            # Store session
            session_id = secrets.token_hex(16)
            self.active_sessions[session_id] = {
                "username": username,
                "token": token,
                "created_at": time.time()
            }
            
            return token
        
        return None
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """Change web user password"""
        web_auth = self.config_manager.config.get("web_auth")
        if not web_auth:
            return False
        
        # Verify old password
        if not self._verify_password(old_password, web_auth["password_hash"]):
            return False
        
        # Update password
        web_auth["password_hash"] = self._hash_password(new_password)
        return self.config_manager.save_config()
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}:{password_hash.hex()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_hex = password_hash.split(':')
            password_hash_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return password_hash_check.hex() == hash_hex
        except:
            return False
