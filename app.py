# app.py
import os
from flask import Flask, jsonify, request, abort, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade as migrate_upgrade, init as migrate_init
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import or_, create_engine, text, inspect
from sqlalchemy.engine import url as sa_url
from sqlalchemy.exc import ProgrammingError
import webbrowser


# Charger les variables d'environnement à partir du fichier .env
load_dotenv()

def setup_database():
    """
    Vérifie si la base de données cible existe et la crée si ce n'est pas le cas.
    Cette fonction se connecte à la base de données 'postgres' par défaut pour effectuer l'opération.
    """
    db_url_str = os.getenv('DATABASE_URL')
    if not db_url_str:
        print("ERREUR: La variable d'environnement DATABASE_URL n'est pas définie. Impossible de configurer la base de données.")
        return

    try:
        # Analyse l'URL de la base de données pour en extraire les composants
        db_url = sa_url.make_url(db_url_str)
        db_name = db_url.database

        # Crée une URL pour se connecter à la base de données 'postgres' (ou une autre base par défaut)
        # pour pouvoir créer la base de données cible.
        postgres_engine_url = db_url._replace(database='postgres')
        engine = create_engine(postgres_engine_url, isolation_level='AUTOCOMMIT')

        with engine.connect() as connection:
            # Vérifie si la base de données existe déjà dans le catalogue système de PostgreSQL
            result = connection.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"))
            db_exists = result.scalar() == 1

            if not db_exists:
                print(f"La base de données '{db_name}' n'existe pas. Création en cours...")
                connection.execute(text(f'CREATE DATABASE "{db_name}"'))
                print(f"Base de données '{db_name}' créée avec succès.")
            else:
                print(f"La base de données '{db_name}' existe déjà.")

    except ProgrammingError as e:
        print(f"Erreur de base de données lors de la configuration : {e}")
        print("Veuillez vous assurer que le serveur PostgreSQL est en cours d'exécution et que les informations d'identification dans le fichier .env sont correctes.")
    except Exception as e:
        print(f"Une erreur inattendue est survenue lors de la configuration de la base de données : {e}")
    finally:
        if 'engine' in locals():
            engine.dispose()


# Configuration de l'application Flask
app = Flask(__name__, template_folder='templates')
CORS(app) # Activer CORS pour toutes les routes

# Configuration de la base de données et des clés secrètes à partir des variables d'environnement
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_strong_dev_secret_key')

# Initialisation de SQLAlchemy et Flask-Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db) # Lier Flask-Migrate à l'application et à la base de données

