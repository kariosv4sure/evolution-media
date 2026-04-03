import os
import requests
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__,
            template_folder='templates',
            static_folder='static',
            static_url_path='/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///evolution.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import models AFTER app is created
from models import db, User, Chat

# Initialize db with app
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========================================
# MAIN PAGES - EVOLUTION MEDIA
# ========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/jamb')
def jamb():
    return render_template('jamb.html')

@app.route('/waec')
def waec():
    return render_template('waec.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# ========================================
# AUTHENTICATION ROUTES
# ========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if user.is_active:
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                flash('Login successful! Welcome back!', 'success')

                if user.is_admin:
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('dashboard'))
            else:
                flash('Your account is disabled. Please contact admin.', 'danger')
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            phone=phone
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    chats = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.created_at.desc()).limit(20).all()
    total_chats = Chat.query.filter_by(user_id=current_user.id).count()

    return render_template('dashboard.html',
                         chats=chats,
                         total_chats=total_chats,
                         user=current_user)

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        user_message = request.form.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Message is required'}), 400

        ai_response = get_ai_response(user_message, current_user.username)

        chat = Chat(
            user_id=current_user.id,
            user_message=user_message,
            bot_response=ai_response
        )
        db.session.add(chat)
        db.session.commit()

        return jsonify({
            'response': ai_response,
            'chat_id': chat.id,
            'timestamp': chat.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    history = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.created_at).all()
    return render_template('chat.html', history=history)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ========================================
# ADMIN ROUTES
# ========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')

        admin_user = User.query.filter_by(is_admin=True).first()

        if admin_user:
            if admin_user.username == username and admin_user.check_password(password):
                login_user(admin_user)
                flash('Admin login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
        else:
            if username == admin_username and password == admin_password:
                admin = User(
                    username=admin_username,
                    email='admin@evolutionmedia.com',
                    full_name='Evolution Media Admin',
                    is_admin=True
                )
                admin.set_password(admin_password)
                db.session.add(admin)
                db.session.commit()
                login_user(admin)
                flash('Admin account created and logged in!', 'success')
                return redirect(url_for('admin_dashboard'))

        flash('Invalid admin credentials.', 'danger')

    return render_template('admin_login.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    total_users = User.query.filter_by(is_admin=False).count()
    total_chats = Chat.query.count()
    active_today = User.query.filter(User.last_login >= datetime.utcnow() - timedelta(days=1)).count()
    recent_users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).limit(10).all()
    recent_chats = Chat.query.order_by(Chat.created_at.desc()).limit(20).all()

    user_growth = []
    for i in range(6, -1, -1):
        date = datetime.utcnow() - timedelta(days=i)
        start = datetime(date.year, date.month, date.day, 0, 0, 0)
        end = datetime(date.year, date.month, date.day, 23, 59, 59)
        count = User.query.filter(
            User.created_at >= start,
            User.created_at <= end,
            User.is_admin == False
        ).count()
        user_growth.append({'date': date.strftime('%b %d'), 'count': count})

    return render_template('admin_dashboard.html',
                         total_users=total_users,
                         total_chats=total_chats,
                         active_today=active_today,
                         recent_users=recent_users,
                         recent_chats=recent_chats,
                         user_growth=user_growth)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/<int:user_id>/toggle')
@login_required
def admin_toggle_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403

    user = User.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({'error': 'Cannot toggle admin user'}), 400

    user.is_active = not user.is_active
    db.session.commit()

    return jsonify({'success': True, 'is_active': user.is_active})

@app.route('/admin/users/<int:user_id>/delete')
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403

    user = User.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({'error': 'Cannot delete admin user'}), 400

    Chat.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True})

@app.route('/admin/chats/<int:user_id>')
@login_required
def admin_user_chats(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)
    chats = Chat.query.filter_by(user_id=user_id).order_by(Chat.created_at.desc()).all()

    return render_template('admin_user_chats.html', user=user, chats=chats)

# ========================================
# AI HELPER FUNCTION - EVOLUTION MEDIA
# ========================================

