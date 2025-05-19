from flask import Blueprint

mail_bp = Blueprint('mail', __name__, template_folder='templates')

from . import routes 