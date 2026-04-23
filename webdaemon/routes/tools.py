from flask import Blueprint, current_app, request, jsonify, session, g
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.barcodeparser import Decoder
from webdaemon.status import servicemonitor
from settings import settings

blueprint = Blueprint("tools",__name__)

@blueprint.route('/parse', methods=['POST'])
def parse_string():
	data = request.get_json(silent=True)
	if data is None:
		current_app.logger.warning("parse_string called with non-JSON or empty body")
		return jsonify({})  # as expected by the JS

	try:
		result = Decoder.parse_input(data)
	except Exception:
		current_app.logger.exception("Barcode parsing failed")
		return jsonify({})

	if result is None:
		return jsonify({})
	
	if 'batch' in result:
		session['batch'] = result['batch']

	# check if the settleplate is registered in DB
	if 'serial' in result:
		result['used'] = db.session.query(
			Settleplate.ScanDate).filter(
				Settleplate.Barcode == result['serial']).count()

	# check if there is a positive test for this lot of settleplates in the DB
	# use .get() to avoid KeyError if 'positive_test_required' is missing from config
	positive_required = settings['general'].get('positive_test_required', False)

	# When positive test is required, use lot to make batch name (ie batch_prefix+<lot>)
	if 'lot' in result and positive_required:
		try:
			batch_prefix = settings['general']['positive_test_prefix']
			positive_test_location = settings['general']['positive_test_location']

		except KeyError as e:
			current_app.logger.error(f"Positive test enabled but missing config key: {e}")
			return jsonify({'config_error': True, 'message': f'Missing configuration: {e}'})
		
		# always derive batch from lot (single source of truth)
		batchname = f"{batch_prefix}{result['lot']}"
		result['batch'] = batchname

		# Any rows with registered positive test that have been scanned:
		has_been_scanned = db.session.query(
			db.session.query(Settleplate)
			.filter(
				Settleplate.Batch == batchname,
				Settleplate.Location == positive_test_location,
				Settleplate.Counts > 0
			)
			.exists()
		).scalar()

		# Any rows of registered positive plate are pending scanning:
		has_registration_pending_scanning = db.session.query(
			db.session.query(Settleplate)
			.filter(
				Settleplate.Batch == batchname,
				Settleplate.Location == positive_test_location,
				Settleplate.Counts == -1
			)
			.exists()
		).scalar()

		# case1: plate exists and its colonies counted (scanned)
		if has_been_scanned:
			result['no_positive'] = False # Positive test exists, add field as it was in old code
			result['positive_state'] = "completed"

		# case2: plate exists but colonies not counted (pending scanning)
		elif has_registration_pending_scanning:
			result['no_positive'] = False # add field as it was in old code
			result['positive_state'] = "registered_uncounted"
		
		# if no positive test has been registered, add fields 
		# that will tell the JS which batch the current plate belongs
		# and which location to register it. Info will be used to warn the UI 
		# with "No positive test registered for this batch"
		else:
			result['no_positive'] = True # add field as it was in old code
			result['positive_state'] = "missing"
			result['no_positive_batch'] = batchname
			result['no_positive_location'] = positive_test_location

	#The case when positive test is not required ie positive_required = False
	elif 'lot' in result:
		result.setdefault('batch', result['lot'])

	return jsonify(result)

@blueprint.before_app_request
def include_status():
	g.status = servicemonitor.status