from flask import Flask
from app.web.views import web

def create_app():
    app = Flask(__name__)
    app.register_blueprint(web)
    return app
