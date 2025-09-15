import os
import secrets
import json
import re
from threading import Timer
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, FileSystemEventHandler

class Settings(FileSystemEventHandler):
	def __init__(self):
		self._data = {}
		self._listeners = []
		self._changed = False
		self._logger = None
		# observer for config file changes
		self._observer = Observer()
		self._observer.start()
		# timer to reload config on change
		self._reloader = None
		self._reload_delay = 0.2

	def init(self, filename: str, app = None):
		if app is not None:
			self._logger = app.logger
		self.set_path(os.path.join('./config',f'{filename}.json'))
		return self.load()

	def __getitem__(self, name: str) -> dict:
		return self._data[name]
	
	def __setitem__(self, name: str, value) -> None:
		self._data[name] = value
		self._changed = True

	def set_path(self, filepath: str):
		self._filepath = os.path.realpath(filepath)
		# monitor file for changes
		self._observer.unschedule_all()
		self._observer.schedule(self, path=os.path.dirname(self._filepath))

	@property
	def data(self):
		return self._data.copy()
	
	def _substitute_db_env_vars(self, obj):
		"""
		Recursively substitute environment variables in the format ${VAR_NAME} picked from the db dict object
		"""
		if isinstance(obj, dict):
			return {key: self._substitute_db_env_vars(value) for key, value in obj.items()}
		elif isinstance(obj, str):
		# Find all ${VAR_NAME} patterns and replace them
			def replace_env_var(match):
				env_var = match.group(1)
				env_value = os.environ.get(env_var)
				if env_value is None:
					if self._logger:
						self._logger.warning(f"Environment variable '{env_var}' not found, keeping original placeholder text value {env_var}")
					return match.group(0)  # Return original ${VAR_NAME} if not found
				return env_value
			
			# Replace ${VAR_NAME} patterns
			return re.sub(r'\$\{([^}]+)\}', replace_env_var, obj)
		else:
			return obj  # Handle any other types (numbers, booleans, etc. eg port : 8000 an integer)

	def load(self, filepath: str = ''):
		if filepath == '':
			filepath = self._filepath
		# load file
		try:
			with open(filepath,'r') as f:
				raw_data = json.load(f)

			# Substitute environment variables
			self._data = self._substitute_db_env_vars(raw_data)

			if self._logger:
				self._logger.info(f"Settings loaded from {filepath}")
			# call listeners
			for func in self._listeners: func()
			return True
		except Exception as e:
			if self._logger:
				self._logger.info(f"Error loading settings from {filepath}: {str(e)}")
			return False

	def save(self):
		# do not trigger event on this change
		self._observer.stop()
		with open(self._filepath,'w') as f:
			json.dump(self._data, f, indent=3)
		self._observer.start()
	
	def on_modified(self, event: FileSystemEvent) -> None:
		if event.src_path != self._filepath:
			return
		if type(self._reloader) is Timer:
			if self._reloader.is_alive():
				return
		self._reloader = Timer(self._reload_delay, self.load)
		self._reloader.daemon = True
		self._reloader.start()

	# Add and remove functions from the list of listeners.
	def addListener(self,func):
		if func in self._listeners: return
		self._listeners.append(func)
	def removeListener(self,func):
		if func not in self._listeners: return
		self._listeners.remove(func)

settings = Settings()

def user_validator(username, password):
	user_min = settings['general']['user_min']
	user_max = settings['general']['user_max']

	if username == 'admin':
		if password == settings['general']['adminpwd']:
			return True, ''
		else:
			return False, 'Wrong password'
	elif user_min <= len(username) <= user_max:
		return True, ''
	else:
		return False, 'Invalid username'
	
def get_secret(filename='secret.key'):
	if os.path.exists(filename):
		with open('secret.key', 'r') as f:
			key = f.readline()
	else:
		key = secrets.token_hex(16)
		with open('secret.key', 'w') as f:
			f.write(key)
	return key