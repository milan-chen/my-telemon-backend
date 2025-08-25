#!/usr/bin/env python3
"""
配置管理模块
支持从 YAML 配置文件和环境变量加载配置
"""

import os
import yaml
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class ProxyConfig:
    """代理配置类"""
    enabled: bool = False
    type: str = "socks5"
    host: str = "127.0.0.1"
    port: int = 7890
    username: Optional[str] = None
    password: Optional[str] = None
    
    def has_proxy(self) -> bool:
        """检查是否配置了代理"""
        return bool(self.enabled and self.host and self.port)
    
    def get_proxy_dict(self) -> Optional[dict]:
        """获取 Telethon 兼容的代理配置"""
        if not self.has_proxy():
            return None
        
        proxy_config = {
            'proxy_type': self.type,
            'addr': self.host,
            'port': self.port,
        }
        
        # 如果有用户名密码，添加认证信息
        if self.username and self.password:
            proxy_config.update({
                'username': self.username,
                'password': self.password
            })
        
        return proxy_config


@dataclass
class TelegramConfig:
    """Telegram API 配置类"""
    api_id: str = "your_api_id_here"
    api_hash: str = "your_api_hash_here"
    phone: str = "+8613812345678"
    proxy: Optional[ProxyConfig] = None
    
    def __post_init__(self):
        if self.proxy is None:
            self.proxy = ProxyConfig()
    
    def validate(self) -> bool:
        """验证配置是否完整"""
        return all([
            self.api_id and self.api_id != 'your_api_id_here',
            self.api_hash and self.api_hash != 'your_api_hash_here',
            self.phone and self.phone.startswith('+')
        ])


@dataclass
class BotConfig:
    """Telegram Bot 配置类"""
    token: str = "your_bot_token_here"
    chat_ids: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.chat_ids is None:
            self.chat_ids = ["your_chat_id_here"]
    
    def validate(self) -> bool:
        """验证Bot配置是否完整"""
        # 验证 Bot Token
        if not self.token or self.token == 'your_bot_token_here':
            return False
            
        # 验证 Chat IDs
        if not self.chat_ids or len(self.chat_ids) == 0:
            return False
            
        # 验证每个 Chat ID 格式
        for chat_id in self.chat_ids:
            if not chat_id or chat_id == 'your_chat_id_here':
                return False
            # 检查 Chat ID 是否为数字（可以以负号开头）
            if not str(chat_id).lstrip('-').isdigit():
                return False
                
        return True


@dataclass
class ServerConfig:
    """服务器配置类"""
    host: str = "0.0.0.0"
    port: int = 8080
    session_dir: str = "sessions"

class AppConfig:
    """应用程序主配置类"""
    
    def __init__(self, config_file: str = "app_config.yaml"):
        self.config_file = config_file
        self.telegram = TelegramConfig()
        self.bot = BotConfig()
        self.server = ServerConfig()
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """加载配置文件和环境变量"""
        # 1. 首先从配置文件加载
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
                    self._apply_config_data(config_data)
            except Exception as e:
                print(f"警告: 配置文件加载失败: {e}")
        
        # 2. 然后从环境变量覆盖
        self._load_from_env()
    
    def _apply_config_data(self, config_data: Dict[str, Any]):
        """应用配置数据"""
        # Telegram 配置
        if 'telegram' in config_data:
            telegram_data = config_data['telegram']
            self.telegram.api_id = telegram_data.get('api_id', self.telegram.api_id)
            self.telegram.api_hash = telegram_data.get('api_hash', self.telegram.api_hash)
            self.telegram.phone = telegram_data.get('phone', self.telegram.phone)
        
        # 代理配置
        if 'proxy' in config_data:
            if self.telegram.proxy is None:
                self.telegram.proxy = ProxyConfig()
            proxy_data = config_data['proxy']
            self.telegram.proxy.enabled = proxy_data.get('enabled', False)
            self.telegram.proxy.type = proxy_data.get('type', 'socks5')
            self.telegram.proxy.host = proxy_data.get('host', '127.0.0.1')
            self.telegram.proxy.port = proxy_data.get('port', 7890)
            self.telegram.proxy.username = proxy_data.get('username')
            self.telegram.proxy.password = proxy_data.get('password')
        
        # Bot 配置
        if 'bot' in config_data:
            bot_data = config_data['bot']
            self.bot.token = bot_data.get('token', self.bot.token)
            self.bot.chat_ids = bot_data.get('chat_ids', self.bot.chat_ids)
        
        # 服务器配置
        if 'server' in config_data:
            server_data = config_data['server']
            self.server.host = server_data.get('host', self.server.host)
            self.server.port = server_data.get('port', self.server.port)
            self.server.session_dir = server_data.get('session_dir', self.server.session_dir)
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # Telegram 配置
        self.telegram.api_id = os.getenv('TELEGRAM_API_ID', self.telegram.api_id)
        self.telegram.api_hash = os.getenv('TELEGRAM_API_HASH', self.telegram.api_hash)
        self.telegram.phone = os.getenv('TELEGRAM_PHONE', self.telegram.phone)
        
        # 代理配置
        if self.telegram.proxy is None:
            self.telegram.proxy = ProxyConfig()
        if os.getenv('PROXY_ENABLED'):
            self.telegram.proxy.enabled = os.getenv('PROXY_ENABLED', '').lower() in ['true', '1', 'yes']
        if os.getenv('PROXY_TYPE'):
            proxy_type = os.getenv('PROXY_TYPE')
            if proxy_type:
                self.telegram.proxy.type = proxy_type
        if os.getenv('PROXY_HOST'):
            proxy_host = os.getenv('PROXY_HOST')
            if proxy_host:
                self.telegram.proxy.host = proxy_host
        if os.getenv('PROXY_PORT'):
            proxy_port = os.getenv('PROXY_PORT')
            if proxy_port:
                self.telegram.proxy.port = int(proxy_port)
        if os.getenv('PROXY_USERNAME'):
            self.telegram.proxy.username = os.getenv('PROXY_USERNAME')
        if os.getenv('PROXY_PASSWORD'):
            self.telegram.proxy.password = os.getenv('PROXY_PASSWORD')
        
        # Bot 配置
        self.bot.token = os.getenv('TELEGRAM_BOT_TOKEN', self.bot.token)
        if os.getenv('TELEGRAM_CHAT_IDS'):
            chat_ids_str = os.getenv('TELEGRAM_CHAT_IDS')
            if chat_ids_str:
                self.bot.chat_ids = [id.strip() for id in chat_ids_str.split(',') if id.strip()]
    
    def validate(self) -> tuple[bool, List[str]]:
        """验证所有配置
        
        Returns:
            tuple: (是否有效, 错误消息列表)
        """
        errors = []
        
        if not self.telegram.validate():
            errors.append("Telegram API 配置不完整：请检查 API ID、API Hash 和手机号")
        
        if not self.bot.validate():
            errors.append("Bot 配置不完整：请检查 Bot Token 和 Chat IDs")
        
        return len(errors) == 0, errors
    
    def validate_bot(self) -> bool:
        """验证Bot配置"""
        return self.bot.validate()
    
    @property
    def chat_ids(self) -> List[str]:
        """获取 Chat IDs"""
        return self.bot.chat_ids or []
    
    @property 
    def bot_token(self) -> str:
        """获取 Bot Token"""
        return self.bot.token


# 全局配置实例
config = AppConfig()