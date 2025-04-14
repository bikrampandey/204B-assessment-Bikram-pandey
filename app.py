from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
#from models import db
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# our database uri
if 'RDS_DB_NAME' in os.environ:
    app.config['SQLALCHEMY_DATABASE_URI'] = \
        'postgresql://{username}:{password}@{host}:{port}/{database}'.format(
        username=os.environ['RDS_USERNAME'],
        password=os.environ['RDS_PASSWORD'],
        host=os.environ['RDS_HOSTNAME'],
        port=os.environ['RDS_PORT'],
        database=os.environ['RDS_DB_NAME'],
    )
else:
    # our database uri
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:6979BIKRAm##@localhost:5432/contacts_db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Print template directory for debugging
print("Template directory:", os.path.join(os.path.dirname(__file__), 'templates'))

# Database migration settings
# db.init_app(app)
#migrate = Migrate(app, db)




if __name__ == '__main__':
    app.run(debug=True, port=5004)