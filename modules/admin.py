from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import add_user, get_user, get_user_by_username, db, User, Module, super_admin_required
from modules.module1 import notificar_telegram
from functools import wraps
import secrets

def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acceso denegado: solo administradores", "danger")
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return decorated_view

admin_bp = Blueprint('admin', __name__, template_folder='../templates')

# Dashboard: muestra usuarios y módulos en la misma página (admin.html)
@admin_bp.route('/')
@login_required
@admin_required
def admin_home():
    users = User.query.all()
    modules = Module.query.all()
    return render_template('admin.html', users=users, modules=modules)

# Gestión de Usuarios
@admin_bp.route('/create_user', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    modules = Module.query.all()
    if request.method == 'POST':
        username = request.form.get('username')
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')
        is_admin = True if request.form.get('is_admin') == 'on' else False
        allowed_modules = request.form.getlist('allowed_modules')
        creditos = request.form.get('creditos')
        if not username or not nombre or not email or not password:
            flash("Faltan datos", "danger")
            return redirect(url_for('admin.create_user'))
        if get_user_by_username(username) or User.query.filter_by(email=email).first():
            flash("El usuario ya existe", "danger")
            return redirect(url_for('admin.create_user'))
        add_user(username, nombre, email, password, is_admin, allowed_modules, creditos=creditos)
        flash("Usuario creado correctamente", "success")
        notificar_telegram(f"Nuevo usuario registrado: {username}")
        return redirect(url_for('admin.admin_home'))
    return render_template('create_user.html', modules=modules)

@admin_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = get_user(user_id)
    if user.username == 'admin' and not current_user.username == 'admin':
        flash("No puedes editar al super administrador", "danger")
        return redirect(url_for('admin.admin_home'))
    modules = Module.query.all()
    if not user:
        flash("Usuario no encontrado", "danger")
        return redirect(url_for('admin.admin_home'))
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.nombre = request.form.get('nombre')
        user.email = request.form.get('email')
        user.is_admin = True if request.form.get('is_admin') == 'on' else False
        allowed_modules = request.form.getlist('allowed_modules')
        user.allowed_modules_list = allowed_modules
        user.suspended = True if request.form.get('suspended') == 'on' else False
        new_password = request.form.get('password')
        user.creditos = request.form.get('creditos')
        if new_password:
            user.set_password(new_password)
            user.regenerate_session_token()
        db.session.commit()
        flash("Usuario actualizado", "success")
        notificar_telegram(f"Usuario actualizado: {user.username}")
        return redirect(url_for('admin.admin_home'))
    return render_template('edit_user.html', user=user, modules=modules)

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = get_user(user_id)
    if user:
        if user.id == int(current_user.get_id()):
            flash("No puedes eliminarte a ti mismo", "danger")
            return redirect(url_for('admin.admin_home'))
        elif user.username == 'admin':
            flash("No puedes eliminar al super administrador", "danger")
            return redirect(url_for('admin.admin_home'))
        db.session.delete(user)
        db.session.commit()
        flash("Usuario eliminado", "success")
        notificar_telegram(f"Usuario eliminado: {user.username}")
    else:
        flash("Usuario no encontrado", "danger")
    return redirect(url_for('admin.admin_home'))

@admin_bp.route('/modules/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_module():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        title = request.form.get('title')
        description = request.form.get('description')
        url_endpoint = request.form.get('url_endpoint')
        new_module = Module(identifier=identifier, title=title, description=description, url_endpoint=url_endpoint)
        db.session.add(new_module)
        db.session.commit()
        flash("Módulo creado exitosamente", "success")
        return redirect(url_for('admin.admin_home'))
    return render_template('create_module.html')

@admin_bp.route('/modules/edit/<int:module_id>', methods=['GET', 'POST'])
@super_admin_required
@login_required
@admin_required
def edit_module(module_id):
    module = Module.query.get(module_id)
    if not module:
        flash("Módulo no encontrado", "danger")
        return redirect(url_for('admin.admin_home'))
    if request.method == 'POST':
        module.identifier = request.form.get('identifier')
        module.title = request.form.get('title')
        module.description = request.form.get('description')
        module.url_endpoint = request.form.get('url_endpoint')
        db.session.commit()
        flash("Módulo actualizado", "success")
        return redirect(url_for('admin.admin_home'))
    return render_template('edit_module.html', module=module)

@admin_bp.route('/modules/delete/<int:module_id>', methods=['POST'])
@super_admin_required
@login_required
@admin_required
def delete_module(module_id):
    module = Module.query.get(module_id)
    if module:
        db.session.delete(module)
        db.session.commit()
        flash("Módulo eliminado", "success")
    else:
        flash("Módulo no encontrado", "danger")
    return redirect(url_for('admin.admin_home'))