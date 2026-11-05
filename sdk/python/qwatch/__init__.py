"""qwatch Python SDK v0.6（生产安全：构造/调用不阻塞；equity/nav 写入所属策略）。"""

from .client import AuthError, Qwatch, QwatchError

__all__ = ["Qwatch", "QwatchError", "AuthError"]
__version__ = "0.6.0"
