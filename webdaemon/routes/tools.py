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
	result = Decoder.parse_input(data)

	if result is None:
		return jsonify({})
	if 'batch' in result:
		session['batch'] = result['batch']
	# check if the settleplate is registered in DB
	if 'serial' in result:
		result['used'] = len(db.session.query(Settleplate.ScanDate).filter(Settleplate.Barcode.like(result['serial'])).all())
	# check if there is a positive test for this lot of settleplates in the DB
	if 'lot' in result and settings['general']['positive_test_required']:
		batchname = settings['general']['positive_test_prefix']+result['lot']
		result['no_positive'] = db.session.query(Settleplate.ScanDate).filter(
			Settleplate.Counts > 0,
			Settleplate.Batch.like(batchname)
		).first() is None
		if result['no_positive']:
			result['no_positive_batch'] = batchname
			result['no_positive_location'] = settings['general']['positive_test_location']

	return jsonify(result)

@blueprint.before_app_request
def include_status():
	g.status = servicemonitor.status