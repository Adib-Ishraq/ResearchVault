"""
Flask application factory for Research Vault.
"""

from flask import Flask
from flask_cors import CORS

from config import Config
from crypto.key_manager import ServerMasterKeys, init_master_keys
from crypto.rsa_engine import deserialize_public_key, deserialize_private_key
from crypto.ecc_engine import deserialize_ecc_public_key, deserialize_ecc_private_key


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # CORS — allow the Vite frontend dev server and production domain
    CORS(app, origins=[app.config["FRONTEND_URL"]], supports_credentials=True)

    # Initialize server master keys from environment
    master = ServerMasterKeys(
        rsa_pub=deserialize_public_key(app.config["SERVER_RSA_MASTER_PUBLIC_KEY"]),
        rsa_priv=deserialize_private_key(app.config["SERVER_RSA_MASTER_PRIVATE_KEY"]),
        ecc_pub=deserialize_ecc_public_key(app.config["SERVER_ECC_MASTER_PUBLIC_KEY"]),
        ecc_priv=deserialize_ecc_private_key(app.config["SERVER_ECC_MASTER_PRIVATE_KEY"]),
    )
    init_master_keys(master)

    # Register blueprints
    from modules.auth.routes import auth_bp
    from modules.users.routes import users_bp
    from modules.search.routes import search_bp
    from modules.rooms.routes import rooms_bp
    from modules.notifications.routes import notifications_bp
    from modules.messages.routes import messages_bp
    from modules.ai.routes import ai_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.register_blueprint(rooms_bp, url_prefix="/api/rooms")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(messages_bp, url_prefix="/api/messages")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
