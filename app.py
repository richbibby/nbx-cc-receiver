import os, hmac, hashlib, logging, requests
from flask import Flask, request, abort

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- Config from env ---
CC_HOST         = os.environ["CC_HOST"].rstrip("/")
CC_USER         = os.environ["CC_USER"]
CC_PASS         = os.environ["CC_PASS"]
NB_SECRET       = os.environ.get("NB_SECRET", "")
VERIFY_TLS      = os.environ.get("VERIFY_TLS", "true").lower() == "true"
DEPLOYMENT_MODE = os.environ.get("DEPLOYMENT_MODE", "Deploy")   # or "Preview"
INTERFACE_PATH  = os.environ.get("INTERFACE_PATH", "generic")    # "generic" or "wireless"

def verify_hmac(raw_body: bytes, signature: str | None) -> bool:
    """Verify NetBox's X-Hook-Signature (HMAC-SHA512). If NB_SECRET is empty, accept all."""
    if not NB_SECRET:
        return True
    digest = hmac.new(NB_SECRET.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature or "")

def catalyst_token() -> str:
    """Obtain an X-Auth-Token from Catalyst Center."""
    url = f"{CC_HOST}/dna/system/api/v1/auth/token"
    r = requests.post(url, auth=(CC_USER, CC_PASS), timeout=15, verify=VERIFY_TLS)
    r.raise_for_status()
    return r.json()["Token"]

def build_update_url(if_uuid: str) -> str:
    """Choose the correct update path based on INTERFACE_PATH."""
    if INTERFACE_PATH == "wireless":
        return f"{CC_HOST}/dna/intent/api/v1/wirelessSettings/interfaces/{if_uuid}"
    # default: generic
    return f"{CC_HOST}/dna/intent/api/v1/interface/{if_uuid}"

def extract_uuid_and_desc(payload: dict) -> tuple[str | None, str | None]:
    """
    Be tolerant of different NetBox webhook shapes.
    Prefer current object under payload['data'], but also check 'post' and 'object'.
    """
    iface_uuid = None
    desc = None

    # 1) Common modern shape: payload['data'] is the current object
    d = payload.get("data") or {}
    if isinstance(d, dict) and d:
        cf = d.get("custom_fields") or {}
        desc = d.get("description", desc)
        iface_uuid = cf.get("catalyst_interface_uuid", iface_uuid)

    # 2) Some payloads include a nested 'post' (after state)
    post = d.get("post") if isinstance(d, dict) else None
    if not post:
        post = payload.get("post")  # fallback if top-level 'post'
    if isinstance(post, dict) and post:
        cf2 = post.get("custom_fields") or {}
        if desc is None:
            desc = post.get("description")
        if iface_uuid is None:
            iface_uuid = cf2.get("catalyst_interface_uuid")

    # 3) Rare older/custom shape: top-level 'object'
    obj = payload.get("object")
    if isinstance(obj, dict) and obj:
        cf3 = obj.get("custom_fields") or {}
        if desc is None:
            desc = obj.get("description")
        if iface_uuid is None:
            iface_uuid = cf3.get("catalyst_interface_uuid")

    return iface_uuid, desc

@app.post("/netbox/interface-updated")
def handle_nbx():
    raw = request.get_data()

    # Verify signature (if configured)
    if not verify_hmac(raw, request.headers.get("X-Hook-Signature")):
        abort(401, "Bad signature")

    payload = request.get_json(force=True)
    iface_uuid, desc = extract_uuid_and_desc(payload)

    app.logger.info("Parsed webhook; uuid=%s, desc=%s", iface_uuid, desc)

    # Safety: only act when we have what we need
    if not iface_uuid or desc is None:
        # Helpful debug so we can tune the extractor if needed
        data_keys = list((payload.get("data") or {}).keys()) if isinstance(payload.get("data"), dict) else type(payload.get("data")).__name__
        app.logger.info("No-op: missing uuid/desc. Top-level keys: %s ; data keys: %s",
                        list(payload.keys()), data_keys)
        return ("no-op", 204)

    # Build target URL
    url = build_update_url(iface_uuid)
    if DEPLOYMENT_MODE:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}deploymentMode={DEPLOYMENT_MODE}"

    # Auth + update
    token = catalyst_token()
    body = {"description": desc}

    r = requests.put(
        url,
        json=body,
        headers={"X-Auth-Token": token, "Content-Type": "application/json"},
        timeout=20,
        verify=VERIFY_TLS
    )

    app.logger.info("Catalyst PUT %s -> %s %s", url, r.status_code, r.text[:400])

    # Return 200 OK to NetBox so it doesn't retry; we log Catalyst response separately.
    return (str(r.status_code), 200)

@app.get("/healthz")
def health():
    return "ok", 200

@app.get("/")
def root():
    return "NetBox → Catalyst Center receiver is running. Try /healthz", 200

if __name__ == "__main__":
    # Default to 5100 to avoid conflicts on macOS
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5100")))
