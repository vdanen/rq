#!/bin/sh

test() {
    cmd="${1}"
    echo ""
    echo "TESTING:: ${cmd}"
    ${cmd}
    if [ "$?" != "0" ]; then
        echo "[FAIL] SOMETHING WENT WRONG! RE-RUNNING WITH --DEBUG OPTION"
        ${cmd} --debug
        exit 1
    else
        echo "[OK]"
    fi
}

cd ..
echo "drop database rq_binary; create database rq_binary; drop database rq_source; create database rq_source;" | mysql -u rq
./create_database.py
[[ "$?" != "0" ]] && exit 1

echo "******************************************"
echo "Testing rqp"
echo "******************************************"
test "./rqp -x"
test "./rqp -C test/rpm/main -U test/rpm/updates -t test -P"
test "./rqp -x"
test "./rqp --list-to-update -t test"
test "./rqp -u test -P"
test "./rqp -x"
test "./rqp -l"

echo "******************************************"
echo "Testing rqs"
echo "******************************************"
test "./rqs -x"
test "./rqs -C test/srpm/main -U test/srpm/updates -t test -P"
test "./rqs -x"
test "./rqs --list-to-update -t test"
test "./rqs -u test -P"
test "./rqs -x"
test "./rqs -l"

