"""
Service for encrypting and decrypting sensitive data like API keys.
"""

import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting/decrypting sensitive data"""
    
    _instance: Optional['EncryptionService'] = None
    _fernet: Optional[Fernet] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._fernet is None:
            self._fernet = self._create_fernet()
    
    def _create_fernet(self) -> Fernet:
        """Create Fernet cipher from SECRET_KEY"""
        try:
            # Use SECRET_KEY as password for key derivation
            password = settings.SECRET_KEY.encode()
            salt = b'rent_no_fees_llm_salt'  # Fixed salt for consistency
            
            # Derive key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            
            return Fernet(key)
        except Exception as e:
            logger.error("Error creating Fernet cipher: %s", e)
            raise
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string"""
        try:
            if not plaintext:
                return ""
            encrypted = self._fernet.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error("Error encrypting data: %s", e)
            raise
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string"""
        try:
            if not ciphertext:
                return ""
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error("Error decrypting data: %s", e)
            raise


# Singleton instance
encryption_service = EncryptionService()





