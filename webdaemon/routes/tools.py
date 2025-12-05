from flask import Blueprint, current_app, request, jsonify, session, g
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.barcodeparser import Decoder
from webdaemon.status import servicemonitor
from settings import settings

blueprint = Blueprint("tools",__name__)

@blueprint.route('/parse', methods=['POST'])
def parse_string():
	data = request.get_json() or {}

	current_app.logger.debug(f"Parsing input payload: {data}")
	result = Decoder.parse_input(data)
	
	if result is None:
		current_app.logger.warning("Decoder could not parse input")
		return jsonify({})
	
	# Store batch session for later use
	if 'batch' in result:
		session['batch'] = result['batch']

	# check if the settleplate is registered in DB
	if 'serial' in result:
		result['used'] = len(
			db.session.query(Settleplate.ScanDate)
			.filter(Settleplate.Barcode.like(result['serial']))
			.all()
			)
		result['used'] = db.session.query(Settleplate).filter(Settleplate.Barcode.like(result['serial'])
		).count()
		current_app.logger.debug(f"Serial {result['serial']} already used. Count: {result['used']}")
	
	# check if there is a positive test for this lot of settleplates in the DB
	if 'lot' in result and settings['general']['positive_test_required']:
		batchname = settings['general']['positive_test_prefix']+result['lot']
		result['no_positive'] = db.session.query(Settleplate.ScanDate).filter(
			#Settleplate.Lot_no == result['lot'],
			Settleplate.Batch.like(batchname),
			Settleplate.Counts > 0,
		).first() is None
		if result['no_positive']:
			result['no_positive_batch'] = batchname
			result['no_positive_location'] = settings['general']['positive_test_location']
			current_app.logger.info(
				f"No positive test found for batch {batchname} at location {result['no_positive_location']}"
			)

	return jsonify(result)

@blueprint.before_app_request
def include_status():
	g.status = servicemonitor.status