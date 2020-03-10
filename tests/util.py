"""Utility functions for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from jwt_authorizer.app import create_app

if TYPE_CHECKING:
    from flask import Flask
    from typing import Any


class RSAKeyPair:
    """An autogenerated public/private key pair."""

    def __init__(self) -> None:
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

    def private_key_as_pem(self) -> bytes:
        return self.private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )

    def public_key_as_pem(self) -> bytes:
        return self.private_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
        )


def create_test_app(**kwargs: Any) -> Flask:
    """Configured Flask app for testing."""
    app = create_app(FORCE_ENV_FOR_DYNACONF="testing", **kwargs)
    return app
