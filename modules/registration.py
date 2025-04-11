from flask import Blueprint, render_template, redirect, url_for, request, flash
from models import add_user, get_user_by_username, User
from modules.module1 import notificar_telegram

registration_bp = Blueprint('registration', __name__, template_folder='../templates')

@registration_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not username or not nombre or not email or not password or not confirm_password:
            flash("Todos los campos son obligatorios", "danger")
            return redirect(url_for('registration.register'))
        if password != confirm_password:
            flash("Las contraseñas no coinciden", "danger")
            return redirect(url_for('registration.register'))
        if get_user_by_username(username) or User.query.filter_by(email=email).first():
            flash("El nombre de usuario o correo ya existen", "danger")
            return redirect(url_for('registration.register'))
        add_user(username, nombre, email, password, is_admin=False, allowed_modules=['tutorial'], suspended=False, creditos=0)
        flash("Registro exitoso. Espera a que un administrador te asigne módulos.", "success")
        notificar_telegram(f"Nuevo usuario registrado: {username}")
        return redirect(url_for('auth.login'))
    return render_template('registration.html')