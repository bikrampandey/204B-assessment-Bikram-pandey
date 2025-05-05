from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os
import time
import uuid
from models import db, User, Contact

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a strong random key
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure file upload settings
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database configuration
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
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost:5432/contacts_db'

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)

# Track failed login attempts
failed_attempts = {}  # Format: {email: {'count': int, 'lockout_until': float}}

@app.route('/')
def index():
    return redirect(url_for('login_by_ajax'))

@app.route('/login-by-ajax', methods=['GET', 'POST'])
def login_by_ajax():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        output_msg = ""
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            return jsonify({'output_msg': f'Welcome back, {user.full_name}!', 'success': True})
        else:
            return jsonify({'output_msg': 'Invalid email or password. Please try again.', 'success': False})
        
    return render_template('login.html')

@app.route('/signup_by_ajax', methods=['GET', 'POST'])
def signup_by_ajax():
    if request.method == 'POST':
        full_name = request.form['username']
        email = request.form['email']
        address = request.form['address']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match.'})
        
        profile_picture = request.files.get('profile_picture')
        profile_picture_path = None
        if profile_picture and allowed_file(profile_picture.filename):
            filename = secure_filename(profile_picture.filename)
            profile_picture_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_picture.save(profile_picture_path)
            profile_picture_path = os.path.join('uploads', filename)
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'Email already in use.'})
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            full_name=full_name,
            email=email,
            password=hashed_password,
            address=address,
            phone=phone,
            profile_picture=profile_picture_path
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Signup successful!', 'redirect': url_for('login_by_ajax')})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    
    return render_template('signup.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_by_ajax'))
    return render_template('home.html', user=user)

@app.route('/list')
def list():
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    contacts = Contact.query.filter_by(user_id=session['user_id']).all()
    return render_template('list.html', contacts=contacts)

@app.route('/add_contact', methods=['GET', 'POST'])
def add_contact():
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    
    if request.method == 'POST':
        try:
            name = request.form['name']
            age = int(request.form['age'])
            phone = request.form['phone']
            address = request.form['address']
            email = request.form['email']
            profile_picture = request.files.get('profile_picture')
            profile_picture_path = None
            
            if profile_picture and allowed_file(profile_picture.filename):
                filename = secure_filename(profile_picture.filename)
                profile_picture_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                profile_picture.save(profile_picture_path)
                profile_picture_path = os.path.join('uploads', filename)
            
            existing_contact = Contact.query.filter_by(email=email, user_id=session['user_id']).first()
            if existing_contact:
                return jsonify({'success': False, 'message': 'Email already exists in contacts!'})
            
            new_contact = Contact(
                name=name,
                age=age,
                phone=phone,
                address=address,
                email=email,
                profile_picture=profile_picture_path,
                user_id=session['user_id']
            )
            
            db.session.add(new_contact)
            db.session.commit()
            return jsonify({'success': True, 'redirect': url_for('list')})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    
    return render_template('add_contact.html')

@app.route('/edit_contact/<int:contact_id>', methods=['GET', 'POST'])
def edit_contact(contact_id):
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    
    contact = Contact.query.get_or_404(contact_id)
    if contact.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    if request.method == 'POST':
        try:
            contact.name = request.form['name']
            contact.email = request.form['email']
            contact.address = request.form['address']
            contact.phone = request.form['phone']
            contact.age = int(request.form['age'])
            
            profile_picture = request.files.get('profile_picture')
            if profile_picture and allowed_file(profile_picture.filename):
                filename = secure_filename(profile_picture.filename)
                profile_picture_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                profile_picture.save(profile_picture_path)
                contact.profile_picture = os.path.join('uploads', filename)
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Contact updated successfully', 'redirect': url_for('list')})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    
    return render_template('edit_contact.html', contact=contact)

@app.route('/delete_confirm/<int:contact_id>', methods=['GET', 'POST'])
def delete_confirm(contact_id):
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    
    contact = Contact.query.get_or_404(contact_id)
    if contact.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    return render_template('delete_confirm.html', contact=contact)

@app.route('/delete_contact/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    
    contact = Contact.query.get_or_404(contact_id)
    if contact.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Contact deleted successfully', 'redirect': url_for('list')})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        try:
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            if new_password != confirm_password:
                return jsonify({'success': False, 'message': 'Passwords do not match'})
            user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            db.session.commit()
            return jsonify({'success': True, 'message': 'Password changed successfully!', 'redirect': url_for('home')})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    
    return render_template('change_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_by_ajax'))

@app.route('/test_db')
def test_db():
    try:
        db.session.execute('SELECT 1')
        return "Database connected successfully!"
    except Exception as e:
        return f"Database connection failed: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5003)