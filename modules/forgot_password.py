# modules/forgot_password.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import db, User, mail
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Message

forgot_bp = Blueprint('forgot', __name__, template_folder='../templates')

def generate_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset-salt')

def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None
    return email

@forgot_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_token(email)
            reset_url = url_for('forgot.reset_password', token=token, _external=True)
            # Enviar email de recuperación
            msg = Message("RECUPERACIÓN DE CONTRASEÑA - PORTAL HERRAMIENTAS SECOMEXT", recipients=[email])
            msg.body = f"Para restablecer tu contraseña, visita el siguiente enlace:\n\n{reset_url}\n\nSi no solicitaste el cambio, ignora este mensaje.\n\nAtentamente,\nEl equipo de soporte de SECOMEXT."
            mail.send(msg)
            flash("Se ha enviado un correo de recuperación de contraseña.", "info")
        else:
            flash("No se encontró una cuenta con ese correo.", "danger")
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html')

@forgot_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = confirm_token(token)
    if not email:
        flash("El enlace de restablecimiento es inválido o ha expirado.", "danger")
        return redirect(url_for('forgot.forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if new_password != confirm_password:
            flash("Las contraseñas no coinciden.", "danger")
            return redirect(url_for('forgot.reset_password', token=token))
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(new_password)
            user.regenerate_session_token()
            db.session.commit()
            flash("Tu contraseña ha sido actualizada. Por favor, inicia sesión.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Usuario no encontrado.", "danger")
            return redirect(url_for('forgot.forgot_password'))
    return render_template('reset_password.html', token=token)