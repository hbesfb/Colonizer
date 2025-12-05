from flask import Blueprint, current_app, render_template, request, jsonify, g
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.barcodeparser import Decoder

blueprint = Blueprint("register",__name__,url_prefix="/settleplate")

@blueprint.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'GET':
		return render_template('register.html')

	data = request.get_json() or {} # safely get JSON even if body is missing or invalid
	
	serial = data.get('serial')
	if serial:
		parsed = Decoder.parse_input(serial)
		if parsed:
			data.update(parsed)
		
	required = ['batch', 'serial', 'location']
	if all([k in data for k in required]):
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

		try:
			db.session.add(new_sp)
			db.session.commit()
			current_app.logger.info(f"User {g.username} registered settleplate : {new_sp.ID}")
		except Exception as e:
			current_app.logger.error(f"Failed to register settleplate: {str(e)}")
			return jsonify({
				'commited': False,   # TODO: fix legacy misspelling
				'error': 'db_write_failed'
			})

		# Success response
		return jsonify({
			'commited': True, # TODO: fix legacy misspelling
			'id': new_sp.ID
		})

	# Error response if required fields missing
	current_app.logger.warning("Register request missing required fields")
	return jsonify({
		'commited': False,  # TODO: fix legacy misspelling
		'error': 'Missing required fields'
	})

@blueprint.route('/batch_bydate', methods=(['POST']))
def batch_bydate():
	data = request.get_json() or {}
	batch_id = data.get('batch', "")
	if len(batch_id):
		limit=25
		results = db.session.query(Settleplate.ScanDate, Settleplate.Barcode, Settleplate.Location).filter(Settleplate.Batch.like(batch_id)).order_by(Settleplate.ScanDate.desc()).limit(limit).all()
		response = [{'ScanDate':sp.ScanDate.strftime("%Y-%m-%d %H:%M"),'Barcode':sp.Barcode,'Location':sp.Location} for sp in results]
		return jsonify(response)
	return jsonify([])