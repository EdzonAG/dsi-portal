# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from datetime import datetime


db = SQLAlchemy()
mail = Mail()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    nombre = db.Column(db.String(128), nullable=False)  
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    allowed_modules = db.Column(db.String(128), default="") 
    suspended = db.Column(db.Boolean, default=False)
    creditos = db.Column(db.Integer, default=0)  
    session_token = db.Column(db.String(64), default=lambda: secrets.token_hex(32), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def regenerate_session_token(self):
        self.session_token = secrets.token_hex(32)
        db.session.commit()
        return self.session_token
    
    @property
    def allowed_modules_list(self):
        if self.allowed_modules:
            return self.allowed_modules.split(',')
        return []
    
    @allowed_modules_list.setter
    def allowed_modules_list(self, modules):
        if isinstance(modules, list):
            self.allowed_modules = ','.join(modules)
        else:
            self.allowed_modules = modules

    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return not self.suspended
    
    @property
    def is_anonymous(self):
        return False

def add_user(username, nombre, email, password, is_admin=False, allowed_modules=None, suspended=False, creditos=0, session_token=lambda: secrets.token_hex(32)):
    user = User(username=username, nombre=nombre, email=email, is_admin=is_admin, suspended=suspended, creditos=creditos, session_token=session_token())
    user.set_password(password)
    if allowed_modules:
        user.allowed_modules_list = allowed_modules
    db.session.add(user)
    db.session.commit()
    return user

def get_user(user_id):
    return User.query.get(user_id)

def get_user_by_username(username):
    return User.query.filter_by(username=username).first()

def module_permission_required(module_name):
    def decorator(func):
        @wraps(func)
        @login_required
        def decorated_view(*args, **kwargs):
            if not (current_user.is_admin or module_name in current_user.allowed_modules_list):
                flash("No tienes permiso para acceder a este módulo", "danger")
                return redirect(url_for('index'))
            return func(*args, **kwargs)
        return decorated_view
    return decorator

def super_admin_required(func):
    @wraps(func)
    @login_required
    def decorated_view(*args, **kwargs):
        if current_user.id != 1:
            flash("Acceso denegado: Se requiere permiso de super administrador", "danger")
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return decorated_view


class Module(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(64), unique=True, nullable=False)  # Ej: "calculator"
    title = db.Column(db.String(128), nullable=False)                   # Ej: "Calculadora Básica"
    description = db.Column(db.String(256), nullable=False)               # Ej: "Calculadora básica de operaciones para pruebas de aplicativo"
    url_endpoint = db.Column(db.String(128), nullable=False)              # Ej: "calculator.calculator_home"
    
    
class GeneratedPassword(db.Model):
    __tablename__ = 'generated_passwords'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    password_plain = db.Column(db.String(128), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    
# models.py
class PSPs(db.Model):
    __tablename__ = 'credentials'

    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=True)
    direccion = db.Column(db.String, nullable=True)
    servicio = db.Column(db.String, nullable=True)
    telefono = db.Column(db.String, nullable=True)

    valid = db.Column(db.Boolean, nullable=False, default=True)
    expiration_date = db.Column(db.DateTime, nullable=True)

    # NUEVO: jefe directo (0..1)
    supervisor_id = db.Column(
        db.String,
        db.ForeignKey('credentials.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    supervisor = db.relationship(
        'PSPs',
        remote_side=[id],
        backref=db.backref('subordinates', lazy='dynamic'),
        foreign_keys=[supervisor_id],
        lazy='joined'
    )

    # Utilidades opcionales
    def direct_boss(self):
        return self.supervisor

    def direct_reports(self):
        return self.subordinates.order_by(PSPs.name)

    def director(self):
        """
        Director = el *ancestro* cuyo supervisor es el Director General (que no tiene jefe).
        Si el PSP reporta directo al Director General, el propio PSP es director.
        Si el PSP es el Director General (sin jefe), devuelve None.
        """
        if self.supervisor is None:
            return None
        # Recorremos hacia arriba guardando el anterior
        node = self
        prev = None
        while node.supervisor is not None:
            prev = node
            node = node.supervisor
        # node es el Director General (sin jefe), prev es el director en la cadena
        return prev
