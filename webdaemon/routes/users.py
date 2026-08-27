from datetime import datetime
#from webdaemon import app
from flask import Blueprint, current_app, render_template, request, redirect,session, url_for, g
from settings import settings
import requests

blueprint = Blueprint("users",__name__)

# new function replacing user_validator
def authsrv_login(username, password):
	"""
	Authenticate against internal sfb service authsrv
	Returns (True, data) on success, (False, error_message) on failure.
	"""
	try:
		response = requests.post(
			settings['authsrv']['url'],
			json={"username": username, "password": password},
			timeout=5
		)

		# Wrong credentials → 401 with JSON error
		if response.status_code != 200:
			try:
				err = response.json().get("message", "Login failed")
			except:
				err = "Login failed"
			return False, err

		data = response.json()

		access_token = data.get("access_token")
		if not access_token:
			return False, "authsrv returned no access_token"
		return True, data

	except Exception as e:
		return False, str(e)

def local_admin_login(username, password):
	"""
	Authenticate the local admin account password against
	settings['general']['adminpwd'], this matches the original user_validator behavior.
	Returns (True, {}) on success, (False, error_message) on failure.
	"""
	if password == settings['general']['adminpwd']:
		return True, {}
	else:
		return False, 'Wrong password for user admin'

# login check
@blueprint.before_app_request
def login_check():
	session.modified = True

	g.username = session.get('user')
	g.isAdmin = g.username in settings['users']

	# Allow requests for static files and status/health/ready endpoints to skip login check
	if request.path.startswith(("/status", "/health", "/ready", "/static/")):
		return

	if g.username is None and request.endpoint not in ['users.login', 'users.logout']:
		session['login_redirect'] = request.url
		return redirect(url_for('users.login'))

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
	error = ''

	if g.username is not None:
		return redirect(url_for('index'))

	# Replaced local user_validator with authsrv_login()
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']

		# Local admin account bypasses authsrv entirely
		if username == 'admin':
			valid, result = local_admin_login(username, password)
		else:
			valid, result = authsrv_login(username, password)

		if valid:
			# Store username + token in session
			session['user'] = username
			session['token'] = result.get('access_token') # note for admin token is None (no authsrv token issued)
			session['user_time'] = datetime.now()

			current_app.logger.info(f"User {session['user']} logged in via {'local admin' if username == 'admin' else 'authsrv'}")

			next_page = session.get('login_redirect', None)
			if next_page is None:
				return redirect(url_for('index'))
			else:
				session['login_redirect'] = None
				return redirect(next_page)
		else:
			current_app.logger.error(f"authsrv rejected login for user {username}")
			session['user'] = None

			# assign login error message
			if isinstance(result, str):
				error = result
			else:
				error = result.get("message", "Login failed")

	# Always return template for GET or failed POST
	return render_template('login.html', error=error)

@blueprint.route('/logout', methods=['GET'])
def logout():
	session['user'] = None
	return redirect(url_for('users.login'))
