"""qwatch Python SDK v0.4（生产安全：构造/调用不阻塞）。"""

from .client import AuthError, Qwatch, QwatchError

__all__ = ["Qwatch", "QwatchError", "AuthError"]
__version__ = "0.4.0"
