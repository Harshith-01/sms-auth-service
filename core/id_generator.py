from sqlalchemy import func
from models.sql_models import User, Admin

def generate_user_id(db):
    last_user = db.query(User).order_by(func.length(User.id).desc(), User.id.desc()).first()
    if not last_user:
        return "U1"
    last_number = int(last_user.id[1:])
    return f"U{last_number + 1}"

def generate_admin_id(db):
    last_admin = db.query(Admin).order_by(func.length(Admin.id).desc(), Admin.id.desc()).first()
    if not last_admin:
        return "A1"
    last_number = int(last_admin.id[1:])
    return f"A{last_number + 1}"
