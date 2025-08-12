# modules/module5.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required
from models import module_permission_required, Module, PSPs, db
from datetime import date, datetime
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
import unicodedata, io
import re  # <-- añade

STOPWORDS = {
    "de", "del", "la", "las", "el", "los", "y", "e", "en", "para", "por",
    "con", "a", "al", "da", "do", "das", "dos"
}

module5_bp = Blueprint('credenciales', __name__, template_folder='../templates')

BASE_VERIFY_URL = "https://toolbox.secomext.com.mx/credenciales/verify/"

def _parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None

def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def _initials(s: str, *, skip_words=STOPWORDS) -> str:
    """Iniciales en MAYÚSCULAS ignorando stopwords (de, del, y, e, ...)."""
    s = _strip_accents(s or '')
    parts = re.split(r"[\s\-]+", s.strip().lower())
    letters = [p[0] for p in parts if p and p not in skip_words and p[0].isalpha()]
    return ''.join(letters).upper()

def _build_base_id(direccion: str, nombre: str) -> str:
    di = _initials(direccion)  # p.ej. 'DSI' para 'Dirección de Seguridad e Infraestructura'
    ni = _initials(nombre)     # p.ej. 'EOAG' para 'Edzon Omar Alanis González'
    return f"{di}-{ni}" if di and ni else (di or ni or "").upper()

def _unique_id(base_id: str) -> str:
    # Si existe, agrega sufijos -2, -3, ...
    candidate = base_id
    i = 2
    while PSPs.query.get(candidate):
        candidate = f"{base_id}-{i}"
        i += 1
    return candidate

@module5_bp.route('/', methods=['GET'])
@login_required
@module_permission_required('credenciales')
def credenciales_home():
    search = (request.args.get('search') or '').strip()
    query = PSPs.query
    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            PSPs.id.ilike(like),
            PSPs.name.ilike(like),
            PSPs.email.ilike(like),
            PSPs.direccion.ilike(like),
            PSPs.servicio.ilike(like),
            PSPs.telefono.ilike(like),
        ))
    history = query.order_by(PSPs.expiration_date).all()
    return render_template(
        'module5.html',
        show_sidebar=True,
        modules=Module.query.all(),
        history=history,
        search=search,
        module_name=Module.query.filter_by(identifier="credenciales").first().title
    )

@module5_bp.route('/add', methods=['GET', 'POST'])
@login_required
@module_permission_required('credenciales')
def add_psp():
    if request.method == 'POST':
        name_psp  = (request.form.get('name_psp') or '').strip()
        email     = (request.form.get('email') or '').strip()
        direccion = (request.form.get('direccion') or '').strip()
        servicio  = (request.form.get('servicio') or '').strip()
        telefono  = (request.form.get('telefono') or '').strip()
        status    = (request.form.get('status_psp') or 'inactivo').strip().lower()
        exp_str   = (request.form.get('expiration_date_psp') or '').strip()

        if not name_psp or not email or not direccion or not exp_str:
            flash("Nombre, correo, dirección y fecha de expiración son obligatorios.", "danger")
            return redirect(url_for('credenciales.add_psp'))

        exp_dt = _parse_date(exp_str)
        if not exp_dt:
            flash("Formato de fecha inválido. Usa YYYY-MM-DD.", "danger")
            return redirect(url_for('credenciales.add_psp'))

        # ID por defecto: INICIALES_DIRECCION + "-" + INICIALES_NOMBRE, único
        base_id = _build_base_id(direccion, name_psp)
        if not base_id:
            flash("No se pudo generar el ID. Revisa nombre y dirección.", "danger")
            return redirect(url_for('credenciales.add_psp'))
        new_id = _unique_id(base_id)

        try:
            db.session.add(PSPs(
                id=new_id,
                name=name_psp,
                email=email,
                direccion=direccion,
                servicio=servicio,
                telefono=telefono,
                valid=(status == 'activo'),
                expiration_date=exp_dt
            ))
            db.session.commit()
            flash(f"PSP creado correctamente. ID asignado: {new_id}", "success")
            return redirect(url_for('credenciales.credenciales_home'))
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo crear: ID duplicado.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear PSP: {e}", "danger")
        return redirect(url_for('credenciales.add_psp'))

    return render_template(
        'create_credentials.html',
        show_sidebar=True,
        modules=Module.query.all(),
        module_name=Module.query.filter_by(identifier="credenciales").first().title
    )

