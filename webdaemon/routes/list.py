from datetime import datetime, timedelta, date
from flask import Blueprint, current_app, render_template, request, g
from webdaemon.model import Settleplate
from webdaemon.database import db

blueprint = Blueprint("list",__name__,url_prefix="/settleplate")

@blueprint.route('/list', methods=['GET', 'POST'])
def settleplates():
	# if get
	if request.method == 'POST' and g.isAdmin:
		selected = request.form.getlist("selected")
		for settleplate_id in selected:
			settleplate = Settleplate.query.get(int(settleplate_id))
			db.session.delete(settleplate)
		db.session.commit()
		current_app.logger.info(f"User {g.username} deleting settleplates : {selected}")

	# define search from request data
	date_from = request.args.get('from', (date.today() - timedelta(days=7)).isoformat(), str)
	date_to = request.args.get('to', (date.today()).isoformat(), str)
	batch = request.args.get('batch', "", str)

	#define query
	query = Settleplate.query
	# filter date
	try:
		a = date(*map(int, date_from.split('-')))
		b = date(*map(int, date_to.split('-')))
		query = query.filter(
			Settleplate.ScanDate >= datetime(a.year, a.month, a.day),
			Settleplate.ScanDate <= datetime(b.year, b.month, b.day, 23, 59, 59)
		)

	except:
		query = query.filter(
			Settleplate.ScanDate >= datetime.today() - timedelta(days=7)
		)
	# filter by batch
	if batch != "":
		query = query.filter(Settleplate.Batch.contains(batch))
	# return	results
	settleplates = query.order_by(Settleplate.ScanDate.desc()).all()
	return render_template('list.html', settleplates=settleplates, date_from=date_from, date_to=date_to, batch=batch)