def get_ai_response(user_message, username):
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    GROQ_API_URL = os.environ.get('GROQ_API_URL', 'https://api.groq.com/openai/v1/chat/completions')

    if not GROQ_API_KEY:
        return get_fallback_response(user_message, username)

    system_prompt = f"""You are Evolution AI, the official assistant for Evolution Media — a technology-driven platform focused on digital innovation, marketing, and education.

About Evolution Media:
- Founded by Emmanuel Okeme, a Computer Science student at Veritas University Abuja
- Specializes in exam tutorials (JAMB, WAEC, NECO), digital empowerment, and tech innovation
- Has helped over 500 students score 270+ in JAMB and secured 700+ admissions into top Nigerian universities (UI, OAU, UNILAG, etc.)
- Hosted Nigeria's biggest English Tutorial in 2025
- Provides practical solutions to modern digital needs

Your personality:
- Encouraging, motivational, and practical
- Keep responses concise and actionable (2-3 paragraphs max)
- Always mention Evolution Media or Emmanuel Okeme when relevant
- Focus heavily on JAMB and WAEC preparation strategies
- Provide specific tips, study techniques, and exam strategies
- Be supportive but direct — students need real advice, not just hype

Remember: You represent Evolution Media. Your goal is to help Nigerian students crush JAMB and WAEC with smart strategies, not just hard work."""

    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': 'llama-3.3-70b-versatile',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message}
        ],
        'temperature': 0.7,
        'max_tokens': 500
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        ai_response = data['choices'][0]['message']['content']
        return ai_response
    except requests.exceptions.Timeout:
        return get_fallback_response(user_message, username) + "\n\n*Note: Response was generated offline due to timeout.*"
    except Exception as e:
        print(f"Groq API Error: {e}")
        return get_fallback_response(user_message, username)

def get_fallback_response(user_message, username):
    user_message_lower = user_message.lower()

    if any(word in user_message_lower for word in ['founder', 'emmanuel', 'owner', 'who created']):
        return "Evolution Media was founded by Emmanuel Okeme, a Computer Science student at Veritas University Abuja. As someone who mastered the JAMB exam himself, his mission is to teach students the exact system he used to succeed. He's built Evolution Media to help Nigerian students achieve outstanding results through quality guidance and resources. 🎓"

    if any(word in user_message_lower for word in ['evolution media', 'your company', 'what is evolution']):
        return "Evolution Media is a technology-driven platform focused on digital innovation, marketing, and education. We provide expert educational services with smooth online transactions and prompt support. Established in 2024, we've already helped over 500 students score 270+ in JAMB and secured 700+ admissions into top Nigerian universities like UI, OAU, and UNILAG. 🚀"

    if 'jamb' in user_message_lower:
        return "For JAMB success, Evolution Media recommends: 1) Focus on past questions — 70% of JAMB repeats patterns, 2) Master your weak subjects first, 3) Take timed mock exams weekly, 4) Join our JAMB tutorial program! Over 500 of our students scored 270+ in 2025. Ready to join the winners? 🎯"

    if 'waec' in user_message_lower:
        return "WAEC requires strategy, not just reading. Evolution Media's approach: 1) Solve past questions religiously, 2) Understand the marking scheme, 3) Practice time management, 4) Take our intensive mock exams. Our students consistently get A's and B's. Want to see our WAEC success blueprint? 📝"

    if 'admission' in user_message_lower or 'university' in user_message_lower:
        return "Getting admission in Nigeria is competitive but very possible. Evolution Media has helped 700+ students secure admission into UI, OAU, UNILAG, and other top universities. We offer personalized admission guidance, course selection help, and CAPS support. Tell me your dream course and let's map out your path! 🏛️"

    if any(word in user_message_lower for word in ['hello', 'hi', 'hey', 'good morning']):
        return f"Hey {username}! Welcome to Evolution Media — your partner in exam success. I'm Evolution AI, here to help you crush JAMB and WAEC with smart strategies. What exam are you preparing for? Let's get you that high score! 😊"

    if any(word in user_message_lower for word in ['study', 'read', 'prepare', 'tips']):
        return "Smart study tip from Evolution Media: Don't just read — practice. Spend 70% of your time solving past questions and 30% reviewing topics you got wrong. This method helped our students average 270+ in JAMB. Which subject do you need help with? 📚"

    return f"Thanks for reaching out to Evolution Media, {username}! Whether you're preparing for JAMB, WAEC, or need admission guidance, we're here to help. Our founder Emmanuel Okeme has created a proven system for exam success. What specific topic or subject can I assist you with today? 🚀📚"

# ========================================
# ERROR HANDLERS
# ========================================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# ========================================
# CREATE TABLES
# ========================================

with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully for Evolution Media!")

    admin_user = User.query.filter_by(is_admin=True).first()
    if not admin_user:
        admin_username = os.environ.get('ADMIN_USERNAME', 'evolution_admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'Evolution2024!')

        admin = User(
            username=admin_username,
            email='admin@evolutionmedia.com',
            full_name='Evolution Media Admin',
            is_admin=True
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin user created: {admin_username} / {admin_password}")

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
