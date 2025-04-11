# modules/module4.py
import random, string, hashlib
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from passlib.hash import sha512_crypt
from models import module_permission_required, Module, GeneratedPassword, db

module4_bp = Blueprint('password_generator', __name__, template_folder='../templates')

def generar_contraseña(longitud=12):
    if longitud < 4:
        raise ValueError("La longitud mínima debe ser 4.")
    minus = string.ascii_lowercase
    mayus = string.ascii_uppercase
    nums  = string.digits
    specs = "!@#$%&*"
    # Garantizar al menos uno de cada
    pwd = [
        random.choice(minus),
        random.choice(mayus),
        random.choice(nums),
        random.choice(specs)
    ]
    pool = minus + mayus + nums + specs
    pwd += [random.choice(pool) for _ in range(longitud - 4)]
    random.shuffle(pwd)
    return ''.join(pwd)

def getCodeCR(clave):
    # Genera salt y luego el hash con passlib
    salt = hashlib.md5(clave.encode('utf-8')).hexdigest()[:10]
    hash_full = sha512_crypt.using(rounds=85000, salt=salt).hash(clave)
    # Extraemos la parte que interesa (la 5ª)
    partes = hash_full.split('$')
    return partes[4]

@module4_bp.route('/', methods=['GET', 'POST'])
@login_required
@module_permission_required('password_generator')
def password_generator_home():
    generated_password = None
    password_hash = None

    if request.method == 'POST':
        username = request.form.get('username').strip()
        if not username:
            flash("Debe indicar un nombre de usuario.", "danger")
            return redirect(url_for('password_generator.password_generator_home'))

        # 1) Generar
        generated_password = generar_contraseña(12)
        # 2) Hashear
        password_hash = getCodeCR(generated_password)
        # 3) Guardar en BD
        registro = GeneratedPassword(
            username=username,
            password_plain=generated_password,
            password_hash=password_hash
        )
        db.session.add(registro)
        db.session.commit()
        flash(f"Contraseña generada para '{username}'", "success")

    # 4) Soporta búsqueda por usuario y obtiene las últimas 20 entradas
    search = request.args.get('search', '').strip()
    query = GeneratedPassword.query
    if search:
        # filtro case‑insensitive
        query = query.filter(GeneratedPassword.username.ilike(f"%{search}%"))
    history = (query.order_by(GeneratedPassword.created_at.desc()).limit(20).all())

    return render_template(
        'module4.html',
        show_sidebar=True,
        modules=Module.query.order_by(Module.id).all(),
        generated_password=generated_password,
        password_hash=password_hash,
        history=history,
        search=search
    )
    
@module4_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
@module_permission_required('password_generator')
def delete_password_entry(entry_id):
    entry = GeneratedPassword.query.get(entry_id)
    if entry:
        db.session.delete(entry)
        db.session.commit()
        flash("Entrada eliminada", "success")
    else:
        flash("Registro no encontrado", "danger")
    # preserva el parámetro de búsqueda si existe
    return redirect(url_for('password_generator.password_generator_home', search=request.args.get('search','')))