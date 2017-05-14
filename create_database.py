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
def create_tables():
    # note that the import is *inside* this function so that we can catch
    # errors that happen at import time
    from app import app
    from app import models
    models.create_tables()
#    models.Role.create(name='admin',description='Administrator')
#    models.Role.create(name='editor',description='Editor')
    #models.UserRoles.create(user=1,role=1)
    #models.UserRoles.create(user=1,role=2)

    print('Successfully initialized database')
    return app

if __name__ == "__main__":
    create_tables()

