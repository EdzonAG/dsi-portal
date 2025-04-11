# modules/auth.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required
from models import get_user_by_username

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = get_user_by_username(username)
        if user and user.check_password(password):
            if not user.is_active:
                flash("Tu usuario está suspendido. Contacta al administrador.", "danger")
                return redirect(url_for('auth.login'))
            login_user(user)
            session['session_token'] = user.session_token
            flash("Inicio de sesión exitoso", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash("Usuario o contraseña incorrectos", "danger")
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión", "info")
    return redirect(url_for('index'))