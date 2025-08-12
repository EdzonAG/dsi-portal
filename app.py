# app.py
from flask import Flask, render_template, redirect, url_for, flash, session
from flask_login import LoginManager, current_user, logout_user
from modules.module0 import module0_bp
from modules.module1 import module1_bp
from modules.module2 import module2_bp
from modules.module3 import module3_bp
from modules.module4 import module4_bp
from modules.module5 import module5_bp
from modules.auth import auth_bp
from modules.admin import admin_bp
from modules.registration import registration_bp
from modules.forgot_password import forgot_bp
from models import db, get_user, User, add_user, mail, Module
import json

with open("./instance/tokens.json") as f:
    config = json.load(f)

app = Flask(__name__)

app.secret_key = config['app_secret_key']

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portal_dsi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = config['MAIL_USERNAME']
app.config['MAIL_PASSWORD'] = config['MAIL_PASSWORD']
app.config['MAIL_DEFAULT_SENDER'] = config['MAIL_USERNAME']

# Inicializar extensiones
db.init_app(app)
mail.init_app(app)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        add_user("admin", "Administrador SECOMEXT", "edzon.alanis@secomext.com.mx", "S3c0m3xt.2025**", 
                is_admin=True, allowed_modules=['all_modules'])

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return get_user(user_id)

# Registro de Blueprints
app.register_blueprint(module0_bp, url_prefix="/tutorial")
app.register_blueprint(module1_bp, url_prefix="/publisher")
app.register_blueprint(module2_bp, url_prefix="/tokens")
app.register_blueprint(module3_bp, url_prefix="/minutas")
app.register_blueprint(module4_bp, url_prefix="/password_generator")
app.register_blueprint(module5_bp, url_prefix="/credenciales")
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(registration_bp, url_prefix="/auth")
app.register_blueprint(forgot_bp, url_prefix="/auth")

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            modules = Module.query.order_by(Module.id).all()
        else:
            allowed_ids = current_user.allowed_modules_list
            modules = Module.query.filter(Module.identifier.in_(allowed_ids)).order_by(Module.id).all()
    else:
        modules = None
    return render_template('index.html', modules=modules)

@app.before_request
def check_if_suspended():
    # Solo actuamos si hay un usuario logueado
    if current_user.is_authenticated:
        # 1) Token de sesión
        token = session.get('session_token')
        if not token or token != current_user.session_token:
            flash("Su sesión ha expirado. Por favor, inicie sesión de nuevo.", "info")
            logout_user()
            return redirect(url_for('auth.login'))

        # 2) Suspensión de cuenta
        if not current_user.is_active:
            flash("Tu cuenta ha sido suspendida. Contacta a DSI para solucionarlo.", "danger")
            logout_user()
            return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(host="localhost", port=8000, debug=True)
