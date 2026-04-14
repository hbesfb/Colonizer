from datetime import datetime
from flask import Blueprint, current_app, render_template, request, jsonify, session, g
from webdaemon.model import Settleplate, SettleplateForm
from webdaemon.database import db
from settings import settings

blueprint = Blueprint("scan",__name__,url_prefix="/settleplate")

@blueprint.route('/scan', methods=['GET', 'POST'])
def scan():
	if request.method == 'GET':
		sp = Settleplate()
		form = SettleplateForm(obj=sp)
		return render_template('scan.html', settleplate=sp, form=form, autocount=settings['general']['autocount'])

	# else if POST
	data = request.get_json() or {} # ensure that data is always a dictionary, even if no JSON is sent.

	# Validate barcode
	barcode = data.get("barcode")
	if not barcode:
		return jsonify({'committed': False, 'error': 'missing barcode'})

	# Validate image capture
	image_timestamp = session.get('image_timestamp')
	img = session.get('image_jpeg')

	if not image_timestamp or not img:
		current_app.logger.error(f"Invalid image capture: image_timestamp={repr(image_timestamp)}, img={type(img)}")
		return jsonify({'committed': False, 'error': 'Image not saved. None was was captured - Check if camera is available'})

	# query for registration (use query that works for both MSSQL and PostgreSQL)
	# returns exactly one row or None if 0 rows match (and raises an error if multiple rows are found)
	plateinfo = (
		Settleplate.query
		.filter(Settleplate.Barcode == barcode,	
				Settleplate.Counts == -1)
		.one_or_none()
	)

	if plateinfo is None:
		return jsonify({'committed': False, 'error': 'barcode not registered'})

	sp = Settleplate()
	sp.Username = g.username
	sp.ScanDate = datetime.fromisoformat(image_timestamp)
	sp.Barcode = barcode
	sp.Lot_no = plateinfo.Lot_no
	sp.Expires = plateinfo.Expires
	counts = data.get('counts')
	if counts is None:
		return jsonify({'committed': False, 'error': 'missing counts'})
	sp.Counts = int(counts) # ensure that counts is an integer
	sp.Location = plateinfo.Location
	sp.Batch = plateinfo.Batch
	sp.Image = img
	# colonies should be string not bytes as was with old code ( data['colonies'].encode('utf8')  # produces bytes)
	sp.Colonies =  data.get('colonies')
	try:
		db.session.add(sp)
		db.session.commit()
	except Exception as e:
		db.session.rollback()
		current_app.logger.error('Failed to write to DB: %s'%str(e))
		return jsonify({'committed': False, 'error': f'Database error: {str(e)}'})

	dt = None
	if plateinfo.ScanDate:
		dt = round((sp.ScanDate - plateinfo.ScanDate).total_seconds() / 3600) # convert to hours
		current_app.logger.info(f'User {g.username} scanned {sp.ID} to DB with {sp.Counts} counts')
	
	return jsonify({'committed':True, 'Counts': sp.Counts, 'ID': sp.ID, 'dT': dt })

@blueprint.route('/info', methods=(['POST']))
def plate_info():
	data = request.get_json() or {}
	barcode = data.get('barcode') # does not throw keyError where 'barcode' is missing or None
	if not barcode: # safer when 'barcode' is missing or None or empty string
		return jsonify({'error':'missing serial'})
	
	# query for registration
	plateinfo = (
		Settleplate.query
		.filter(Settleplate.Barcode == barcode,
				Settleplate.Counts == -1)
		.one_or_none()
	)

	if plateinfo is None:
		return jsonify({'error': 'serial not in db'})

	# query for scans
	# .like() behaves differently across MSSQL and PostgreSQL, so we use a query that works for both
	scans = (
		Settleplate.query
		.filter(Settleplate.Barcode == barcode,
				Settleplate.Counts >= 0)
		.order_by(Settleplate.ScanDate.asc())
		.limit(10)
		.all()
	)

	timepoints = []
	for scan in scans:
		dt = round((scan.ScanDate - plateinfo.ScanDate).total_seconds() / 3600) # convert to hours
		timepoints.append({
			'ID' : scan.ID,
			'Counts' : scan.Counts,
			'dT' : dt
		})

	# return plate info and scan times
	response = {
		'ScanDate': plateinfo.ScanDate.isoformat() if plateinfo.ScanDate else None,
		'Location': plateinfo.Location,
		'Batch': plateinfo.Batch,
		'Username': plateinfo.Username,
		# check if user scanning plate is same as user registering, and check if settings allow this
		'SameUser': (g.username == plateinfo.Username) and settings['general']['sameuser'],
		'Timepoints': timepoints
	}
	return jsonify(response)