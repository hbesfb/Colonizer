from flask import Blueprint, current_app, render_template, request, jsonify, g
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.barcodeparser import Decoder
from settings import settings
from sqlalchemy.exc import IntegrityError

blueprint = Blueprint("register",__name__,url_prefix="/settleplate")

@blueprint.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'GET':
		return render_template('register.html')

	raw_data = request.get_json()

	if settings['general'].get('workflow_starts_with_batch', True):
		return register_legacy(raw_data)
	return register_gs1(raw_data)


def register_legacy(data):
	data.update(Decoder.parse_input(data['serial'])) # parse serial and add result to data dictionary

	if missing := check_missing_fields(data): # use default required fields for legacy
		return jsonify({"error": {"message": f"Missing required field(s): {', '.join(missing)}"}}), 400

	new_sp = build_settleplate(data)
	return commit_settleplate(new_sp)


def register_gs1(data):
	current_app.logger.info(f"User {g.username} registering settleplate with data: {data}")

	# align required fields with JS payload + full GS1 barcode
	required_gs1_fields = ['batch', 'plate_serial', 'full_barcode', 'location', 'expire', 'lot']
	if missing := check_missing_fields(data, required_gs1_fields):
		return jsonify({"error": {"message": f"Missing required field(s): {', '.join(missing)}"}}), 400
	new_sp = build_settleplate(data)
	return commit_settleplate(new_sp)


def build_settleplate(data: dict):
	"""Construct a Settleplate instance from a validated data dict."""
	new_sp = Settleplate()
	new_sp.Username = g.username
	new_sp.Batch    = data['batch']
	new_sp.Location = data['location']

	# new_sp row will have null values for Lot_no and Expires if 'lot' and 'expire' are missing from data
	# this is consistent with legacy behavior where lot and expire were not required fields and
	# missing values were stored as null in the DB
	if 'lot' in data:
		new_sp.Lot_no = data['lot']
	if 'expire' in data:
		new_sp.Expires = data['expire']


	#TODO: find out if we want to allow registering expired plates, if not:
	# if 'expire' in data and data['expire'] < datetime.utcnow():
	# 	return jsonify({'committed': False, 'reason': 'expired_plate'}), 400

	new_sp.Counts   = -1
	
	#TODO consider adding PlateSerial to settleplate model (model.py) to store the original serial number separate from the full barcode
	# Thereafter you can add a separate field for PlateSerial
	if not settings['general'].get('workflow_starts_with_batch', True):
		clean_barcode = data['full_barcode'].replace("\x1D", "") # remove FNC1 separators before storage
		new_sp.Barcode = clean_barcode
		#new_sp.PlateSerial = data['plate_serial'] # value will not be saved since the ORM model does not define this column
	else:
		new_sp.Barcode = data['serial'] # in legacy mode
	return new_sp

def commit_settleplate(new_sp: Settleplate):
	"""
	Attempt to persist a Settleplate, returning a JSON response.
	Returns (response, status_code) on conflict, or a success response.
	"""
	try:
		db.session.add(new_sp)
		db.session.commit()
	except IntegrityError:
		db.session.rollback()
		return jsonify({"error": {"type": "DUPLICATE_LOCATION", "message": "Location already used for this lot"}}), 409
	except Exception as e:
		db.session.rollback()
		return jsonify({"error": {"type": "DB_ERROR", "message": str(e)}}), 500

	current_app.logger.info(f"User {g.username} registered settleplate: {new_sp.ID}")
	return jsonify({"committed": True}), 200


def check_missing_fields(data: dict, required_fields=None):
	"""
	Avoid inserting a row in the DB unless data is complete and valid.
	Check for missing required fields in the input data.
	"""
	if required_fields is None:
		# note that lot and expire were not required in legacy code, 
		# if missing they are saved with null values in the DB
		
		# minimal legacy requirements
		required_fields = ['batch', 'serial', 'location']
	return [k for k in required_fields if k not in data]


@blueprint.route('/batch_bydate', methods=(['POST']))
def batch_bydate():
	data = request.get_json(silent=True) # return None for invalid or missing JSON body instead of raising an exception
	if not data: # If data is None
		return jsonify([])

	# Use .get() + falsy check to avoid KeyError when 'batch' is missing or empty;
	batch_id = data.get('batch')
	if not batch_id:
		return jsonify([])

	limit=25
	# use exact match (ie == not .like)
	results = db.session.query(Settleplate.ScanDate, Settleplate.Barcode, Settleplate.Location).filter(Settleplate.Batch == batch_id).order_by(Settleplate.ScanDate.desc()).limit(limit).all()
	#  TODO: Find out if table view should only show registraton rows (ie Counts == -1)
	# results = db.session.query(Settleplate.ScanDate, Settleplate.Barcode, Settleplate.Location).filter(Settleplate.Batch==batch_id,Settleplate.Counts==-1).order_by(Settleplate.ScanDate.desc()).limit(limit).all()
	
	response = [{'ScanDate':sp.ScanDate.strftime("%Y-%m-%d %H:%M"),'Barcode':sp.Barcode,'Location':sp.Location} for sp in results]
	return jsonify(response)