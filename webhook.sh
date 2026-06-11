#!/usr/bin/env bash
# webhook.sh — Manage the Telegram bot webhook URL.
# Usage:
#   ./webhook.sh set          Set webhook to current ngrok URL
#   ./webhook.sh set <url>    Set webhook to a custom URL
#   ./webhook.sh status       Show current webhook status
#   ./webhook.sh delete       Remove the webhook
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load env vars from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
SECRET="${TELEGRAM_WEBHOOK_SECRET:-}"

if [ -z "$BOT_TOKEN" ]; then
    echo "Error: TELEGRAM_BOT_TOKEN not set in .env" >&2
    exit 1
fi

API="https://api.telegram.org/bot${BOT_TOKEN}"

get_ngrok_url() {
    local url
    url=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | \
           python3 -c "import sys,json; tunnels=json.load(sys.stdin)['tunnels']; print([t['public_url'] for t in tunnels if t['proto']=='https'][0])" 2>/dev/null) || true
    if [ -z "$url" ]; then
        echo "Error: ngrok not running. Start it with: ngrok http 8000" >&2
        exit 1
    fi
    echo "$url"
}

set_webhook() {
    local base_url="$1"
    local webhook_url="${base_url}/coins/telegram/webhook/"
    local secret_param=""

    if [ -n "$SECRET" ]; then
        secret_param="&secret_token=${SECRET}"
    fi

    echo "Setting webhook to: $webhook_url"
    curl -s "${API}/setWebhook?url=${webhook_url}${secret_param}" | python3 -m json.tool
    echo ""
}

status_webhook() {
    curl -s "${API}/getWebhookInfo" | python3 -m json.tool
}

delete_webhook() {
    echo "Deleting webhook..."
    curl -s "${API}/deleteWebhook" | python3 -m json.tool
    echo ""
}

case "${1:-}" in
    set)
        if [ -n "${2:-}" ]; then
            URL="$2"
        else
            URL=$(get_ngrok_url)
        fi
        set_webhook "$URL"
        ;;
    status)
        status_webhook
        ;;
    delete)
        delete_webhook
        ;;
    *)
        echo "Usage: $0 {set [url]|status|delete}"
        echo ""
        echo "  set        Set webhook to current ngrok URL"
        echo "  set <url>  Set webhook to a custom URL"
        echo "  status     Show current webhook info"
        echo "  delete     Remove the webhook"
        exit 1
        ;;
esac
