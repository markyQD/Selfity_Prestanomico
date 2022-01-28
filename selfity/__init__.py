from flask import Flask
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    with app.app_context():
        from selfity.routes import phone_bp
        app.register_blueprint(phone_bp)
    

    return app
    
    
    















