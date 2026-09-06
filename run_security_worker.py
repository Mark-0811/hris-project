from hris.app import create_app
from hris.app.security.worker import run_security_worker


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        run_security_worker()
