# Local dev launcher.
#
# Avast (and other AV products that scan HTTPS) replace Google's TLS
# certificate with their own. Python's ssl module trusts it via the Windows
# certificate store, but gRPC and requests ship their own CA bundles and do
# not, so Firestore calls fail with CERTIFICATE_VERIFY_FAILED.
#
# certs/windows-ca-bundle.pem is certifi plus the Windows root store. It is
# gitignored and machine-specific. Regenerate it with scripts/build_ca_bundle.py
# if the AV root changes. Nothing here ships to production — Render has no
# interception and needs none of it.

$bundle = Join-Path $PSScriptRoot "..\certs\windows-ca-bundle.pem" | Resolve-Path
$env:GRPC_DEFAULT_SSL_ROOTS_FILE_PATH = $bundle
$env:REQUESTS_CA_BUNDLE = $bundle
$env:SSL_CERT_FILE = $bundle

uvicorn src.main:app --reload --port 8000
