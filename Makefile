.PHONY: help run build rebuild test clean stop logs restart

help:
	@echo "📧 KW Email Reader - Makefile"
	@echo ""
	@echo "Commandes disponibles:"
	@echo "  make run        - Lancer le container (compose)"
	@echo "  make build      - Build l'image Docker"
	@echo "  make rebuild    - Build Docker sans cache"
	@echo "  make test       - Tester la connexion IMAP"
	@echo "  make clean      - Nettoyer les fichiers temporaires"
	@echo "  make stop       - Arrêter le container (compose)"
	@echo "  make logs       - Logs du container (compose)"
	@echo "  make restart    - Redémarrer le container (compose)"

run:
	@echo "🐳 Lancement Docker..."
	docker compose up -d

build:
	@echo "🐳 Build Docker..."
	docker compose up -d --build --force-recreate
	@echo "✅ Container recréé"

rebuild:
	@echo "🐳 Build Docker (no cache)..."
	docker compose build --no-cache
	docker compose up -d --build --force-recreate
	@echo "✅ Container recréé"

stop:
	@echo "🐳 Arrêt Docker..."
	docker compose down

logs:
	@echo "🐳 Logs Docker..."
	docker logs -f kw-mail

restart:
	@echo "🐳 Redémarrage Docker..."
	docker compose restart

test:
	@echo "🔍 Test de la connexion IMAP..."
	docker compose run --rm kw-mail python3 -c "from app.email.imap_client import IMAPClient; from dotenv import load_dotenv; load_dotenv(); c = IMAPClient(); c.connect(); emails = c.get_emails_last_24h(); print(f'✅ {len(emails)} emails trouvés'); c.disconnect()"

clean:
	@echo "🧹 Nettoyage..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Nettoyage terminé"
