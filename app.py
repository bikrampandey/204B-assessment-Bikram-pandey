from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os
import time
from datetime import datetime as dt
import threading
import uuid
from models import db, User, Contact

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a strong random key
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Configure file upload settings
PROFILE_PIC_UPLOAD_FOLDER = 'static/profile_pic_uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif','jfif'}
app.config['PROFILE_PIC_UPLOAD_FOLDER'] = PROFILE_PIC_UPLOAD_FOLDER

CONTACTS_PIC_UPLOADS_FOLDER='static/contacts_pic_uploads/'
ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif','jfif'}
app.config['CONTACTS_PIC_UPLOADS_FOLDER'] = CONTACTS_PIC_UPLOADS_FOLDER

if not os.path.exists(PROFILE_PIC_UPLOAD_FOLDER):
    os.makedirs(PROFILE_PIC_UPLOAD_FOLDER)

if not os.path.exists(CONTACTS_PIC_UPLOADS_FOLDER):
    os.makedirs(CONTACTS_PIC_UPLOADS_FOLDER)


failed_attempts_lock = threading.Lock()

'''
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
'''

# Function for file type validation
# Returns true if file to upload is of the type mentioned in ALLOWED_EXTENSIONS setting
def allowed_file(filename):
    # if file is user.jpg, it splits it at the '.' into two words -> user, jpg. It returns the second word i.e. jpg, 
    # converts it to lower case and checks if its in the ALLOWED_EXTENSIONS
    print("Here??")
    file_name_split = filename.rsplit('.', 1)
    print("Here too??")
    file_extension = file_name_split[1]
    print(file_extension)
    if file_extension in ALLOWED_EXTENSIONS:
        return True
    else:
        return False
    '''

    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           '''

