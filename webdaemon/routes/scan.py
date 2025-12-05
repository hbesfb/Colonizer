from datetime import datetime
from flask import Blueprint, current_app, render_template, request, jsonify, session, g
from webdaemon.model import Settleplate, SettleplateForm
from webdaemon.database import db
from settings import settings
from datetime import datetime, timezone

blueprint = Blueprint("scan",__name__,url_prefix="/settleplate")

@blueprint.route('/scan', methods=['GET', 'POST'])
def scan():
	if request.method == 'GET':
		sp = Settleplate()
		form = SettleplateForm(obj=sp)
		return render_template('scan.html', settleplate=sp, form=form, autocount=settings['general']['autocount'])

	# else if POST
	data = request.get_json() or {}
	barcode = data.get("barcode")
	if not barcode:
		current_app.logger.warning("Scan request missing barcode")
		#return jsonify({'committed': False})  # keeps old contract
		return jsonify({'committed': False, 'error': 'missing barcode'})

	# Query for registration
	query = db.session.query(
		Settleplate.Location,
		Settleplate.Batch,
		Settleplate.Lot_no,
		Settleplate.ScanDate,
		Settleplate.Expires
	)
	filters = query.filter(Settleplate.Barcode.like(barcode), Settleplate.Counts == -1)
	plateinfo = filters.first()

	if not plateinfo:
		current_app.logger.warning(f"Barcode {barcode} not registered in DB")
		#return jsonify({'committed': False})  # keep old contract
		return jsonify({'committed': False, 'error': 'barcode not registered'})

	sp = Settleplate()
	sp.Username = g.username
	sp.Barcode = barcode
	sp.Lot_no = plateinfo.Lot_no
	sp.Expires = plateinfo.Expires
	sp.Location = plateinfo.Location
	sp.Batch = plateinfo.Batch
	sp.Image = session.get('image_jpeg')

	# Safe timestamp handling
	image_ts = session.get('image_timestamp')
	try:
		sp.ScanDate = datetime.fromisoformat(image_ts) if image_ts else datetime.utcnow()
	except (TypeError, ValueError):
		sp.ScanDate = datetime.now(timezone.utc)

	counts = data.get('counts')
	if counts is None:
		current_app.logger.warning(f"Barcode {barcode} missing counts value")
		#return jsonify({'committed': False})  # keep old contract
		return jsonify({'committed': False, 'error': 'missing counts'})
	sp.Counts = counts

	colonies = data.get('colonies', '')
	sp.Colonies = colonies.encode('utf-8') if isinstance(colonies, str) else colonies

	try:
		db.session.add(sp)
		db.session.commit()
	except Exception as e:
		current_app.logger.error(f"Failed to write to DB: {str(e)}")
		return jsonify({'committed': False})  # keep old contract
	else:
		try:
			dt = round((sp.ScanDate - plateinfo.ScanDate).total_seconds() / 3600)
		except Exception:
			dt = 0
		current_app.logger.info(
			f"User {g.username} scanned {sp.ID} to DB with {sp.Counts} counts"
		)
		return jsonify({'committed': True, 'Counts': sp.Counts, 'ID': sp.ID, 'dT': dt})

@blueprint.route('/info', methods=['POST'])
def plate_info():
	data = request.get_json() or {}
	barcode = data.get('barcode', '')
	if not barcode:
		current_app.logger.warning("Plate info request missing barcode")
		return jsonify({'error': 'missing serial'})  # same as old contract

	# Query for registration
	query = db.session.query(
		Settleplate.ScanDate,
		Settleplate.Location,
		Settleplate.Batch,
		Settleplate.Username
	).filter(
		Settleplate.Barcode.like(barcode),
		Settleplate.Counts == -1
	)
	plateinfo = query.first()
	if not plateinfo:
		current_app.logger.warning(f"Plate info: serial {barcode} not in DB")
		return jsonify({'error': 'serial not in db'})

	# Query for scans
	scans = db.session.query(
		Settleplate.ID,
		Settleplate.ScanDate,
		Settleplate.Counts
	).filter(
		Settleplate.Barcode.like(barcode),
		Settleplate.Counts >= 0
	).order_by(Settleplate.ScanDate.asc()).limit(10).all()

	timepoints = []
	for scan in scans:
		try:
			dt = round((scan.ScanDate - plateinfo.ScanDate).total_seconds() / 3600)
		except Exception:
			dt = 0
		timepoints.append({
			'ID': scan.ID,
			'Counts': scan.Counts,
			'dT': dt
		})

	# Return plate info and scan times
	response = plateinfo._asdict()
	response['SameUser'] = (g.username == plateinfo.Username) and settings['general']['sameuser']
	response['Timepoints'] = timepoints
	return jsonify(response)