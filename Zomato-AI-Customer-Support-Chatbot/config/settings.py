import os
from pathlib import Path
from dotenv import load_dotenv
import socket

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")
# Force Python socket layer to IPv4 only across all libraries
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_getaddrinfo

class Settings:
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "avnadmin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "zomato_support")
    
    DB_SSL_CA: Path = BASE_DIR / os.getenv("DB_SSL_CA", "certs/ca.pem")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-3.8-flash")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.DB_PASSWORD:
            missing.append("DB_PASSWORD")
        if not cls.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not cls.DB_SSL_CA.exists():
            missing.append(f"SSL CA file missing at: {cls.DB_SSL_CA}")
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

settings = Settings()