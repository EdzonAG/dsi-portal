# modules/module5.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from models import module_permission_required, Module, PSPs, db
from datetime import date, datetime
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

module5_bp = Blueprint('credenciales', __name__, template_folder='../templates')

def _parse_date(value: str):
    """Convierte 'YYYY-MM-DD' a datetime (00:00:00)."""
    try:
        d = datetime.strptime(value, "%Y-%m-%d")  # naive (local)
        return d
    except Exception:
        return None

@module5_bp.route('/', methods=['GET', 'POST'])
@login_required
@module_permission_required('credenciales')
def credenciales_home():
    # --- Alta rápida (POST) ---
    if request.method == 'POST':
        id_psp = (request.form.get('id_psp') or '').strip()
        name_psp = (request.form.get('name_psp') or '').strip()
        status_psp = (request.form.get('status_psp') or 'inactivo').strip().lower()
        exp_str = (request.form.get('expiration_date_psp') or '').strip()

        # Normalizaciones
        id_psp = id_psp.upper()
        valid = 1 if status_psp == 'activo' else 0
        exp_dt = _parse_date(exp_str)

        # Validaciones mínimas
        if not id_psp or not name_psp or not exp_dt:
            flash("Completa todos los campos.", "danger")
            return redirect(url_for('credenciales.credenciales_home'))

        # Regla: ID solo letras (como ya aplica el pattern del form)
        if not id_psp.isalpha() or len(id_psp) > 4:
            flash("El ID PSP debe ser de hasta 4 letras.", "danger")
            return redirect(url_for('credenciales.credenciales_home'))

        try:
            # Evitar duplicados por ID
            if PSPs.query.get(id_psp):
                flash("Ya existe un PSP con ese ID.", "warning")
                return redirect(url_for('credenciales.credenciales_home'))

            new_psp = PSPs(
                id=id_psp,
                name=name_psp,
                valid=valid,
                expiration_date=exp_dt
            )
            db.session.add(new_psp)
            db.session.commit()
            flash("PSP creado correctamente.", "success")
            return redirect(url_for('credenciales.credenciales_home'))
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo crear: ID duplicado.", "danger")
            return redirect(url_for('credenciales.credenciales_home'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear PSP: {e}", "danger")
            return redirect(url_for('credenciales.credenciales_home'))

    # --- Listado + búsqueda (GET) ---
    search = (request.args.get('search') or '').strip()
    query = PSPs.query
    if search:
        like = f"%{search}%"
        query = query.filter(or_(PSPs.id.ilike(like), PSPs.name.ilike(like)))

    history = query.order_by(PSPs.expiration_date).all()

    return render_template(
        'module5.html',
        show_sidebar=True,
        modules=Module.query.all(),
        history=history,
        search=search
    )

@module5_bp.route('/verify/<psp_id>', methods=['GET'])
# @login_required
# @module_permission_required('credenciales')
def verify_credentials(psp_id):
    psp = PSPs.query.get(psp_id.upper())
    if not psp:
        # status="invalid" dispara el card rojo en la vista
        return render_template('verify_credentials.html', status="invalid", name=None)

    name = psp.name
    exp = psp.expiration_date
    valid = psp.valid

    # Revalida por fecha
    if exp is not None and exp.date() < date.today():
        valid = 0

    status = "ACTIVO" if valid else "INACTIVO"

    return render_template(
        'verify_credentials.html',
        status=status,
        name=name,
        psp_id=psp.id,
        expiration_date=exp  # la vista lo formatea a YYYY-MM-DD
    )

@module5_bp.route('/edit/<psp_id>', methods=['GET'])
@login_required
@module_permission_required('credenciales')
def edit_psp(psp_id):
    psp = PSPs.query.get(psp_id.upper())
    if not psp:
        flash("PSP no encontrado.", "danger")
        return redirect(url_for('credenciales.credenciales_home'))
    return render_template(
        'edit_credentials.html',
        psp=psp,
        show_sidebar=True,
        modules=Module.query.all()
    )

@module5_bp.route('/update/<psp_id>', methods=['POST'])
@login_required
@module_permission_required('credenciales')
def update_credentials(psp_id):
    psp = PSPs.query.get(psp_id.upper())
    if not psp:
        flash("PSP no encontrado.", "danger")
        return redirect(url_for('credenciales.credenciales_home'))

    name_psp = (request.form.get('name_psp') or '').strip()
    status_psp = (request.form.get('status_psp') or 'inactivo').strip().lower()
    exp_str = (request.form.get('expiration_date_psp') or '').strip()

    if not name_psp or not exp_str:
        flash("Nombre y fecha de expiración son obligatorios.", "danger")
        return redirect(url_for('credenciales.edit_psp', psp_id=psp.id))

    exp_dt = _parse_date(exp_str)
    if not exp_dt:
        flash("Formato de fecha inválido. Usa YYYY-MM-DD.", "danger")
        return redirect(url_for('credenciales.edit_psp', psp_id=psp.id))

    try:
        psp.name = name_psp
        psp.valid = 1 if status_psp == 'activo' else 0
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
    psp = PSPs.query.get(psp_id.upper())
    if psp:
        db.session.delete(psp)
        db.session.commit()
        flash("Registro eliminado", "success")
    else:
        flash("Registro no encontrado", "danger")
    return redirect(url_for('credenciales.credenciales_home'))
