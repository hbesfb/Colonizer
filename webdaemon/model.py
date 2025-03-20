from datetime import datetime
from sqlalchemy.orm import deferred
from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField, DateField, FloatField, IntegerField, validators, HiddenField, FieldList
from webdaemon.database import db
from webdaemon.version import __version__

# using sqlacodegen db_uri

class Settleplate(db.Model):
	__tablename__ = 'SETTLEPLATE'
	ID = db.Column(db.Integer, primary_key=True)
	Username = db.Column(db.NVARCHAR(32))
	ScanDate = db.Column(db.DateTime)
	Barcode = db.Column(db.VARCHAR(128))
	Lot_no = db.Column(db.VARCHAR(64))
	Expires = db.Column(db.Date)
	Counts = db.Column(db.Integer)
	Version = db.Column(db.VARCHAR(32))
	Location = db.Column(db.NVARCHAR(128))
	Batch = db.Column(db.NVARCHAR(128))
	Image = deferred(db.Column(db.LargeBinary)) # deferred so only loaded when accessed, not when queried
	Colonies = db.Column(db.VARCHAR('max'))
	Exported = db.Column(db.BINARY(1), default=False)

	def __init__(self, **kwargs):
			super(Settleplate, self,).__init__(**kwargs)
			self.ScanDate = datetime.now()
			self.Exported = False
			self.Version = f"WebApp {__version__}"

	def __repr__(self):
		return '<Settleplate %r>' % self.ID

class SettleplateForm(FlaskForm):
	Username = StringField('Name', [validators.DataRequired("Please enter study name")])
	ScanDate = DateTimeField('Date')
	Barcode = StringField('Barcode', [validators.DataRequired("Settleplate barcode needed")])
	Lot_no = StringField('Lot number')
	Expires = DateField('Expire Date')
	Counts = IntegerField('Counts')
	Location = StringField('Location', [validators.DataRequired("Location needed")])
	Batch = StringField('Batch', [validators.DataRequired("Batch# needed")])
	Colonies = HiddenField('Colonies') #, filters=[lambda x: x.decode('utf8') if type(x) is bytes else x])
	Version = StringField('Version', render_kw={'readonly': True})

	#def validate_Colonies(form, field):
	#	if type(field.data) is str:
	#		field.data = field.data.encode('utf8')
	#	return type(field.data) is bytes