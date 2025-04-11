from flask import Blueprint, render_template
from flask_login import login_required
from models import Module, module_permission_required

module0_bp = Blueprint('tutorial', __name__, template_folder='../templates')

@module0_bp.route('/')
@login_required
@module_permission_required('tutorial')
def tutorial_home():
    return render_template('module0.html', show_sidebar=True, modules=Module.query.all())