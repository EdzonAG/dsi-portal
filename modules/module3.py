# modules/module3.py
import os
import uuid
from fpdf import FPDF
from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash, send_from_directory
from flask_login import login_required
from models import Module, module_permission_required, get_user, current_user, db
from modules.module1 import notificar_telegram
import time

module3_bp = Blueprint('minutas', __name__, template_folder='../templates')

@module3_bp.route('/', methods=['GET', 'POST'])
@login_required
@module_permission_required('minutas')
def minutas_home():
    user = get_user(int(current_user.get_id()))
    if request.method == 'POST':
        
        if user.creditos == 0:
            flash("No tienes créditos suficientes para generar minutas", "warning")
            return redirect(url_for('minutas.minutas_home'))
        elif user.creditos > 0:
            user.creditos -= 1
            db.session.commit()
        
        opcion = request.form.get('opcion', '')
        file = request.files.get('archivo')

        # 1. Validar que haya archivo
        if not file or file.filename.strip() == '':
            flash("¡Debes subir un archivo!", "warning")
            return redirect(url_for('minutas.minutas_home'))

        # 2. Validar que coincida con la opción elegida
        #    Usamos 'mimetype' para video/audio y la extensión para .vtt
        if opcion == 'video':
            if not file.mimetype.startswith('video/'):
                flash("El archivo debe ser un video si seleccionaste 'Video'.", "warning")
                return redirect(url_for('minutas.minutas_home'))
        elif opcion == 'audio':
            if not file.mimetype.startswith('audio/'):
                flash("El archivo debe ser un audio si seleccionaste 'Audio'.", "warning")
                return redirect(url_for('minutas.minutas_home'))
        elif opcion == 'transcripcion':
            # Validamos extensión .vtt
            if not file.filename.lower().endswith('.vtt'):
                flash("El archivo debe ser .vtt si seleccionaste 'Transcripción'.", "warning")
                return redirect(url_for('minutas.minutas_home'))
        else:
            flash("Debes seleccionar una fuente válida (Video, Audio o Transcripción).", "warning")
            return redirect(url_for('minutas.minutas_home'))

        # 3. Generar la minuta (PDF) - Ejemplo simple
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Minuta generada a partir de {opcion}", ln=1, align='C')
        pdf.cell(200, 10, txt="(Ejemplo de PDF)", ln=2, align='C')

        # 4. Guardar PDF en 'instance/generated_minutas' con nombre único
        minutas_folder = os.path.join(current_app.instance_path, 'generated_minutas')
        os.makedirs(minutas_folder, exist_ok=True)

        pdf_filename = f"minuta_{uuid.uuid4().hex}.pdf"
        time.sleep(4)  # Simular proceso de generación
        pdf_path = os.path.join(minutas_folder, pdf_filename)
        pdf.output(pdf_path)

        # 5. Flash de éxito
        flash("Minuta generada correctamente. La descarga se iniciará en automático.", "success")
        notificar_telegram(f"El usuario {user.nombre} ha generado una minuta. Créditos restantes: {user.creditos}")

        # 6. Redirigir con el parámetro ?download=pdf_filename
        return redirect(url_for('minutas.minutas_home', download=pdf_filename))

    # Si es GET (o si falló la validación y se redirigió), mostrar formulario
    return render_template('module3.html',
                           user=user,
                           show_sidebar=True, 
                           modules=Module.query.all(),
                           module_name = Module.query.filter_by(identifier="minutas").first().title)

@module3_bp.route('/download/<filename>')
@login_required
@module_permission_required('minutas')
def download_minuta(filename):
    """
    Descarga el PDF guardado en 'instance/generated_minutas/<filename>'
    """
    minutas_folder = os.path.join(current_app.instance_path, 'generated_minutas')
    return send_from_directory(
        directory=minutas_folder,
        path=filename,
        as_attachment=True
    )