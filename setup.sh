#!/bin/sh
exit=0
for app in pip3 virtualenv; do # mysql_config; do
    if [ "$(which ${app} >/dev/null 2>&1; echo $?)" == "1" ]; then
        echo "Unable to find ${app} which is required!"
        exit=1
    fi
done

if [ ${exit} -eq 1 ]; then
    exit 1
fi

virtualenv flask
flask/bin/pip install -r requirements.txt
flask/bin/pip install mysql-python

