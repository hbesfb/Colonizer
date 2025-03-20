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
	data.update(Decoder.parse_input(data['serial'])) # parse serial and add result to data dictionary
		
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
		db.session.add(new_sp)
		db.session.commit()
		current_app.logger.info(f"User {g.username} registered settleplate : {new_sp.ID}")

	return jsonify({'commited':True})

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