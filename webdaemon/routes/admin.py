from flask import Blueprint, current_app, render_template, g, abort
from settings import settings

blueprint = Blueprint("admin",__name__, url_prefix="/admin")

@blueprint.route('/settings', methods=['GET'])
def admin_settings():
	if not g.isAdmin:
		abort(404)

	return render_template('settings.html', settings=settings.data)#, form=form)
