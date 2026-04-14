from flask import Blueprint, current_app, render_template, request, jsonify, g
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.barcodeparser import Decoder

blueprint = Blueprint("register",__name__,url_prefix="/settleplate")

@blueprint.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'GET':
		return render_template('register.html')

	data = request.get_json()

	# data contains 'serial' because frontend always sends it, but it could be invalid.
	parsed = Decoder.parse_input(data.get('serial'))
	if parsed is None:
		return jsonify({'committed': False, 'reason': 'invalid_barcode'})

	# Merge parsed data into original data dictionary
	data.update(parsed)

	# Check the presence of required fields
	required = ['batch', 'serial', 'location']
	missing = [k for k in required if k not in data]
	if missing:
		current_app.logger.warning(f"Missing required fields: {missing}")
		return jsonify({'committed': False, 'reason': 'missing_required_fields'})

	# Duplicate registration check: Check for an existing registration row (Counts = -1)
	existing = (
		db.session.query(Settleplate)
		.filter_by(Barcode=data['serial'], Counts=-1)
		.first()
	)
	if existing:
		return jsonify({'committed': False, 'reason': 'duplicate_barcode'})

	# Create new registration row in DB
	new_sp = Settleplate()
	new_sp.Username = g.username
	new_sp.Batch = data['batch']
	new_sp.Barcode = data['serial']
	new_sp.Location = data['location']
	if 'lot' in data:
		new_sp.Lot_no = data['lot']
	if 'expire' in data:
		new_sp.Expires = data['expire']
	new_sp.Counts = -1
	db.session.add(new_sp)
	try:
		db.session.commit()
	except Exception as e:
		db.session.rollback() 
		current_app.logger.exception("Unexpected error during commit")
		return jsonify({'committed': False, 'reason': 'unexpected_error'})

	current_app.logger.info(f"User {g.username} registered settleplate : {new_sp.ID}")
	return jsonify({'committed':True}) # this always returns HTTP 200

@blueprint.route('/batch_bydate', methods=(['POST']))
def batch_bydate():
	data = request.get_json()
	batch_id = data['batch']
	if len(batch_id):
		limit=25
		results = db.session.query(Settleplate.ScanDate, Settleplate.Barcode, Settleplate.Location).filter(Settleplate.Batch.like(batch_id)).order_by(Settleplate.ScanDate.desc()).limit(limit).all()
		response = [{'ScanDate':sp.ScanDate.strftime("%Y-%m-%d %H:%M"),'Barcode':sp.Barcode,'Location':sp.Location} for sp in results]
		return jsonify(response)
	return jsonify([])