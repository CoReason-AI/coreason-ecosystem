# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

import os
import time
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import jwt
from coreason_ecosystem.auth.license_validator import (
    verify_token_signature,
    install_license,
    get_root_ca_key,
)


@pytest.fixture
def keypair():
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def test_verify_token_signature_valid(keypair):
    private_pem, public_pem = keypair
    old_key = os.environ.get("COREASON_ROOT_CA_KEY")
    os.environ["COREASON_ROOT_CA_KEY"] = public_pem
    try:
        payload = {
            "sub": "tenant_1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, private_pem, algorithm="EdDSA")

        decoded = verify_token_signature(token)
        assert decoded["sub"] == "tenant_1"
    finally:
        if old_key is not None:
            os.environ["COREASON_ROOT_CA_KEY"] = old_key
        else:
            del os.environ["COREASON_ROOT_CA_KEY"]


def test_verify_token_signature_invalid_key(keypair):
    private_pem, _ = keypair

    other_public_pem = (
        ed25519.Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    old_key = os.environ.get("COREASON_ROOT_CA_KEY")
    os.environ["COREASON_ROOT_CA_KEY"] = other_public_pem
    try:
        payload = {
            "sub": "tenant_1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, private_pem, algorithm="EdDSA")

        with pytest.raises(ValueError, match="Malformed or invalid token:"):
            verify_token_signature(token)
    finally:
        if old_key is not None:
            os.environ["COREASON_ROOT_CA_KEY"] = old_key
        else:
            del os.environ["COREASON_ROOT_CA_KEY"]


def test_get_root_ca_key_production_missing():
    old_env = os.environ.get("COREASON_ENV")
    old_root = os.environ.get("COREASON_ROOT_CA_KEY")
    old_dev = os.environ.get("COREASON_DEV_KEY")

    os.environ["COREASON_ENV"] = "production"
    if "COREASON_ROOT_CA_KEY" in os.environ:
        del os.environ["COREASON_ROOT_CA_KEY"]
    if "COREASON_DEV_KEY" in os.environ:
        del os.environ["COREASON_DEV_KEY"]

    try:
        with pytest.raises(
            RuntimeError, match="Root CA Key not configured. Owner Ceremony required."
        ):
            get_root_ca_key()
    finally:
        if old_env is not None:
            os.environ["COREASON_ENV"] = old_env
        elif "COREASON_ENV" in os.environ:
            del os.environ["COREASON_ENV"]
        if old_root is not None:
            os.environ["COREASON_ROOT_CA_KEY"] = old_root
        if old_dev is not None:
            os.environ["COREASON_DEV_KEY"] = old_dev


def test_install_license_production_vault_guards(keypair):
    private_pem, public_pem = keypair
    old_key = os.environ.get("COREASON_ROOT_CA_KEY")
    old_env = os.environ.get("COREASON_ENV")
    old_vault_addr = os.environ.get("VAULT_ADDR")

    os.environ["COREASON_ROOT_CA_KEY"] = public_pem
    os.environ["COREASON_ENV"] = "production"
    if "VAULT_ADDR" in os.environ:
        del os.environ["VAULT_ADDR"]

    try:
        payload = {
            "sub": "tenant_1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, private_pem, algorithm="EdDSA")

        with pytest.raises(
            ValueError,
            match="Production deployment requires valid Vault credentials and non-local Vault address.",
        ):
            install_license(token)
    finally:
        if old_key is not None:
            os.environ["COREASON_ROOT_CA_KEY"] = old_key
        elif "COREASON_ROOT_CA_KEY" in os.environ:
            del os.environ["COREASON_ROOT_CA_KEY"]

        if old_env is not None:
            os.environ["COREASON_ENV"] = old_env
        elif "COREASON_ENV" in os.environ:
            del os.environ["COREASON_ENV"]

        if old_vault_addr is not None:
            os.environ["VAULT_ADDR"] = old_vault_addr
        elif "VAULT_ADDR" in os.environ:
            del os.environ["VAULT_ADDR"]
