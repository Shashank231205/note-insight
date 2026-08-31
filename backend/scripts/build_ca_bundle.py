"""Write certifi + the Windows root store into one PEM bundle.

Needed only on machines where an antivirus intercepts TLS: gRPC and requests
use their own bundled roots and reject the AV's substituted certificate, while
Python's ssl module accepts it from the Windows store. Combining both makes all
three agree. The output is gitignored — it describes this machine, not the app.
"""

import ssl
from pathlib import Path

import certifi

OUTPUT = Path(__file__).resolve().parent.parent / "certs" / "windows-ca-bundle.pem"


def build_bundle() -> int:
    windows_roots = [
        ssl.DER_cert_to_PEM_cert(cert) for cert, _encoding, _trust in ssl.enum_certificates("ROOT")
    ]
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(
        "\n".join([Path(certifi.where()).read_text(encoding="utf-8"), *windows_roots]),
        encoding="utf-8",
    )
    return len(windows_roots)


if __name__ == "__main__":
    count = build_bundle()
    print(f"Wrote {OUTPUT} (certifi + {count} Windows root certificates).")
