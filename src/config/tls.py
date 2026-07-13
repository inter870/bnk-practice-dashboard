from __future__ import annotations

import hashlib
import os
import ssl
import tempfile
from pathlib import Path
from typing import MutableMapping

import requests


SERVER_AUTH_OID = "1.3.6.1.5.5.7.3.1"


def build_windows_ca_bundle(target_dir: str | Path | None = None) -> str | None:
    """Combine Requests' CA bundle with Windows certificates trusted for TLS."""
    if os.name != "nt" or not hasattr(ssl, "enum_certificates"):
        return None

    certificates: list[str] = []
    try:
        for store_name in ("ROOT", "CA"):
            for certificate, encoding, trust in ssl.enum_certificates(store_name):
                if encoding != "x509_asn":
                    continue
                if trust is not True and SERVER_AUTH_OID not in trust:
                    continue
                certificates.append(ssl.DER_cert_to_PEM_cert(certificate))
    except (OSError, ssl.SSLError):
        return None

    unique_certificates = list(dict.fromkeys(certificates))
    if not unique_certificates:
        return None

    try:
        base_bundle = Path(requests.certs.where()).read_text(encoding="ascii")
        combined_bundle = base_bundle.rstrip() + "\n" + "\n".join(unique_certificates)
        bundle_hash = hashlib.sha256(combined_bundle.encode("ascii")).hexdigest()[:16]
        output_dir = Path(target_dir or tempfile.gettempdir()) / "stance_stock_strategy"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"windows-ca-{bundle_hash}.pem"
        if not output_path.exists():
            output_path.write_text(combined_bundle, encoding="ascii")
        return str(output_path)
    except (OSError, UnicodeError):
        return None


def configure_requests_ca_bundle(
    explicit_bundle: str | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> str | None:
    """Configure Requests without replacing a deployment-provided CA setting."""
    env = environ if environ is not None else os.environ
    injected_bundle = str(env.get("REQUESTS_CA_BUNDLE") or "").strip()
    if injected_bundle:
        return injected_bundle

    configured_bundle = str(explicit_bundle or "").strip()
    if configured_bundle:
        env["REQUESTS_CA_BUNDLE"] = configured_bundle
        return configured_bundle

    windows_bundle = build_windows_ca_bundle()
    if windows_bundle:
        env["REQUESTS_CA_BUNDLE"] = windows_bundle
    return windows_bundle
