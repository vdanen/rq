from flask import Flask, session, g, render_template, request
import datetime
import os

app = Flask(__name__)
app.config.from_object('config')
if 'LOCALCONFIG' in os.environ:
    app.config.from_envvar('LOCALCONFIG')

# strip whitespace from template output
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

RPM_URI  = app.config['RPM_URI']
SRPM_URI = app.config['SRPM_URI']
DATADIR  = app.config['DATADIR']


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.after_request
def after_request(response):
    g.db.close()
    return response


from app.models import rpm_db, srpm_db
#from app import views


@app.before_request
def before_request():
    g.VERSION = app.config['VERSION']
    g.db = database
    g.db.connect()

    g.year = datetime.datetime.now().strftime('%Y')
