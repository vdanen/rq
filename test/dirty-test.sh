#!/bin/sh
cd ..
echo "drop database rq_binary; create database rq_binary; drop database rq_source; create database rq_source;" | mysql -u rq
./create_database.py
echo "******************************************"
echo "Testing rqp"
echo "******************************************"
./rqp -x
./rqp -C test/rpm/main -U test/rpm/updates -t test -P
./rqp -x
./rqp --list-to-update -t test
./rqp -u test -P
./rqp -x
./rqp -l
echo "******************************************"
echo "Testing rqs"
echo "******************************************"
./rqs -x
./rqs -C test/srpm/main -U test/srpm/updates -t test -P
./rqs -x
./rqs --list-to-update -t test
./rqs -u test -P
./rqs -x
./rqs -l

