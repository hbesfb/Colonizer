#!/bin/bash
# Script for restarting potentially hung services/processes if watchdog is triggered

# incase visual studio code is running remotely
kill $(pidof node)
# stop services
service supervisor stop
service redis stop
# restart services
service redis start
serivce supervisor start