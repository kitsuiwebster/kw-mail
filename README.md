# KW eMail Reader

Telegram bot for email management via IMAP with AI.

## Quick Start

```bash
make install  # Build Docker image
make run      # Run container
```

## Commands

```bash
make install  # Build Docker image
make run      # Start container
make dev      # Start container (rebuild)
make test     # Test IMAP connection (in container)
make clean    # Clean temp files
```

## Webhook Setup

```bash
# Local (with ngrok)
./scripts/set_webhook_local.sh https://your-ngrok-url.ngrok-free.dev

# VPS
./scripts/set_webhook_vps.sh
```
