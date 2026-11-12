import base64
import hashlib
import json
import os
import platform
import subprocess
import uuid
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
import requests

LICENSE_FILE = "miras.lic"
SERVER_URL = "http://127.0.0.1:8000/activate"

# Load Client Public Key
with open("public_key.pem", "rb") as f:
    PUBLIC_KEY = serialization.load_pem_public_key(f.read())


def get_hardware_id() -> str:
    """Generates a deterministic SHA-256 fingerprint bound to the physical machine."""
    system_info = [platform.node(), platform.machine(), str(uuid.getnode())]

    # Attempt to pull motherboard/BIOS UUID on Windows or Linux
    try:
        if platform.system() == "Windows":
            cmd = 'powershell -Command "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"'
            bios_uuid = subprocess.check_output(cmd, shell=True).decode().strip()
            system_info.append(bios_uuid)
        elif platform.system() == "Linux" and os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id", "r") as f:
                system_info.append(f.read().strip())
    except Exception:
        pass

    raw_fingerprint = "|".join(system_info).encode("utf-8")
    return hashlib.sha256(raw_fingerprint).hexdigest()


def verify_local_license(current_hwid: str) -> bool:
    """Verifies miras.lic completely offline using the embedded Public Key."""
    if not os.path.exists(LICENSE_FILE):
        return False

    try:
        with open(LICENSE_FILE, "r") as f:
            lic_data = json.load(f)

        payload = lic_data["payload"]
        signature = base64.b64decode(lic_data["signature"])
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

        # 1. Verify cryptographic signature (prevents tampering/forging)
        PUBLIC_KEY.verify(signature, payload_bytes)

        # 2. Verify hardware binding (prevents copying miras.lic to another laptop)
        if payload.get("hwid") != current_hwid:
            print(
                "[SECURITY ALERT] License file belongs to a different machine!"
            )
            return False

        return True
    except (InvalidSignature, KeyError, json.JSONDecodeError):
        print("[SECURITY ALERT] Corrupted or tampered license file.")
        return False


def main():
    hwid = get_hardware_id()
    print(f"Detected Local Hardware ID: {hwid[:16]}...")

    # Step A: Attempt 100% Offline Verification First
    if verify_local_license(hwid):
        print(
            "[ACCESS GRANTED] Valid local license verified offline. Launching MIRAS..."
        )
        return

    # Step B: Prompt for One-Time Activation if no valid local license exists
    print(
        "[LOCKED] No valid local license found. One-time activation required."
    )
    user_key = input(
        "Enter Product License Key (e.g., MIRAS-2026-TEST-001): "
    ).strip()

    try:
        response = requests.post(
            SERVER_URL,
            json={"license_key": user_key, "hwid": hwid},
            timeout=5,
        )
        if response.status_code == 200:
            with open(LICENSE_FILE, "w") as f:
                json.dump(response.json(), f, indent=2)
            print(
                "[SUCCESS] Hardware authenticated and bound! Saved miras.lic locally."
            )
            print(
                "[ACCESS GRANTED] Launching MIRAS (Internet no longer required)..."
            )
        else:
            print(
                f"[ACCESS DENIED] Server rejected activation: {response.json().get('detail')}"
            )
    except requests.exceptions.RequestException:
        print(
            "[ERROR] Cannot reach activation server. Check network connection for initial setup."
        )


if __name__ == "__main__":
    main()