# --- Définition du Modèle de Données ---
class Ministere(db.Model):
    """
    Représente un ministère ou une entité gouvernementale.
    Peut avoir une relation parent-enfant avec d'autres ministères.
    """
    __tablename__ = 'ministeres'
    
    id = db.Column(db.Integer, db.Identity(start=1), primary_key=True)
    name_ar = db.Column('name_ar', db.String, nullable=False)
    name_fr = db.Column(db.String, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('ministeres.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # Relation pour lier un ministère à son parent (auto-référencement)
    parent = db.relationship('Ministere', remote_side=[id])

    def to_dict(self):
        """Convertit l'objet Ministere en un dictionnaire sérialisable en JSON."""
        return {
            'id': self.id,
            'name_ar': self.name_ar,
            'name_fr': self.name_fr,
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# --- Routes de l'API ---

@app.route('/')
def admin_panel():
    """Sert le panneau d'administration principal."""
    return render_template('index2.html')

@app.route('/ministeres', methods=['GET'])
def get_ministeres():
    """Récupère la liste de tous les ministères."""
    minis = Ministere.query.order_by(Ministere.id).all()
    return jsonify([m.to_dict() for m in minis])

@app.route('/ministeres', methods=['POST'])
def create_ministere():
    """Crée un nouveau ministère."""
    data = request.get_json() or {}
    if not data.get('name_ar') or not data.get('name_fr'):
        abort(400, description="'name_ar' et 'name_fr' sont des champs requis.")
    
    m = Ministere(
        name_ar=data['name_ar'],
        name_fr=data['name_fr'],
        parent_id=data.get('parent_id')
    )
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201

@app.route('/ministeres/<int:id>', methods=['PUT'])
def update_ministere(id):
    """Met à jour un ministère existant."""
    m = db.session.get(Ministere, id) or abort(404, description=f"Ministère avec id {id} non trouvé.")
    data = request.get_json() or {}
    
    if 'name_ar' in data:
        m.name_ar = data['name_ar']
    if 'name_fr' in data:
        m.name_fr = data['name_fr']
    if 'parent_id' in data:
        pid = data['parent_id']
        if pid is not None and pid == id:
            abort(400, description='Un ministère ne peut pas être son propre parent.')
        m.parent_id = pid
        
    db.session.commit()
    return jsonify({'message': 'Ministère mis à jour avec succès.', 'id': m.id})

@app.route('/ministeres/<int:id>', methods=['DELETE'])
def delete_ministere(id):
    """Supprime un ministère."""
    m = db.session.get(Ministere, id) or abort(404, description=f"Ministère avec id {id} non trouvé.")
    
    # Met à jour les enfants pour qu'ils n'aient plus de parent avant la suppression
    Ministere.query.filter_by(parent_id=id).update({'parent_id': None})
    
    db.session.delete(m)
    db.session.commit()
    return '', 204

@app.route('/ministeres/<int:id>/parent', methods=['GET'])
def get_parent(id):
    """Récupère le parent d'un ministère spécifique."""
    m = db.session.get(Ministere, id) or abort(404)
    parent = m.parent
    return jsonify(parent.to_dict() if parent else None)

@app.route('/ministeres/<int:id>/children', methods=['GET'])
def get_children(id):
    """Récupère les enfants d'un ministère spécifique."""
    # S'assure que le ministère parent existe
    db.session.get(Ministere, id) or abort(404)
    children = Ministere.query.filter_by(parent_id=id).all()
    return jsonify([c.to_dict() for c in children])

@app.route('/ministeres/search', methods=['GET'])
def search_ministeres():
    """Recherche des ministères par ID, nom arabe ou nom français."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    filters = []
    # Si la requête est un nombre, recherche aussi par ID
    if q.isdigit():
        filters.append(Ministere.id == int(q))
    
    # Recherche insensible à la casse dans les noms
    filters.extend([
        Ministere.name_ar.ilike(f"%{q}%"),
        Ministere.name_fr.ilike(f"%{q}%")
    ])
    
    results = Ministere.query.filter(or_(*filters)).all()
    return jsonify([r.to_dict() for r in results])

# --- Point d'entrée de l'application ---
if __name__ == '__main__':
    # Étape 1: Configurer la base de données (la créer si elle n'existe pas)
    setup_database()
    
    # Étape 2: Appliquer les migrations de la base de données au démarrage
    with app.app_context():
        # S'assure que le dossier de migration est initialisé pour éviter les erreurs
        if not os.path.isdir('migrations'):
            print("Dossier 'migrations' non trouvé. Initialisation en cours...")
            migrate_init()
            print("Initialisation terminée. Vous devez maintenant créer la migration initiale.")
            print("--> Exécutez cette commande dans votre terminal : flask db migrate -m \"Création initiale des tables\"")
            print("--> Puis relancez ce script.")
        else:
            print("Application des migrations de la base de données...")
            migrate_upgrade()
            print("Migrations appliquées avec succès.")

        # Vérifie si la table 'ministeres' existe, sinon la crée
        inspector = inspect(db.engine)
        if 'ministeres' not in inspector.get_table_names():
            print("Table 'ministeres' absente, création en cours...")
            db.create_all()
            print("Table 'ministeres' créée avec succès.")

    # Étape 3: Démarrer l'application Flask
    print("Démarrage de l'application Flask...")
    import os
    import webbrowser
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webbrowser.open('http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=True)
