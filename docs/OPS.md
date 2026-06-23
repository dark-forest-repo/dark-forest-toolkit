# Signer Operations Manual

## Installation

```bash
pip install dark-forest
# or from source
pip install -e git+https://github.com/dark-forest-repo/dark-forest-toolkit.git#egg=dark-forest
```

## Quick Start

```bash
# 1. Create an encrypted keystore
df ks init

# 2. Generate or import an account
df ks add alice
# or: df ks import alice 0xYourPrivateKey

# 3. Start the signer
df-signer --rpc https://bsc-dataseed.binance.org --account alice

# 4. Copy the DF_SIGNER_TOKEN from the startup output
# 5. On your agent: export DF_SIGNER_URL=... DF_SIGNER_TOKEN=...
```

## Production Deployment

### Systemd Unit

`/etc/systemd/system/df-signer.service`:

```ini
[Unit]
Description=Dark Forest Signer
After=network.target

[Service]
Type=simple
User=darkforest
Group=darkforest
WorkingDirectory=/home/darkforest
Environment="RPC_URL=https://bsc-dataseed.binance.org"
Environment="PROXY_ADDR=0x..."
Environment="TOKEN_ADDR=0x..."
Environment="MARKET_ADDR=0x..."
Environment="ALLIANCE_ADDR=0x..."
ExecStart=/usr/local/bin/df-signer \
    --rpc "${RPC_URL}" \
    --bind 0.0.0.0 \
    --port 43567 \
    --tls-cert /etc/ssl/df-signer/server.crt \
    --tls-key /etc/ssl/df-signer/server.key \
    --account alice \
    --log-file /var/log/df-signer/audit.log \
    --lock-timeout 3600 \
    --rate-limit 30 \
    --max-retries 3
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable df-signer
sudo systemctl start df-signer
```

### Log Rotation

`/etc/logrotate.d/df-signer`:

```
/var/log/df-signer/audit.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        systemctl kill -s USR1 df-signer || true
    endscript
}
```

### TLS Certificate Setup

```bash
# Generate self-signed cert (development only)
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt \
    -days 365 -nodes -subj "/CN=your-vm-hostname"

# Or use Let's Encrypt (production)
certbot certonly --standalone -d your-vm-hostname

# Copy to signer directory
cp /etc/letsencrypt/live/your-vm/fullchain.pem /etc/ssl/df-signer/server.crt
cp /etc/letsencrypt/live/your-vm/privkey.pem   /etc/ssl/df-signer/server.key
chmod 600 /etc/ssl/df-signer/server.key
chown darkforest:darkforest /etc/ssl/df-signer/
```

### fail2ban Integration

`/etc/fail2ban/filter.d/df-signer.conf`:

```ini
[Definition]
failregex = ^\{"ts":.*"status":401,"msg":"wrong Bearer token".*\}$
ignoreregex =
```

`/etc/fail2ban/jail.local`:

```ini
[df-signer]
enabled = true
port = 43567
filter = df-signer
logpath = /var/log/df-signer/audit.log
maxretry = 5
bantime = 3600
findtime = 600
```

```bash
sudo systemctl restart fail2ban
```

## Firewall Rules

```bash
# Only allow from your agent's IP
sudo ufw allow from $AGENT_IP to any port 43567 proto tcp
```

## Monitoring & Health

```bash
# Check if signer is alive
curl -s https://your-vm:43567/health | jq .

# Detailed health (with token)
curl -s -H "Authorization: Bearer $DF_SIGNER_TOKEN" \
    https://your-vm:43567/health | jq .
```

Response format:
```json
{
  "ok": true,
  "unlocked": true,
  "locked": false,
  "address": "0x...",
  "account": "alice",
  "rate_limit_remaining": 28
}
```

## Recovery Procedures

### Signer Crash
```bash
sudo systemctl restart df-signer
# Check: curl -s https://your-vm:43567/health
```

### Locked by Inactivity
```bash
# Unlock via management endpoint (localhost only)
curl -X POST -H "Authorization: Bearer $DF_SIGNER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"password": "your-keystore-password"}' \
    http://127.0.0.1:43567/unlock
```

### Switch Account
```bash
curl -X POST -H "Authorization: Bearer $DF_SIGNER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"account": "bob"}' \
    http://127.0.0.1:43567/use-account
```

### Emergency Lock
```bash
curl -X POST -H "Authorization: Bearer $DF_SIGNER_TOKEN" \
    http://127.0.0.1:43567/lock
```

## Security Checklist

- [ ] Signer runs on dedicated VM, not shared hosting
- [ ] TLS certificate is valid and not self-signed in production
- [ ] API token is stored in agent's env, never committed to git
- [ ] Target allowlist is enabled (default from env vars)
- [ ] Rate limiting is configured (>0)
- [ ] Auto-lock timeout is set (3600s recommended)
- [ ] Audit log is written to persistent storage
- [ ] fail2ban is enabled for 401 detection
- [ ] Firewall blocks all ports except 43567 from agent IP
- [ ] Systemd unit has `Restart=on-failure`
- [ ] Log rotation is configured
- [ ] Keystore password is strong (16+ chars, stored in password manager)
- [ ] `DF_KEYSTORE_PASS` env var is NOT set in systemd unit (use interactive unlock)
