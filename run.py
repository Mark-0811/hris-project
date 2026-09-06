from hris.app import create_app
from hris.app.extensions import socketio


app = create_app()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
