from flask import Blueprint, current_app, render_template, request, jsonify, g
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.barcodeparser import Decoder
from settings import settings

blueprint = Blueprint("register",__name__,url_prefix="/settleplate")

@blueprint.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'GET':
		return render_template('register.html')

	data = request.get_json(silent=True) # return None if parsing fails
	if not data: # Gaurd against missing or malformed JSON body
		return jsonify({'committed': False, 'reason': 'invalid or missing JSON body in request'}), 400

	#guard against missing 'serial' key before calling parser
	if 'serial' not in data:
		return jsonify({'error': 'Missing required field: serial'}), 400
	
	# use a try exccept and return JSON error when barcode is invalid
	try:
		parsedSerial = Decoder.parse_input(data['serial'])
	except Exception:
		current_app.logger.exception("Barcode parse error during registration")
		return jsonify({'committed': False, 'error': 'invalid serial barcode'}), 400
	
	# reject invalid parse results
	if not parsedSerial:
		return jsonify({'committed': False, 'error': 'invalid serial barcode'}), 400

	# Add parsed barcode fields into the client JSON; parsed values replace any overlapping client fields
	data.update(parsedSerial)

	# For positive tests, derive batch from lot ( using this as source of truth)
	positive_required = settings['general'].get('positive_test_required', False)
	if 'lot' in parsedSerial and positive_required:
		try:
			batch_prefix = settings['general']['positive_test_prefix']
		except Exception as e:
			current_app.logger.error(f"Positive test enabled but missing config key: {e}")
			return jsonify({'config_error': True, 'message': f'Missing configuration: {e}'}), 400

		# validate batch is not mismatch (detect frontend bugs) #TODO remove once we see that all works well
		expected_batch = f"{batch_prefix}{parsedSerial['lot']}"
		if 'batch' in data and data['batch'] != expected_batch:
			current_app.logger.warning(f"Batch mismatch! received={data['batch']} expected={expected_batch}")
			return jsonify({'error': 'Batch/Lot mismatch', 'expected': expected_batch, 'received': data['batch']}), 400
		
		# force correct batch
		data['batch'] = expected_batch

	# Check the presence of required fields
	required = ['batch', 'serial', 'location']
	missing = [k for k in required if k not in data]
	if missing:
		current_app.logger.warning(f"Missing required fields: {missing}")
		return jsonify({'committed': False, 'reason':  f"Missing required fields: {', '.join(missing)}"}), 400

	#TODO: find out if we want to allow registering expired plates
	# if 'expire' in data and data['expire'] < datetime.utcnow():
	# 	return jsonify({'committed': False, 'reason': 'expired_plate'}), 400

	# check duplicate barcode on server-side (not just UI alone)
	existing_barcode = db.session.query(Settleplate.ID).filter(
		Settleplate.Barcode == data['serial']
	).first()
	if existing_barcode:
		return jsonify({'error': 'Settleplate barcode already registered'}), 409 # conflict

	# check for duplicate locations in same batch on server-side (not just client-side only)
	existing_location = db.session.query(Settleplate.ID).filter(
		Settleplate.Batch == data['batch'],
		Settleplate.Location == data['location']
	).first()
	if existing_location:
		return jsonify({'error': 'Location already registered in this batch'}), 409 # conflict
	
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
		current_app.logger.exception('Failed to register settleplate: %s' % str(e))
		return jsonify({'committed': False, 'reason': f'Database error: {str(e)}'}), 500 # internal server error

	current_app.logger.info(f"User {g.username} registered settleplate : {new_sp.ID}")
	return jsonify({'committed':True})

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