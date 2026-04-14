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
	data = request.get_json()
	if "barcode" in data:
		# query for registration
		query = db.session.query(Settleplate.Location, Settleplate.Batch, Settleplate.Lot_no, Settleplate.ScanDate, Settleplate.Expires, Settleplate.Lot_no)
		filters = query.filter(Settleplate.Barcode.like(data['barcode']), Settleplate.Counts == -1)
		plateinfo = filters.one()
		if len(plateinfo):
			sp = Settleplate()
			sp.Username = g.username
			sp.ScanDate = datetime.fromisoformat(session['image_timestamp'])
			sp.Barcode = data['barcode']
			sp.Lot_no = plateinfo.Lot_no
			sp.Expires = plateinfo.Expires
			sp.Counts = data['counts']
			sp.Location = plateinfo.Location
			sp.Batch = plateinfo.Batch
			sp.Image = session['image_jpeg']
			sp.Colonies = data['colonies'].encode('utf8')
			#for key, value in sp.__dict__.items():
			#	current_app.logger.debug(f'SP[{key}]: {value} ({type(value)})')
			try:
				db.session.add(sp)
				db.session.commit()
			except Exception as e:
				current_app.logger.error('Failed to write to DB: %s'%str(e))
				return jsonify({'committed':False})
			else:
				dt = round((sp.ScanDate - plateinfo.ScanDate).total_seconds() / 3600) # convert to hours
				current_app.logger.info(f'User {g.username} scanned {sp.ID} to DB with {sp.Counts} counts')
				return jsonify({'committed':True, 'Counts': sp.Counts, 'ID': sp.ID, 'dT': dt })
		else:
			return jsonify({'committed':False})


@blueprint.route('/info', methods=(['POST']))
def plate_info():
	data = request.get_json()
	barcode = data['barcode']
	if not len(barcode):
		return jsonify({'error':'missing serial'})
	
	# query for registration
	query = db.session.query(Settleplate.ScanDate, Settleplate.Location, Settleplate.Batch, Settleplate.Username)
	filters = query.filter(Settleplate.Barcode.like(barcode), Settleplate.Counts == -1)
	try:
		plateinfo = filters.one()
	except:
		return jsonify({'error':'serial not in db'})

	# query for scans
	query = db.session.query(Settleplate.ID, Settleplate.ScanDate, Settleplate.Counts)
	filters = query.filter(Settleplate.Barcode.like(barcode), Settleplate.Counts >= 0)
	# return sorted and max 10
	scans = filters.order_by(Settleplate.ScanDate.asc()).limit(10).all()
	timepoints = []
	for scan in scans:
		dt = round((scan.ScanDate - plateinfo.ScanDate).total_seconds() / 3600) # convert to hours
		timepoints.append({
			'ID' : scan.ID,
			'Counts' : scan.Counts,
			'dT' : dt
		})

	# return plate info and scan times
	response = plateinfo._asdict()
	# check if user scanning plate is same as user registering, and check if settings allow this
	response['SameUser'] = (g.username == plateinfo.Username) and settings['general']['sameuser']
	response['Timepoints'] = timepoints
	return jsonify(response)