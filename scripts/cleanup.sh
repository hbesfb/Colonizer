#!/bin/bash
find /app/Colonizer/flask_session -mtime +1 -exec rm -f {} \;
