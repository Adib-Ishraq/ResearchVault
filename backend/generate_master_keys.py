"""
Run once to generate server master RSA + ECC keypairs.
Output can be pasted directly into your .env file.

Usage:
    cd backend
    python generate_master_keys.py
"""

from crypto.key_manager import ServerMasterKeys

if __name__ == "__main__":
    print("Generating server master keys (RSA-2048 + ECC P-256)...")
    print("This may take 10–30 seconds for RSA key generation.\n")
    master = ServerMasterKeys.generate_new()
    env_vars = master.export_env_vars()
    print("# Add these to your backend/.env file:\n")
    for key, value in env_vars.items():
        print(f"{key}={value}")
