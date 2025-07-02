# admin_app.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask import redirect
import webbrowser

# Charger les variables d'environnement
load_dotenv()

# Configuration de l'application et de la base de données
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

db = SQLAlchemy(app)

# Définition du modèle Ministere
class Ministere(db.Model):
    __tablename__ = 'ministeres'
    id = db.Column(db.Integer, db.Identity(start=1), primary_key=True)
    name_ar = db.Column('name_ar', db.String, nullable=False)
    name_fr = db.Column('name_fr', db.String, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('ministeres.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    parent = db.relationship('Ministere', remote_side=[id])

    def __str__(self):
        return f"{self.name_ar} / {self.name_fr}"

    def __repr__(self):
        return f"<Ministere(id={self.id}, name_ar='{self.name_ar}')>"

# Vue d'administration personnalisée
class MinistereAdminView(ModelView):
    column_list = ('id', 'name_ar', 'name_fr', 'parent_id', 'created_at', 'updated_at')
    column_labels = {
        'name_ar': 'Nom Arabe',
        'name_fr': 'Nom Français',
        'parent_id': 'Id Parent',
        'created_at': 'Créé le',
        'updated_at': 'Mis à jour le'
    }
    column_searchable_list = ('id', 'name_ar', 'name_fr')
    column_sortable_list = ('id', 'name_ar', 'name_fr', 'parent_id', 'created_at', 'updated_at')
    column_filters = ('name_ar', 'name_fr', 'parent_id', 'created_at', 'updated_at')
    form_ajax_refs = {
        'parent': {
            'fields': ('id', 'name_ar', 'name_fr'),
            'page_size': 10
        }
    }

# Tableau de bord personnalisé
class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
       
        return redirect('/admin/ministere/')

# Create the custom view instance first
ministere_view = MinistereAdminView(Ministere, db.session, name='Ministères')

# Initialize Flask-Admin (without index_view)
admin = Admin(app, name='Admin Ministères', template_mode='bootstrap4')
admin.add_view(ministere_view)

# Optional: Redirect /admin/ to /admin/ministere/
@app.route('/admin/')
def admin_root():
    return redirect('/admin/ministere/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    
    webbrowser.open('http://localhost:5001/admin/ministere/')
app.run(host='0.0.0.0', port=5001, debug=True)
