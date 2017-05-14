#!flask/bin/python

try:
    from flask_failsafe import failsafe
except ImportError:
    # Shadow the failsafe when Failsafe module is not available
    def failsafe(func):
        return func


# Failsafe flask instance for development
# See https://pypi.python.org/pypi/Flask-Failsafe/

@failsafe
def create_app():
    # note that the import is *inside* this function so that we can catch
    # errors that happen at import time
    from app import app
    return app

if __name__ == "__main__":
    create_app().run(debug=True, host='0.0.0.0', port=80)
