import os
from flask import Flask, jsonify, request, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from sqlalchemy import or_

# Charger les variables d'environnement d'un fichier .env au démarrage.
load_dotenv()

# --- Configuration de l'application et de la base de données ---
app = Flask(__name__)
# La variable DATABASE_URL doit être définie dans vos variables d'environnement pour PostgreSQL.
# Exemple: DATABASE_URL="postgresql://user:password@localhost/mydatabase"
# Pour que cela fonctionne, vous devez installer le pilote PostgreSQL: pip install psycopg2-binary
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///nodes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'une_cle_tres_secrete_pour_le_dev')

db = SQLAlchemy(app)


# --- Définition du modèle de base de données ---
class Node(db.Model):
    """
    Représente un nœud dans la hiérarchie. Ce modèle est conçu pour une base de données PostgreSQL.
    Chaque nœud doit avoir un nom en arabe et en français.
    Un nœud peut éventuellement avoir un parent. S'il n'a pas de parent, son parent_id est NULL.
    Les horodatages pour la création et la mise à jour sont gérés automatiquement.
    """
    __tablename__ = 'nodes'

    # Utiliser db.Identity() est la manière moderne et la plus fiable de s'assurer
    # que la séquence d'auto-incrémentation de la clé primaire de PostgreSQL est utilisée.
    id = db.Column(db.Integer, db.Identity(start=1), primary_key=True)
    
    # Mapper explicitement l'attribut Python 'name_ar' à la colonne de base de données 'name_ar'.
    name_ar = db.Column('name_ar', db.String, nullable=False)  # Nom en arabe, requis
    
    # Mapper explicitement 'name_fr' à la colonne de base de données 'name_fr'.
    name_fr = db.Column('name_fr', db.String, nullable=False)  # Nom en français, requis
    
    # Le parent_id est facultatif. S'il n'est pas fourni, il sera NULL, indiquant un nœud racine.
    parent_id = db.Column(db.Integer, db.ForeignKey('nodes.id'), nullable=True)
    
    # Horodatages pour la création et la mise à jour.
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    
    # Relation avec l'ID du parent.
    parent = db.relationship('Node', remote_side=[id])
    
    def __str__(self):
        """
        Représentation textuelle pour l'affichage dans les composants de l'interface utilisateur de Flask-Admin.
        """
        return f"{self.name_ar} / {self.name_fr}"

    def __repr__(self):
        """
        Représentation non ambiguë de l'objet pour le débogage.
        """
        return f"<Node(id={self.id}, name_ar='{self.name_ar}')>"


# --- Configuration de Flask-Admin ---
class NodeAdminView(ModelView):
    """
    Vue d'administration personnalisée pour la gestion des objets 'Node'.
    """
    # Colonnes à afficher dans la vue de liste.
    column_list = ('id', 'name_ar', 'name_fr', 'parent_id', 'created_at', 'updated_at')
    
    # Libellés conviviaux pour les colonnes.
    column_labels = dict(name_ar='Nom Arabe', name_fr='Nom Français', parent_id='Id Parent', created_at='Créé le', updated_at='Mis à jour le')
    
    # Champs consultables dans la vue de liste.
    column_searchable_list = ('name_ar', 'name_fr', 'id')
    
    # Active le tri sur ces colonnes dans la vue de liste de l'administrateur.
    column_sortable_list = ('id', 'name_ar', 'name_fr', 'parent_id', 'created_at', 'updated_at')
    
    # Champs filtrables.
    column_filters = ('name_ar', 'name_fr', 'parent_id', 'created_at', 'updated_at')

    # Configure la liste déroulante AJAX pour la sélection d'un ID parent.
    # Cela permet à l'utilisateur de rechercher un parent par son numéro d'ID ou par son nom.
    form_ajax_refs = {
        'parent': {
            'fields': ('id', 'name_ar', 'name_fr'),
            'page_size': 10
        }
    }

# Initialiser Flask-Admin.
admin = Admin(app, name='Admin', template_mode='bootstrap3')
admin.add_view(NodeAdminView(Node, db.session, name="Nodes"))


# --- Points de terminaison de l'API ---

@app.route('/')
def index():
    """
    Point de terminaison racine qui fournit des informations de base et une liste des points de terminaison disponibles.
    """
    return jsonify({
        'message': 'Le microservice de l\'arborescence des nœuds est en cours d\'exécution',
        'points_de_terminaison': {
            'operations_crud': {
                'creer': 'POST /nodes',
                'modifier': 'PUT /nodes/<id>',
                'supprimer': 'DELETE /nodes/<id>'
            },
            'lecture_parent': 'GET /nodes/<id>/parent',
            'lecture_enfants': 'GET /nodes/<id>/children',
            'recherche': 'GET /nodes/search?q=...'
        },
        'panneau_admin': url_for('admin.index', _external=True)
    }), 200

# --- 1. Opérations CRUD (Ajouter, Modifier, Supprimer) ---