@module5_bp.route('/verify/<psp_id>', methods=['GET'])
def verify_credentials(psp_id):
    psp = PSPs.query.get((psp_id or '').upper())
    if not psp:
        return render_template('verify_credentials.html', status="invalid", name=None)

    valid = bool(psp.valid)
    if psp.expiration_date and psp.expiration_date.date() < date.today():
        valid = False

    status = "ACTIVO" if valid else "INACTIVO"
    return render_template(
        'verify_credentials.html',
        status=status,
        name=psp.name,
        psp_id=psp.id,
        direccion=psp.direccion,
        servicio=psp.servicio,
        expiration_date=psp.expiration_date
    )

@module5_bp.route('/edit/<psp_id>', methods=['GET'])
@login_required
@module_permission_required('credenciales')
def edit_psp(psp_id):
    psp = PSPs.query.get((psp_id or '').upper())
    if not psp:
        flash("PSP no encontrado.", "danger")
        return redirect(url_for('credenciales.credenciales_home'))
    return render_template('edit_credentials.html', psp=psp, show_sidebar=True, modules=Module.query.all())

@module5_bp.route('/update/<psp_id>', methods=['POST'])
@login_required
@module_permission_required('credenciales')
def update_credentials(psp_id):
    psp = PSPs.query.get((psp_id or '').upper())
    if not psp:
        flash("PSP no encontrado.", "danger")
        return redirect(url_for('credenciales.credenciales_home'))

    name_psp  = (request.form.get('name_psp') or '').strip()
    email     = (request.form.get('email') or '').strip()
    direccion = (request.form.get('direccion') or '').strip()
    servicio  = (request.form.get('servicio') or '').strip()
    telefono  = (request.form.get('telefono') or '').strip()
    status    = (request.form.get('status_psp') or 'inactivo').strip().lower()
    exp_str   = (request.form.get('expiration_date_psp') or '').strip()

    if not name_psp or not email or not direccion or not exp_str:
        flash("Nombre, correo, dirección y fecha de expiración son obligatorios.", "danger")
        return redirect(url_for('credenciales.edit_psp', psp_id=psp.id))

    exp_dt = _parse_date(exp_str)
    if not exp_dt:
        flash("Formato de fecha inválido. Usa YYYY-MM-DD.", "danger")
        return redirect(url_for('credenciales.edit_psp', psp_id=psp.id))

    try:
        psp.name = name_psp
        psp.email = email
        psp.direccion = direccion
        psp.servicio = servicio
        psp.telefono = telefono
        psp.valid = (status == 'activo')
        psp.expiration_date = exp_dt
        db.session.commit()
        flash("PSP actualizado correctamente.", "success")
        return redirect(url_for('credenciales.credenciales_home'))
    except Exception as e:
        db.session.rollback()
        flash(f"Error al actualizar PSP: {e}", "danger")
        return redirect(url_for('credenciales.edit_psp', psp_id=psp.id))

@module5_bp.route('/delete/<psp_id>', methods=['POST'])
@login_required
@module_permission_required('credenciales')
def delete_credentials(psp_id):
    psp = PSPs.query.get((psp_id or '').upper())
    if psp:
        db.session.delete(psp)
        db.session.commit()
        flash("Registro eliminado", "success")
    else:
        flash("Registro no encontrado", "danger")
    return redirect(url_for('credenciales.credenciales_home'))

@module5_bp.route('/qr/<psp_id>', methods=['GET'])
@login_required
@module_permission_required('credenciales')
def qr_psp(psp_id):
    """Genera y descarga el QR con la URL pública de verificación."""
    import segno  # pip install segno
    url = f"{BASE_VERIFY_URL}{(psp_id or '').upper()}"
    qr = segno.make(url, error='m')  # nivel medio
    buf = io.BytesIO()
    qr.save(buf, kind='png', scale=6)
    buf.seek(0)
    filename = f"{(psp_id or 'psp').upper()}_qr.png"
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name=filename)
