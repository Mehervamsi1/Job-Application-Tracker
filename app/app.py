# app.py - Main Flask Application
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
import os
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///job_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    job_applications = db.relationship('JobApplication', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"User('{self.name}', '{self.email}')"

class JobApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='applied')
    application_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    job_url = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"JobApplication('{self.title}', '{self.company}', '{self.status}')"

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('signin'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('signup.html')
        
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User with this email already exists!', 'error')
            return render_template('signup.html')
        
        # Create new user
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(name=name, email=email, password=hashed_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully! Please sign in.', 'success')
            return redirect(url_for('signin'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
    
    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('signin.html')

@app.route('/signout')
def signout():
    session.clear()
    flash('You have been signed out successfully.', 'success')
    return redirect(url_for('signin'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    # Get user's job applications
    job_applications = JobApplication.query.filter_by(user_id=user_id)\
                                          .order_by(JobApplication.application_date.desc())\
                                          .all()
    
    # Calculate statistics
    total_applications = len(job_applications)
    pending_applications = len([job for job in job_applications if job.status == 'applied'])
    interview_applications = len([job for job in job_applications if job.status == 'interview'])
    offer_applications = len([job for job in job_applications if job.status == 'offer'])
    
    stats = {
        'total': total_applications,
        'pending': pending_applications,
        'interviews': interview_applications,
        'offers': offer_applications
    }
    
    return render_template('dashboard.html', 
                         user=user, 
                         job_applications=job_applications, 
                         stats=stats)

@app.route('/add_job', methods=['GET', 'POST'])
@login_required
def add_job():
    if request.method == 'POST':
        title = request.form['title']
        company = request.form['company']
        status = request.form['status']
        application_date = datetime.strptime(request.form['application_date'], '%Y-%m-%d').date()
        job_url = request.form['job_url'] if request.form['job_url'] else None
        notes = request.form['notes'] if request.form['notes'] else None
        
        # Create new job application
        new_job = JobApplication(
            title=title,
            company=company,
            status=status,
            application_date=application_date,
            job_url=job_url,
            notes=notes,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_job)
            db.session.commit()
            flash('Job application added successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
    
    return render_template('add_job.html')

@app.route('/edit_job/<int:job_id>', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    job = JobApplication.query.filter_by(id=job_id, user_id=session['user_id']).first_or_404()
    
    if request.method == 'POST':
        job.title = request.form['title']
        job.company = request.form['company']
        job.status = request.form['status']
        job.application_date = datetime.strptime(request.form['application_date'], '%Y-%m-%d').date()
        job.job_url = request.form['job_url'] if request.form['job_url'] else None
        job.notes = request.form['notes'] if request.form['notes'] else None
        
        try:
            db.session.commit()
            flash('Job application updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
    
    return render_template('edit_job.html', job=job)

@app.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    job = JobApplication.query.filter_by(id=job_id, user_id=session['user_id']).first_or_404()
    
    try:
        db.session.delete(job)
        db.session.commit()
        flash('Job application deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred. Please try again.', 'error')
    
    return redirect(url_for('dashboard'))

# Create database tables
@app.before_first_request
def create_tables():
    db.create_all()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)