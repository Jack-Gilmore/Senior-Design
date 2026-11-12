import base64
from datetime import datetime, timezone
import json
import sqlite3
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="MIRAS Node-Locked Activation Server")
DB_PATH = "licenses.db"

# Load Server Private Key
with open("private_key.pem", "rb") as f:
    PRIVATE_KEY = serialization.load_pem_private_key(f.read(), password=None)


# Initialize SQLite Database and Seed a Test Key
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS licenses (
                                                           license_key TEXT PRIMARY KEY,
                                                           bound_hwid TEXT,
                                                           status TEXT DEFAULT 'ACTIVE',
                                                           activated_at TEXT
                   )
                   """)
    # Insert a sample valid key for testing
    cursor.execute(
        """
        INSERT OR IGNORE INTO licenses (license_key, bound_hwid, status)
        VALUES ('MIRAS-2026-TEST-001', NULL, 'ACTIVE')
        """
    )
    conn.commit()
    conn.close()


init_db()


class ActivationRequest(BaseModel):
    license_key: str
    hwid: str


@app.post("/activate")
def activate_license(req: ActivationRequest):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT bound_hwid, status FROM licenses WHERE license_key = ?",
        (req.license_key,),
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid license key.")

    bound_hwid, status = row

    if status != "ACTIVE":
        conn.close()
        raise HTTPException(
            status_code=403, detail="License key has been revoked."
        )

    # Case 1: Key has never been activated -> Bind it to this Hardware ID
    if bound_hwid is None:
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE licenses SET bound_hwid = ?, activated_at = ? WHERE license_key = ?",
            (req.hwid, now, req.license_key),
        )
        conn.commit()
        bound_hwid = req.hwid
        print(f"[SERVER] Key {req.license_key} newly bound to HWID: {req.hwid}")

    # Case 2: Key is already bound to a DIFFERENT machine -> Reject
    elif bound_hwid != req.hwid:
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="License key is already bound to another hardware device.",
        )

    conn.close()

    # Construct and cryptographically sign the offline .lic payload
    license_payload = {
        "license_key": req.license_key,
        "hwid": bound_hwid,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(license_payload, sort_keys=True).encode("utf-8")
    signature = PRIVATE_KEY.sign(payload_bytes)

    return {
        "payload": license_payload,
        "signature": base64.b64encode(signature).decode("utf-8"),
    }