# function to get the file extension
def get_file_extension(filename):
    print("Here??")
    file_name_split = filename.rsplit('.', 1)
    print("Here too??")
    file_extension = file_name_split[1]
    print(file_extension)
    return file_extension

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
        
        # Check for lockout
        with failed_attempts_lock:
            if email in failed_attempts:
                lockout_until = failed_attempts[email].get('lockout_until', 0)
                current_time = time.time()
                if lockout_until > current_time:
                    remaining_time = int(lockout_until - current_time)
                    return jsonify({
                        'output_msg': f'Too many failed attempts. Please wait {remaining_time} seconds.',
                        'success': False
                    })
                elif lockout_until <= current_time and failed_attempts[email].get('count', 0) >= 3:
                    # Reset attempts after lockout period expires
                    failed_attempts[email] = {'count': 0, 'lockout_until': 0}
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            with failed_attempts_lock:
                # Reset failed attempts on successful login
                if email in failed_attempts:
                    failed_attempts[email] = {'count': 0, 'lockout_until': 0}
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            return jsonify({'output_msg': f'Welcome back, {user.full_name}!', 'success': True})
        else:
            with failed_attempts_lock:
                # Increment failed attempts
                if email not in failed_attempts:
                    failed_attempts[email] = {'count': 0, 'lockout_until': 0}
                failed_attempts[email]['count'] += 1
                if failed_attempts[email]['count'] >= 3:
                    # Set lockout for 3 minutes (180 seconds)
                    failed_attempts[email]['lockout_until'] = time.time() + 180
                    return jsonify({
                        'output_msg': 'Too many failed attempts. Account locked for 3 minutes.',
                        'success': False
                    })
            return jsonify({
                'output_msg': 'Invalid email or password. Please try again.',
                'success': False
            })
        
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

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'Email already in use.'})
                
        # Handle profile picture upload
        profile_picture = request.files.get('profile_picture')
        print(f"Profile Picture: {profile_picture}")  # Debug
        print(f"Request Files: {request.files}")  # Debug entire files dict
        profile_pic_file_path = None  # Default to None if no file
        
        if profile_picture and allowed_file(profile_picture.filename):
            filename = secure_filename(profile_picture.filename)
            print(filename)
            dt_now = dt.now().strftime("%Y%m%d%H%M%S%f")
            file_extension = get_file_extension(profile_picture.filename)

            filename_to_save = full_name + "_" + dt_now + "." + file_extension
            print(filename_to_save)            
            # Save this file to the folder path
            profile_picture.save(os.path.join(app.config['PROFILE_PIC_UPLOAD_FOLDER'], filename_to_save))
            profile_pic_file_path = PROFILE_PIC_UPLOAD_FOLDER + filename_to_save
            print(profile_pic_file_path)

        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            full_name=full_name,
            email=email,
            password=hashed_password,
            address=address,
            phone=phone,
            profile_picture=profile_pic_file_path
        )
        print(new_user)
        
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
    print("DID IT RETRIEVE THE USER??")
    print(user)
    if not user:
        session.clear()
        return redirect(url_for('login_by_ajax'))
    print(f"Rendering home for user: {user.email}, Profile Picture: {user.profile_picture}")  # Debug
    if user.profile_picture:
        print("IS IT HERE??")
        absolute_path = os.path.join(app.config['PROFILE_PIC_UPLOAD_FOLDER'], os.path.basename(user.profile_picture))
        print(f"Checking profile picture at: {absolute_path}, Exists: {os.path.exists(absolute_path)}")  # Debug
    return render_template('home.html', user=user)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login_by_ajax'))
    
    if request.method == 'POST':
        try:
            # Update user information
            user.full_name = request.form['full_name']
            user.email = request.form['email']
            user.address = request.form['address']
            user.phone = request.form['phone']
            
            # Handle profile picture upload
            profile_picture = request.files.get('profile_picture')
            if profile_picture and allowed_file(profile_picture.filename):
                filename = secure_filename(profile_picture.filename)
                dt_now = dt.now().strftime("%Y%m%d%H%M%S%f")
                file_extension = get_file_extension(profile_picture.filename)
                filename_to_save = f"{user.full_name}_{dt_now}.{file_extension}"
                profile_picture_path = os.path.join(app.config['PROFILE_PIC_UPLOAD_FOLDER'], filename_to_save)
                profile_picture.save(profile_picture_path)
                user.profile_picture = os.path.join('static/profile_pic_Uploads', filename_to_save)
                print(f"Updated Profile Picture: {user.profile_picture}")  # Debug
            
            db.session.commit()
            session['user_name'] = user.full_name  # Update session name
            return jsonify({'success': True, 'message': 'Profile updated successfully!', 'redirect': url_for('home')})
        except Exception as e:
            db.session.rollback()
            print(f"Error updating profile: {str(e)}")  # Debug
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    
    return render_template('profile.html', user=user)

@app.route('/all_contact')
def all_contact():
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    contacts = Contact.query.filter_by(user_id=session['user_id']).all()
    
    return render_template('all_contact.html', contacts=contacts)

