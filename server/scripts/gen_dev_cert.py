"""Generate a self-signed TLS certificate for the laptop MEC (dev only).

  python scripts/gen_dev_cert.py 192.168.1.20        (your laptop's Wi-Fi IP)

Writes data/tls/cert.pem and data/tls/key.pem. The Android app pins this
certificate, so regenerate it only when the laptop's IP changes, and copy
the new cert.pem into the app afterwards.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.settings import Settings  # noqa: E402


def main(ips: list[str]) -> None:
    out = Settings.from_env().data_dir / "tls"
    out.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "attendance-mec.local")])
    sans: list[x509.GeneralName] = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    sans += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    (out / "key.pem").write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (out / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Wrote {out / 'cert.pem'} and {out / 'key.pem'} for: localhost, 127.0.0.1, {', '.join(ips) or '-'}")


if __name__ == "__main__":
    main(sys.argv[1:])
