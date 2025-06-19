# Utilise le shell par défaut de l'utilisateur.
SHELL := /bin/bash

# Nom de l'environnement virtuel.
VENV := venv

# Exécutable Python à l'intérieur de l'environnement virtuel.
PYTHON := $(VENV)/bin/python

# --- Cibles principales ---

.PHONY: help
help:
	@echo "Commandes disponibles:"
	@echo "  make install    -> Installe les dépendances dans un environnement virtuel."
	@echo "  make run        -> Démarre le serveur de développement Flask."
	@echo "  make clean      -> Supprime les fichiers temporaires et le cache."
	@echo "  make reset-db   -> Supprime le fichier de la base de données SQLite (pour le développement)."

.PHONY: install
install: $(VENV)/bin/activate
$(VENV)/bin/activate: requirements.txt
	@echo "Création de l'environnement virtuel..."
	test -d $(VENV) || python3 -m venv $(VENV)
	@echo "Installation des dépendances..."
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	@echo ""
	@echo "Installation terminée. Activez l'environnement avec : source $(VENV)/bin/activate"

.PHONY: run
run:
	@echo "Démarrage du serveur Flask sur http://127.0.0.1:5000"
	@$(PYTHON) app.py

.PHONY: clean
clean:
	@echo "Nettoyage des fichiers temporaires..."
	@rm -rf `find . -name __pycache__`
	@rm -f `find . -type f -name '*.py[co]' `
	@rm -f `find . -type f -name '*~' `
	@rm -f `find . -type f -name '.*~' `
	@echo "Nettoyage terminé."

.PHONY: reset-db
reset-db:
	@echo "Réinitialisation de la base de données de développement (nodes.db)..."
	@rm -f nodes.db
	@echo "Base de données supprimée."

