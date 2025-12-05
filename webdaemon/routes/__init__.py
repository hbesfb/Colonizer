from webdaemon import app, __version__
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

# -------------------------------
# Register blueprints
# -------------------------------
blueprints = [
	admin,
	edit,
	images,
	list,
	register,
	scan,
	tools,
	users,
	hiscore,
	hive,
]

for bp in blueprints:
	app.register_blueprint(bp.blueprint)

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

# some variables used when rendering
@app.before_request
def pre_checks():
	g.testserver = settings['general']['testserver']
	g.timeout = settings['general']['timeout']
	g.version = __version__