@app.route('/nodes', methods=['POST'])
def create_node():
    """
    Crée un nouveau nœud. 'name_ar' et 'name_fr' sont requis.
    'parent_id' est facultatif. S'il n'est pas fourni, est null ou est 0, il est traité comme un nœud racine.
    """
    data = request.get_json()
    if not data or 'name_ar' not in data or 'name_fr' not in data:
        return jsonify({'error': "Le nom arabe ('name_ar') et le nom français ('name_fr') sont requis"}), 400

    name_ar = data.get('name_ar')
    name_fr = data.get('name_fr')
    parent_id = data.get('parent_id')

    if parent_id == 0:
        parent_id = None

    if parent_id is not None:
        parent_node = db.session.get(Node, parent_id)
        if not parent_node:
            return jsonify({'error': 'Nœud parent non trouvé'}), 404

    new_node = Node(name_ar=name_ar, name_fr=name_fr, parent_id=parent_id)
    db.session.add(new_node)
    db.session.commit()
    return jsonify({
        'id': new_node.id, 
        'name_ar': new_node.name_ar, 
        'name_fr': new_node.name_fr,
        'parent_id': new_node.parent_id,
        'created_at': new_node.created_at.isoformat(),
        'updated_at': new_node.updated_at.isoformat()
    }), 201

@app.route('/nodes/<int:id>', methods=['PUT'])
def update_node(id):
    """
    Met à jour les informations d'un nœud existant. L'ID du nœud ne peut pas être modifié.
    """
    node_to_update = db.session.get(Node, id) or abort(404)
    data = request.get_json()

    if 'name_ar' in data:
        node_to_update.name_ar = data['name_ar']
    if 'name_fr' in data:
        node_to_update.name_fr = data['name_fr']
    if 'parent_id' in data:
        new_parent_id = data.get('parent_id')
        if new_parent_id == 0: # Traiter 0 comme NULL
            new_parent_id = None

        if new_parent_id is not None:
            if new_parent_id == id:
                return jsonify({'error': 'Un nœud ne peut pas être son propre parent'}), 400
            parent_node = db.session.get(Node, new_parent_id)
            if not parent_node:
                return jsonify({'error': 'Nouveau nœud parent non trouvé'}), 404
        node_to_update.parent_id = new_parent_id

    db.session.commit()
    return jsonify({
        'message': 'Mis à jour avec succès', 
        'id': node_to_update.id
    })

@app.route('/nodes/<int:id>', methods=['DELETE'])
def delete_node(id):
    """
    Supprime un nœud. Ses enfants auront leur parent_id mis à NULL,
    devenant ainsi des nœuds racines.
    """
    node_to_delete = db.session.get(Node, id) or abort(404)
    
    # Trouver tous les enfants du nœud en cours de suppression et définir leur parent_id sur None
    children = Node.query.filter_by(parent_id=id).all()
    for child in children:
        child.parent_id = None
        
    db.session.delete(node_to_delete)
    db.session.commit()
    return jsonify({'message': 'Supprimé avec succès'}), 200


# --- 2. Lecture du Parent ---

@app.route('/nodes/<int:id>/parent', methods=['GET'])
def get_parent(id):
    """
    Récupère le parent d'un nœud spécifique.
    """
    node = db.session.get(Node, id) or abort(404)
    parent = node.parent
    if parent:
        return jsonify({
            'id': parent.id, 
            'name_ar': parent.name_ar, 
            'name_fr': parent.name_fr
        }), 200
    return jsonify(None), 200


# --- 3. Lecture des Enfants ---

@app.route('/nodes/<int:id>/children', methods=['GET'])
def get_children(id):
    """
    Récupère tous les enfants immédiats d'un nœud spécifique.
    """
    node = db.session.get(Node, id) or abort(404, description="Nœud non trouvé")
    children = Node.query.filter_by(parent_id=id).all()
    children_list = [{'id': child.id, 'name_ar': child.name_ar, 'name_fr': child.name_fr} for child in children]
    return jsonify(children_list), 200


# --- 4. Recherche ---

@app.route('/nodes/search', methods=['GET'])
def search_nodes():
    """
    Recherche des nœuds par une chaîne de requête, en comparant avec l'ID,
    les noms arabes et français.
    """
    search_term = request.args.get('q', '')
    if not search_term:
        return jsonify([]), 200
    
    filters = [
        Node.name_ar.ilike(f'%{search_term}%'),
        Node.name_fr.ilike(f'%{search_term}%')
    ]

    # Rechercher également par ID si le terme de recherche est un entier valide
    try:
        node_id = int(search_term)
        filters.append(Node.id == node_id)
    except ValueError:
        pass # Le terme de recherche n'est pas un entier, donc nous n'ajoutons pas de filtre ID

    results = Node.query.filter(or_(*filters)).all()
    
    results_list = [{'id': n.id, 'name_ar': n.name_ar, 'name_fr': n.name_fr} for n in results]
    return jsonify(results_list), 200


# --- Bloc d'exécution principal ---
if __name__ == "__main__":
    with app.app_context():
        # Cela créera les tables en fonction de vos modèles si elles n'existent pas.
        db.create_all()
    # Exécuter le serveur de développement Flask.
    app.run(debug=True, port=5000)
