from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# Generate Ed25519 keypair
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Save Private Key (Keep on Server ONLY)
with open("private_key.pem", "wb") as f:
    f.write(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

# Save Public Key (Embed in Client App)
with open("public_key.pem", "wb") as f:
    f.write(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

print("Generated private_key.pem and public_key.pem successfully.")