@app.route('/add_contact', methods=['GET', 'POST'])
def add_contact():
    if 'user_id' not in session:
        return redirect(url_for('login_by_ajax'))
    
    if request.method == 'POST':
        try:
            name = request.form['name']
            age = request.form['age']
            phone = request.form['phone']
            address = request.form['address']
            email = request.form['email']
            profile_picture = request.files.get('profile_picture')

            # Validate required fields
            if not name or not email or not age:
                return jsonify({'success': False, 'message': 'Name, email, and age are required'})
            if not address:
                return jsonify({'success': False, 'message': 'Address is required'})
            if not phone:
                return jsonify({'success': False, 'message': 'Phone number is required'})
            
            try:
                age = int(age)
            except ValueError:
                return jsonify({'success': False, 'message': 'Age must be a valid number'})

            # Check for existing contact
            existing_contact = Contact.query.filter_by(email=email, user_id=session['user_id']).first()
            if existing_contact:
                return jsonify({'success': False, 'message': 'Email already exists in contacts!'})

            # Handle profile picture upload
            profile_picture_path = None
            if profile_picture and allowed_file(profile_picture.filename):
                filename = secure_filename(profile_picture.filename)
                dt_now = dt.now().strftime("%Y%m%d%H%M%S%f")
                file_extension = get_file_extension(profile_picture.filename)
                filename_to_save = f"{name}_{dt_now}.{file_extension}"
                profile_picture_path = os.path.join(app.config['CONTACTS_PIC_UPLOADS_FOLDER'], filename_to_save)
                profile_picture.save(profile_picture_path)
                profile_picture = os.path.join('static/contacts_pic_uploads', filename_to_save)
                print(f"Updated Profile Picture: {profile_picture}")  # Debug
               

            # Create new contact
            new_contact = Contact(
                name=name,
                age=age,
                phone=phone,
                address=address,
                email=email,
                user_id=session['user_id'],
                profile_picture=profile_picture_path
            )
            
            db.session.add(new_contact)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Contact added successfully', 'redirect': url_for('all_contact')})
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
    
    if contact.profile_picture:
        print("IS IT HERE??")
        save_path = os.path.join(app.config['CONTACTS_PIC_UPLOADS_FOLDER'], os.path.basename(contact.profile_picture))
        print(f"Checking profile picture at: {save_path}, Exists: {os.path.exists(save_path)}")  # Debug
    
    if request.method == 'POST':
        try:
            contact.name = request.form['name']
            contact.email = request.form['email']
            contact.address = request.form['address']
            contact.phone = request.form['phone']
            age = request.form['age']
            profile_picture = request.files.get('profile_picture')

            # Validate required fields
            if not contact.name or not contact.email or not contact.address or not contact.phone or not age:
                return jsonify({'success': False, 'message': 'All fields are required'})

            try:
                contact.age = int(age)
            except ValueError:
                return jsonify({'success': False, 'message': 'Age must be a valid number'})

            # Check for duplicate email
            existing_contact = Contact.query.filter_by(email=contact.email, user_id=session['user_id']).first()
            if existing_contact and existing_contact.id != contact.id:
                return jsonify({'success': False, 'message': 'Email already exists in contacts!'})

            # Handle profile picture upload
            if profile_picture and allowed_file(profile_picture.filename):
                # Delete old image if exists
                print("CONTACT PROFILE PICTURE")
                print(contact.profile_picture)
                if contact.profile_picture and os.path.exists(os.path.join('static', contact.profile_picture)):
                    print(f"Deleting old image: {contact.profile_picture}")  # Debug
                    os.remove(os.path.join('static', contact.profile_picture))
                filename = secure_filename(profile_picture.filename)
                dt_now = dt.now().strftime("%Y%m%d%H%M%S%f")
                file_extension = get_file_extension(profile_picture.filename)
                filename_to_save = f"{contact.name}_{dt_now}.{file_extension}"
                save_path = os.path.join(app.config['CONTACTS_PIC_UPLOADS_FOLDER'], filename_to_save)
                print(f"Saving new contact image to: {save_path}")  # Debug
                profile_picture.save(save_path)
                #profile_picture = os.save_path.join('static/contacts_pic_uploads', filename_to_save)
                contact.profile_picture=save_path
                print(f"Updated Profile Picture: {profile_picture}")  # Debug
            db.session.commit()
            return jsonify({'success': True, 'message': 'Contact updated successfully', 'redirect': url_for('all_contact')})
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
        # Delete profile picture file if exists
        if contact.profile_picture and os.path.exists(os.path.join('static', contact.profile_picture)):
            os.remove(os.path.join('static', contact.profile_picture))
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Contact deleted successfully', 'redirect': url_for('all_contact')})
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
            return jsonify({'success': True, 'message': 'Password changed successfully!', 'redirect': url_for('profile')})
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