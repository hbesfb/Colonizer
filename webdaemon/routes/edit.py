from datetime import datetime
from flask import Blueprint, current_app, render_template, request, redirect, url_for, g, abort
from webdaemon.model import Settleplate, SettleplateForm
from webdaemon.database import db
from settings import settings

blueprint = Blueprint("edit",__name__,url_prefix="/settleplate")

@blueprint.route('/<int:settleplate_id>', methods=['GET', 'POST'])
def edit_settleplate(settleplate_id):
	#try to fetch settleplate
	sp = Settleplate.query.get(int(settleplate_id))
	if sp is None:
		abort(404)

	# do user have access to change/delete this?
	# must either be admin, or creator withing 30 minutes
	age = (datetime.now()-sp.ScanDate).total_seconds()
	readonly = not (g.isAdmin or (sp.Username == g.username and age < settings['general']['grace_period']))

	# create form
	form = SettleplateForm(obj=sp)

	# validate form if POST
	updated = False
	action = request.form.get('send', None)
	if action == "update" and not readonly:
		if form.validate_on_submit():
			form.populate_obj(sp)
			try:
				db.session.add(sp)
				db.session.commit()
			except:
				current_app.logger.error(f"Failed to update : {sp.ID}")
			else:
				current_app.logger.info(f"Updating settleplate : {sp.ID}")
				updated = True
	elif action == "delete" and not readonly:
		current_app.logger.info(f"Deleting settleplate : {sp.ID}")
		db.session.delete(sp)
		db.session.commit()
		return redirect(url_for('list.settleplates'))

	return render_template('settleplate.html', settleplate=sp, form=form, readonly=readonly, updated=updated)
