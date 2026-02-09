from flask import Blueprint, current_app, request, jsonify, session, g
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.barcodeparser import Decoder
from webdaemon.status import servicemonitor
from settings import settings

blueprint = Blueprint("tools",__name__)

@blueprint.route('/parse', methods=['POST'])
def parse_string():
	data = request.get_json()
	try:
		result = Decoder.parse_input(data)
	except Exception:
		return jsonify({}) # will be treated as invalid barcode by JS frontend

	if result is None: # Input did not match any regex, will be treated as invalid barcode by JS frontend
		return jsonify({})

	if 'batch' in result:
		session['batch'] = result['batch']
	
	# Add number of times this serial has been used ie check if the settleplate is registered in DB
	if 'serial' in result:
		result['used'] = len(db.session.query(Settleplate.ScanDate).filter(Settleplate.Barcode.like(result['serial'])).all())

	# check if there is a positive test for this lot of settleplates in the DB
	# If the setting is missing 'positive_test_required', we explicitly treat it as disabled (False).
	positive_required = settings['general'].get('positive_test_required', False)

	if 'lot' in result and positive_required:
		try:
			batch_prefix = settings['general']['positive_test_prefix']
			positive_test_location = settings['general']['positive_test_location']
		except KeyError as e:
			current_app.logger.error(
				f"Positive test enabled but missing config key: {e}"
			)
			# Return error in same format as register endpoint
			return jsonify({
				'config_error': True,
				'message': f'Missing configuration: {e}'
			})
	
		batchname = batch_prefix+result['lot']

		# determine positive test state by location not by counts
		positive_plate = db.session.query(Settleplate).filter(
			Settleplate.Batch == batchname,
			Settleplate.Location == positive_test_location
		).first()

		if positive_plate is None:
				result['positive_state'] = "missing" # No positive plate registered yet
				result['no_positive_batch'] = batchname
				result['no_positive_location'] = positive_test_location

		elif positive_plate.Counts == -1: # Positive plate exists but has not been counted yet
			result['positive_state'] = "registered_uncounted"
			result['batch'] = batchname

		else:
			result['positive_state'] = "completed" # Positive plate exists and has been counted
	
	# Handle the case of when 'positive_test_required' = false, set batch from 'lot'
	elif 'lot' in result:
		result['batch'] = result['lot']

	return jsonify(result)

@blueprint.before_app_request
def include_status():
	g.status = servicemonitor.status