.PHONY: help install run dev test clean stop

help:
	@echo "📧 KW Email Reader - Makefile"
	@echo ""
	@echo "Commandes disponibles:"
	@echo "  make install    - Installer les dépendances"
	@echo "  make run        - Lancer le serveur"
	@echo "  make dev        - Lancer le serveur en mode dev (auto-reload)"
	@echo "  make test       - Tester la connexion IMAP"
	@echo "  make clean      - Nettoyer les fichiers temporaires"
	@echo "  make stop       - Stopper les processus uvicorn du projet"

install:
	@echo "📦 Installation des dépendances..."
	pip install -r requirements.txt
	@echo "✅ Dépendances installées"

run:
	@echo "🚀 Démarrage du serveur..."
	. .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	@echo "🚀 Démarrage du serveur en mode dev (auto-reload)..."
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

stop:
	@echo "🛑 Arrêt des processus uvicorn..."
	@pkill -f "uvicorn app.main:app" || true
	@echo "✅ Uvicorn stoppé (si présent)"

test:
	@echo "🔍 Test de la connexion IMAP..."
	python3 -c "from app.email.imap_client import IMAPClient; from dotenv import load_dotenv; load_dotenv(); c = IMAPClient(); c.connect(); emails = c.get_emails_last_24h(); print(f'✅ {len(emails)} emails trouvés'); c.disconnect()"

clean:
	@echo "🧹 Nettoyage..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Nettoyage terminé"
