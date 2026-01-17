"""
Telegram Export Parser Service
Supports JSON and HTML exports from Telegram Desktop
"""
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class TelegramParser:
    """Parser for Telegram Desktop exports"""
    
    @staticmethod
    def detect_format(file_path: str) -> str:
        """Detect if file is JSON or HTML"""
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        if suffix == '.json':
            return 'json'
        elif suffix in ['.html', '.htm']:
            return 'html'
        else:
            # Try to detect by content
            with open(file_path, 'r', encoding='utf-8') as f:
                first_chars = f.read(100).strip()
                if first_chars.startswith('{') or first_chars.startswith('['):
                    return 'json'
                elif first_chars.startswith('<!DOCTYPE') or first_chars.startswith('<html'):
                    return 'html'
        
        raise ValueError(f"Unknown file format: {suffix}")
    
    @staticmethod
    def parse_json(file_path: str) -> Dict[str, Any]:
        """
        Parse Telegram Desktop JSON export
        Returns chat info and list of messages
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        chat_info = {
            'name': data.get('name', 'Unknown Chat'),
            'type': data.get('type', 'unknown'),
            'id': data.get('id', 0),
        }
        
        messages = []
        raw_messages = data.get('messages', [])
        
        for msg in raw_messages:
            # Skip service messages
            if msg.get('type') != 'message':
                continue
            
            # Extract text (can be string or list of entities)
            text = TelegramParser._extract_text(msg.get('text', ''))
            
            if not text or not text.strip():
                continue
            
            # Parse date
            date_str = msg.get('date', '')
            try:
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                date = None
            
            messages.append({
                'msg_id': str(msg.get('id', '')),
                'date': date,
                'author': msg.get('from', '') or msg.get('actor', ''),
                'author_id': str(msg.get('from_id', '') or msg.get('actor_id', '')),
                'text': text,
                'raw_json': msg,
            })
        
        return {
            'chat_info': chat_info,
            'messages': messages
        }
    
    @staticmethod
    def _extract_text(text_field: Any) -> str:
        """Extract plain text from Telegram text field"""
        if isinstance(text_field, str):
            return text_field
        elif isinstance(text_field, list):
            parts = []
            for item in text_field:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(item.get('text', ''))
            return ''.join(parts)
        return ''
    
    @staticmethod
    def parse_html(file_path: str) -> Dict[str, Any]:
        """
        Parse Telegram Desktop HTML export
        Basic support for extracting messages
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        
        # Try to get chat name
        title_elem = soup.find('div', class_='page_header')
        chat_name = title_elem.get_text(strip=True) if title_elem else 'Unknown Chat'
        
        chat_info = {
            'name': chat_name,
            'type': 'unknown',
            'id': 0,
        }
        
        messages = []
        msg_elements = soup.find_all('div', class_='message')
        
        for idx, msg_elem in enumerate(msg_elements):
            # Extract author
            author_elem = msg_elem.find('div', class_='from_name')
            author = author_elem.get_text(strip=True) if author_elem else ''
            
            # Extract text
            text_elem = msg_elem.find('div', class_='text')
            text = text_elem.get_text(strip=True) if text_elem else ''
            
            if not text:
                continue
            
            # Extract date
            date_elem = msg_elem.find('div', class_='date')
            date_str = date_elem.get('title', '') if date_elem else ''
            try:
                date = datetime.strptime(date_str, '%d.%m.%Y %H:%M:%S')
            except:
                date = None
            
            messages.append({
                'msg_id': str(idx),
                'date': date,
                'author': author,
                'author_id': '',
                'text': text,
                'raw_json': None,
            })
        
        return {
            'chat_info': chat_info,
            'messages': messages
        }
    
    @staticmethod
    def parse(file_path: str) -> Dict[str, Any]:
        """Auto-detect format and parse"""
        format_type = TelegramParser.detect_format(file_path)
        
        if format_type == 'json':
            return TelegramParser.parse_json(file_path)
        elif format_type == 'html':
            return TelegramParser.parse_html(file_path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")


def filter_relevant_messages(messages: List[Dict], min_length: int = 20) -> List[Dict]:
    """
    Filter messages to only include potentially relevant ones
    - Minimum text length
    - Contains keywords suggesting a task/vacancy
    """
    keywords = [
        'ищу', 'нужен', 'нужна', 'требуется', 'заказ',
        'вакансия', 'работа', 'проект', 'задача', 'разработка',
        'бот', 'сайт', 'парсер', 'автоматизация', 'интеграция',
        'crm', 'bitrix', 'telegram', 'whatsapp', 'скрипт',
        'нужно сделать', 'кто может', 'кто сделает', 'возьмется',
        'бюджет', 'оплата', 'тз', 'сроки', 'дедлайн',
        'looking for', 'need', 'developer', 'freelance',
    ]
    
    filtered = []
    for msg in messages:
        text = msg.get('text', '').lower()
        
        # Skip short messages
        if len(text) < min_length:
            continue
        
        # Check for keywords
        has_keyword = any(kw in text for kw in keywords)
        if has_keyword:
            filtered.append(msg)
    
    return filtered
