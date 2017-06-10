import os

VERSION = '1.0'

BASEDIR = os.path.abspath(os.path.dirname(__file__))

# if our local override exists, set the environment to load it
if os.path.isfile(BASEDIR + '/local.cfg'):
    os.environ['LOCALCONFIG'] = BASEDIR + '/local.cfg'

USERHOME = '/home/vagrant'
HOMEDIR = '/srv/www/rq'
DATADIR = '%s/flask/data' % HOMEDIR

# read the ~/.my.cnf to get our password
with open(USERHOME + '/.my.cnf') as f:
    content = [x.strip('\n') for x in f.readlines()]
for line in content:
    if line.startswith('password'):
        if '"' in line:
            DB_PASS = line.split('=')[1].split('"')[1]
        else:
            DB_PASS = line.split('=')[1]

#
# production defaults; override using local.cfg
#
#
# database settings
DB_HOST  = 'localhost'
DB_USER  = 'rq'
DB_RPMS  = 'rq_binary'
DB_SRPMS = 'rq_source'
DB_PORT  = '3306'
RPM_URI  = 'mysql://%s:%s@%s:%s/%s' % (DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_RPMS)
SRPM_URI = 'mysql://%s:%s@%s:%s/%s' % (DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_SRPMS)

PRODUCTION = True

WTF_CSRF_ENABLED = True
SECRET_KEY = '116a99d7daf243dfe5b6600be2485257632d055de7daae01cbf6b2cd2bf75b87'

del os

