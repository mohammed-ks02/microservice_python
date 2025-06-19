import os
from flask import Flask, jsonify, request, url_for, abort, render_template
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import or_
from flask_cors import CORS

# Charger les variables d'environnement d'un fichier .env au démarrage.
load_dotenv()

# --- Configuration de l'application et de la base de données ---
app = Flask(__name__, template_folder='templates')
CORS(app) # Active CORS pour autoriser les requêtes de l'interface

# Configuration de la base de données
# La variable DATABASE_URL doit être définie dans vos variables d'environnement pour PostgreSQL.
# Exemple: DATABASE_URL="postgresql://user:password@localhost/mydatabase"
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///nodes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'une_cle_tres_secrete_pour_le_dev')

db = SQLAlchemy(app)


# --- Définition du modèle de base de données ---
class Node(db.Model):
    """
    Représente un nœud dans la hiérarchie.
    """
    __tablename__ = 'nodes'

    id = db.Column(db.Integer, db.Identity(start=1), primary_key=True)
    name_ar = db.Column('name_ar', db.String, nullable=False)
    name_fr = db.Column('name_fr', db.String, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('nodes.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    
    parent = db.relationship('Node', remote_side=[id])
    
    def to_dict(self):
        """Convertit l'objet Node en dictionnaire pour les réponses JSON."""
        return {
            'id': self.id,
            'name_ar': self.name_ar,
            'name_fr': self.name_fr,
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# --- Points de terminaison de l'API ---

@app.route('/')
def admin_panel():
    """
    Sert le panneau d'administration personnalisé (le fichier index.html).
    """
    return render_template('index.html')


# --- 1. Opérations CRUD (Ajouter, Modifier, Supprimer, Lister) ---

@app.route('/nodes', methods=['GET'])
def get_all_nodes():
    """Récupère tous les nœuds de la base de données, triés par ID."""
    nodes = Node.query.order_by(Node.id).all()
    return jsonify([node.to_dict() for node in nodes])


@app.route('/nodes', methods=['POST'])
def create_node():
    """Crée un nouveau nœud."""
    data = request.get_json()
    if not data or 'name_ar' not in data or 'name_fr' not in data:
        return jsonify({'error': "Le nom arabe ('name_ar') et le nom français ('name_fr') sont requis"}), 400

    new_node = Node(
        name_ar=data.get('name_ar'),
        name_fr=data.get('name_fr'),
        parent_id=data.get('parent_id') or None  # Gère les valeurs nulles ou vides
    )
    db.session.add(new_node)
    db.session.commit()
    return jsonify(new_node.to_dict()), 201

@app.route('/nodes/<int:id>', methods=['PUT'])
def update_node(id):
    """Met à jour les informations d'un nœud existant."""
    node_to_update = db.session.get(Node, id) or abort(404)
    data = request.get_json()

    if 'name_ar' in data:
        node_to_update.name_ar = data['name_ar']
    if 'name_fr' in data:
        node_to_update.name_fr = data['name_fr']
    if 'parent_id' in data:
        new_parent_id = data.get('parent_id')
        if new_parent_id is not None and new_parent_id == id:
            return jsonify({'error': 'Un nœud ne peut pas être son propre parent'}), 400
        node_to_update.parent_id = new_parent_id or None

    db.session.commit()
    return jsonify({'message': 'Mis à jour avec succès', 'id': node_to_update.id})

@app.route('/nodes/<int:id>', methods=['DELETE'])
def delete_node(id):
    """Supprime un nœud et met à jour ses enfants."""
    node_to_delete = db.session.get(Node, id) or abort(404)
    
    # Met à jour les enfants pour qu'ils n'aient plus de parent (deviennent des racines).
    Node.query.filter_by(parent_id=id).update({'parent_id': None})
        
    db.session.delete(node_to_delete)
    db.session.commit()
    return jsonify({'message': 'Supprimé avec succès'}), 200


# --- 2. Lecture du Parent ---

@app.route('/nodes/<int:id>/parent', methods=['GET'])
def get_parent(id):
    """Récupère le parent d'un nœud spécifique."""
    node = db.session.get(Node, id) or abort(404)
    parent = node.parent
    if parent:
        return jsonify(parent.to_dict())
    return jsonify(None), 200


# --- 3. Lecture des Enfants ---

@app.route('/nodes/<int:id>/children', methods=['GET'])
def get_children(id):
    """Récupère tous les enfants immédiats d'un nœud spécifique."""
    node = db.session.get(Node, id) or abort(404)
    children = Node.query.filter_by(parent_id=id).all()
    return jsonify([child.to_dict() for child in children]), 200


# --- 4. Recherche ---

@app.route('/nodes/search', methods=['GET'])
def search_nodes():
    """Recherche des nœuds par une chaîne de requête (ID, nom arabe ou nom français)."""
    search_term = request.args.get('q', '')
    if not search_term:
        return jsonify([]), 200
    
    filters = [
        Node.name_ar.ilike(f'%{search_term}%'),
        Node.name_fr.ilike(f'%{search_term}%')
    ]

    # Ajoute la recherche par ID si le terme est un nombre.
    if search_term.isdigit():
        filters.append(Node.id == int(search_term))

    results = Node.query.filter(or_(*filters)).all()
    return jsonify([n.to_dict() for n in results]), 200


# --- Bloc d'exécution principal ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
