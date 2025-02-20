from webdaemon import app
from flask import render_template, redirect, url_for, g
from sqlalchemy.exc import SQLAlchemyError
from settings import settings

from . import admin
from . import edit
from . import images
from . import list
from . import register
from . import scan
from . import tools
from . import users
from . import hiscore
from . import hive

app.register_blueprint(admin.blueprint)
app.register_blueprint(edit.blueprint)
app.register_blueprint(images.blueprint)
app.register_blueprint(list.blueprint)
app.register_blueprint(register.blueprint)
app.register_blueprint(scan.blueprint)
app.register_blueprint(tools.blueprint)
app.register_blueprint(users.blueprint)
app.register_blueprint(hiscore.blueprint)
app.register_blueprint(hive.blueprint)

# error handler for SQL errors:
@app.errorhandler(SQLAlchemyError)
def sqlerror(e):
	return render_template('sqlerror.html', error=e)

# default page
@app.route('/')
def index():
	return redirect(url_for('list.settleplates'))

# 404 not found
@app.errorhandler(404)
def page_not_found(e):
	# note that we set the 404 status explicitly
	return render_template('404.html'), 404

# test server
@app.before_request
def test_server_check():
	g.testserver = settings['general']['testserver']