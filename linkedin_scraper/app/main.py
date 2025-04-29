# app/main.py

from flask import Flask
from app.web.views import web

def create_app():
    app = Flask(__name__)
    app.register_blueprint(web)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
