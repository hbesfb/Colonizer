from datetime import datetime
#from webdaemon import app
from flask import Blueprint, current_app, render_template, request, redirect,session, url_for, g
from settings import settings, user_validator

blueprint = Blueprint("users",__name__)

# Login dialog
# login check
@blueprint.before_app_request
def login_check():
	session.modified = True

	g.username = session.get('user')
	g.isAdmin = (g.username == 'admin')

	if request.path.startswith(('/status')):
		return

	if g.username is None and request.endpoint not in ['users.login', 'users.logout']:
		session['login_redirect'] = request.url
		return redirect(url_for('users.login'))
	
@blueprint.route('/login', methods=['GET', 'POST'])
def login():
	error = ''

	if g.username is not None:
		return redirect(url_for('index'))
	
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']
		valid, error = user_validator(username, password)
		if valid:
			session['user'] = username
			session['user_time'] = datetime.now()
			current_app.logger.info(f"User {session['user']} logged in")
			next_page = session.get('login_redirect', None)
			if next_page is None:
				return redirect(url_for('index'))
			else:
				session['login_redirect'] = None
				return redirect(next_page)
		else:
			current_app.logger.error(f"Wrong password for user {username}")
			session['user'] = None
	return render_template('login.html', error=error)

@blueprint.route('/logout', methods=['GET'])
def logout():
	session['user'] = None
	return redirect(url_for('users.login'))
