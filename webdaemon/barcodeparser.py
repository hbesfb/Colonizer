import re
from datetime import datetime
from settings import settings

class _BarcodeParser():

	def __init__(self, parent = None):
		# setup logging
		#self.logger = generate_logger("DAEMON")
		# compile regexp
		self.regex_patterns = []
		self.update_regexp()
		self.string_pattern = re.compile(r"[^\w:\-_]")
		settings.addListener(self.update_regexp)

	def update_regexp(self):
		self.regex_patterns.clear()
		for pattern in ['user', 'batch', 'location', 'settleplate']:
			for regex in settings['regex'][pattern]:
				#self.logger.debug("Compiling {p}: r'{r}'".format(p=pattern,r=regex))
				self.regex_patterns.append(re.compile(regex))

	def parse_input(self, text):
		# clean text
		text = self.string_pattern.sub('', text)
		params = None
		for pattern in self.regex_patterns:
			result = pattern.search(text)
			if(result):
				params = result.groupdict()
				#self.logger.debug('Scanned: %s '%params)
				break

		# if no match, ignore text
		if not params:
			#self.logger.error('Not recognized: "%s"'%text)
			return None
		# process expire date
		if all([k in params for k in ['year', 'month', 'day']]):
			if len(params['year']) == 2:
				params['year'] = '20' + params['year']
			params['expire'] = datetime(int(params['year']), int(params['month']), int(params['day']))
		# return result
		return params

Decoder = _BarcodeParser()