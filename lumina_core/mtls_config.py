"""mTLS / TLS material loader for Fabric gRPC and future HTTP (v51 / ADR-0042).

Localhost Fabric remains insecure channel by default (ADR-0035).
Remote multi-host requires:
  LUMINA_FABRIC_TLS_CA
  LUMINA_FABRIC_TLS_CERT (client)
  LUMINA_FABRIC_TLS_KEY  (client)
  optional LUMINA_FABRIC_TLS_SERVER_NAME
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FabricTlsMaterial:
    ca_cert_path: Path
    client_cert_path: Path | None
    client_key_path: Path | None
    server_name: str

    @property
    def mutual(self) -> bool:
        return bool(self.client_cert_path and self.client_key_path)


def fabric_tls_configured() -> bool:
    return bool(str(os.getenv("LUMINA_FABRIC_TLS_CA", "") or "").strip())


def load_fabric_tls_material() -> FabricTlsMaterial | None:
    ca = str(os.getenv("LUMINA_FABRIC_TLS_CA", "") or "").strip()
    if not ca:
        return None
    ca_path = Path(ca)
    if not ca_path.is_file():
        raise RuntimeError(f"LUMINA_FABRIC_TLS_CA not found: {ca_path}")
    cert = str(os.getenv("LUMINA_FABRIC_TLS_CERT", "") or "").strip()
    key = str(os.getenv("LUMINA_FABRIC_TLS_KEY", "") or "").strip()
    cert_path = Path(cert) if cert else None
    key_path = Path(key) if key else None
    if cert_path is not None and not cert_path.is_file():
        raise RuntimeError(f"LUMINA_FABRIC_TLS_CERT not found: {cert_path}")
    if key_path is not None and not key_path.is_file():
        raise RuntimeError(f"LUMINA_FABRIC_TLS_KEY not found: {key_path}")
    if (cert_path is None) ^ (key_path is None):
        raise RuntimeError("Set both LUMINA_FABRIC_TLS_CERT and LUMINA_FABRIC_TLS_KEY for mTLS")
    server_name = str(os.getenv("LUMINA_FABRIC_TLS_SERVER_NAME", "") or "localhost").strip()
    return FabricTlsMaterial(
        ca_cert_path=ca_path,
        client_cert_path=cert_path,
        client_key_path=key_path,
        server_name=server_name,
    )


def build_grpc_channel(target: str, *, options: list[tuple[str, Any]] | None = None) -> Any:
    """Build insecure (default) or TLS/mTLS gRPC channel."""
    import grpc

    opts = list(options or [])
    material = load_fabric_tls_material()
    if material is None:
        return grpc.insecure_channel(target, options=opts)

    root = material.ca_cert_path.read_bytes()
    private_key = None
    certificate_chain = None
    if material.mutual:
        assert material.client_key_path is not None
        assert material.client_cert_path is not None
        private_key = material.client_key_path.read_bytes()
        certificate_chain = material.client_cert_path.read_bytes()
    creds = grpc.ssl_channel_credentials(
        root_certificates=root,
        private_key=private_key,
        certificate_chain=certificate_chain,
    )
    # Override SSL target name when connecting via IP.
    opts = opts + [("grpc.ssl_target_name_override", material.server_name)]
    logger.info(
        "fabric.grpc TLS channel target=%s mutual=%s server_name=%s",
        target,
        material.mutual,
        material.server_name,
    )
    return grpc.secure_channel(target, creds, options=opts)
