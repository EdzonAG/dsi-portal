# module6.py
from __future__ import annotations

import io
import os
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_required
from werkzeug.utils import secure_filename

from models import Module, module_permission_required

# Requiere: PyMuPDF
import fitz  # pip install pymupdf


module6_bp = Blueprint("pdf_manager", __name__, template_folder="../templates")


# -------------------------
# Helpers / Config
# -------------------------

ALLOWED_EXTENSIONS = {".pdf"}
MAX_UPLOAD_MB_DEFAULT = 50  # puedes sobrescribir con app.config["PDF_MANAGER_MAX_UPLOAD_MB"]


def _ensure_dirs() -> Tuple[Path, Path]:
    """
    Crea carpetas de trabajo dentro de instance/ para no ensuciar el repo.
    """
    base = Path(current_app.instance_path) / "pdf_manager"
    uploads = base / "uploads"
    outputs = base / "outputs"
    uploads.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    return uploads, outputs


def _max_upload_bytes() -> int:
    mb = int(current_app.config.get("PDF_MANAGER_MAX_UPLOAD_MB", MAX_UPLOAD_MB_DEFAULT))
    return mb * 1024 * 1024


def _is_allowed_pdf(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _save_upload(file_storage) -> Path:
    """
    Guarda el PDF subido y regresa el path.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No se recibió archivo.")

    filename = secure_filename(file_storage.filename)
    if not filename or not _is_allowed_pdf(filename):
        raise ValueError("Archivo inválido. Solo se permiten PDFs.")

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > _max_upload_bytes():
        raise ValueError(
            f"El archivo excede el límite permitido ({_max_upload_bytes()//(1024*1024)} MB)."
        )

    uploads_dir, _ = _ensure_dirs()
    unique = f"{uuid.uuid4().hex}_{filename}"
    out_path = uploads_dir / unique
    file_storage.save(out_path)
    return out_path


def _module_context():
    m = Module.query.filter_by(identifier="pdf_manager").first()
    return dict(
        show_sidebar=True,
        modules=Module.query.all(),
        module_name=m.title if m else "PDF Manager",
        module_description=m.description if m else "Convierte PDFs a imágenes y comprime PDFs.",
    )


# -------------------------
# PDF -> Images
# -------------------------

def _pdf_to_images_zip(
    pdf_path: Path,
    dpi: int = 200,
    img_format: str = "png",
    jpeg_quality: int = 85,
    grayscale: bool = False,
) -> bytes:
    """
    Convierte cada página del PDF a imagen y retorna un ZIP en bytes.
    """
    if dpi < 72 or dpi > 600:
        raise ValueError("DPI fuera de rango (72–600).")

    img_format = img_format.lower().strip()
    if img_format not in {"png", "jpg", "jpeg"}:
        raise ValueError("Formato de imagen inválido. Usa PNG o JPG.")

    if img_format == "jpeg":
        img_format = "jpg"

    if jpeg_quality < 10 or jpeg_quality > 100:
        raise ValueError("Calidad JPG fuera de rango (10–100).")

    doc = fitz.open(pdf_path)
    try:
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i in range(doc.page_count):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                if grayscale:
                    pix = fitz.Pixmap(fitz.csGRAY, pix)

                base_name = f"page_{i+1:04d}.{img_format}"
                img_bytes = pix.tobytes(output=img_format)
                zf.writestr(base_name, img_bytes)

        zip_buffer.seek(0)
        return zip_buffer.read()
    finally:
        doc.close()


# -------------------------
# PDF Compress (GHOSTSCRIPT ONLY)
# -------------------------

def _gs_available() -> Optional[str]:
    # Prioridad: ruta fija (producción) y luego fallback a PATH
    candidates = ["/usr/bin/gs", "/usr/local/bin/gs", "gs"]
    for cmd in candidates:
        if cmd.startswith("/") and Path(cmd).exists():
            return cmd
        if shutil.which(cmd):
            return cmd
    return None


def _compress_pdf_with_ghostscript(
    input_pdf: Path,
    output_pdf: Path,
    preset: str = "ebook",
    dpi: int = 150,
) -> None:
    """
    Compresión con pérdida (reduce imágenes). Requiere Ghostscript instalado.
    preset: screen | ebook | printer | prepress | default
    """
    gs_cmd = _gs_available()
    if not gs_cmd:
        raise RuntimeError("Ghostscript no está instalado o no está en PATH (no se encontró 'gs').")

    preset = preset.lower().strip()
    allowed = {"screen", "ebook", "printer", "prepress", "default"}
    if preset not in allowed:
        raise ValueError("Preset inválido. Usa: screen, ebook, printer, prepress, default.")

    if dpi < 50 or dpi > 300:
        raise ValueError("DPI inválido para compresión (50–300).")

    args = [
        gs_cmd,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{preset}",
        "-dNOPAUSE",
        "-dBATCH",
        "-dSAFER",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        f"-dColorImageResolution={dpi}",
        f"-dGrayImageResolution={dpi}",
        f"-dMonoImageResolution={dpi}",
        f"-sOutputFile={str(output_pdf)}",
        str(input_pdf),
    ]

    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Ghostscript falló: {proc.stderr.strip() or proc.stdout.strip()}")


# -------------------------
# Routes
# -------------------------

@module6_bp.route("/")
@login_required
@module_permission_required("pdf_manager")
def pdf_manager_home():
    return render_template("module6.html", **_module_context())


@module6_bp.route("/pdf-to-images", methods=["POST"])
@login_required
@module_permission_required("pdf_manager")
def pdf_to_images():
    try:
        pdf = request.files.get("pdf_file")
        pdf_path = _save_upload(pdf)

        dpi = int(request.form.get("dpi", "200"))
        img_format = request.form.get("img_format", "png")
        grayscale = request.form.get("grayscale") == "on"
        jpeg_quality = int(request.form.get("jpeg_quality", "85"))

        zip_bytes = _pdf_to_images_zip(
            pdf_path=pdf_path,
            dpi=dpi,
            img_format=img_format,
            jpeg_quality=jpeg_quality,
            grayscale=grayscale,
        )

        download_name = f"{pdf_path.stem}_images.zip"
        return send_file(
            io.BytesIO(zip_bytes),
            mimetype="application/zip",
            as_attachment=True,
            download_name=download_name,
        )

    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("pdf_manager.pdf_manager_home"))


@module6_bp.route("/compress", methods=["POST"])
@login_required
@module_permission_required("pdf_manager")
def compress_pdf():
    try:
        pdf = request.files.get("pdf_file_compress")
        pdf_path = _save_upload(pdf)

        preset = request.form.get("preset", "ebook")
        dpi = int(request.form.get("compress_dpi", "150"))

        _, outputs_dir = _ensure_dirs()
        out_path = outputs_dir / f"{pdf_path.stem}_compressed.pdf"

        in_size = pdf_path.stat().st_size
        _compress_pdf_with_ghostscript(pdf_path, out_path, preset=preset, dpi=dpi)
        out_size = out_path.stat().st_size

        # Si no reduce, avisamos para que el usuario no piense que "no hizo nada".
        if out_size >= in_size:
            flash(
                "Aviso: el PDF resultante no fue más pequeño. Puede que el archivo ya esté optimizado.",
                "warning",
            )

        return send_file(
            str(out_path),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=Path(out_path).name,
        )

    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("pdf_manager.pdf_manager_home"))