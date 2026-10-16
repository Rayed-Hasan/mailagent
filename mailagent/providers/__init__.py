"""
Email providers
"""

from mailagent.providers.base import EmailProviderInterface
from mailagent.providers.gmail_provider import GmailProvider, GmailOAuthFlow
from mailagent.providers.imap_provider import IMAPProvider

__all__ = [
    "EmailProviderInterface",
    "GmailProvider",
    "GmailOAuthFlow",
    "IMAPProvider"
]
