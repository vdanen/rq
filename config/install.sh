#!/bin/sh -x
if [ "$(/usr/bin/whoami)" != 'root' ]; then
    echo "This script must be executed as root"
    exit 1
fi

cp -f rq.service /etc/systemd/system/
cp -f rq.socket /etc/systemd/system/
cp -f tmpfiles.d-rq.conf /etc/tmpfiles.d/

systemd-tmpfiles --create
systemctl enable rq.service
systemctl enable rq.socket

if [ "$(hostname)" == "localhost.localdomain" ]; then
    ln -s httpd.conf /etc/httpd/conf.d/00_rq.conf
else
    cp -f httpd-production.conf /etc/apache2/conf.d/userdata/ssl/2_4/rq/rq.annvix.ca/flask.conf
fi

if [ "$(grep -q rq /etc/crontab >/dev/null 2>&1; echo $?)" == "1" ]; then
#    cat cron >>/etc/crontab
    echo "Be sure to update /etc/crontab!"
fi

