#!/usr/bin/env python3
import os
import logging
from redis import Redis
from flask import Flask
from flask_session import Session
from settings import settings, get_secret
from .status import servicemonitor
from webdaemon.database import init_database, create_database
from webdaemon.version import __version__
import hwlayer.client as hwclient

# create flask app
app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.logger.info(f'Starting Colonizer v{__version__}')

# load settings
config_file = os.environ.get('SETTLEPLATE_CONFIG','default')
if not settings.init(config_file, app):
	exit(1)

# config
app.config['SECRET_KEY'] = get_secret(),
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False,
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Enable session
app.logger.info('Setting up local session storage...')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = Redis(host='localhost', port=6379)
app.config['SESSION_COOKIE_SAMESITE'] = "Strict"
app.config['SESSION_COOKIE_NAME'] = 'Colonizer-App'
app.config['PERMANENT_SESSION_LIFETIME'] = settings['general']['timeout']
Session(app)

# initialize database
init_database(app)
#create_database(app)

# initialize camera
app.logger.info('Connecting to RPI HW server...')
hwclient.start_socket('localhost')

app.logger.info('Setting up routes...')

# init service checker
servicemonitor.init(app)

import webdaemon.routes
