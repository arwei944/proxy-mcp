#!/bin/bash
# proxy-mcp deploy script
# Usage: ./deploy.sh [commit message]
set -e

REPO="arwei944/proxy-mcp"
GITHUB_API="https://api.github.com/repos/${REPO}"
HF_URL="https://arwei944-proxy-mcp.hf.space"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: GITHUB_TOKEN not set"
    echo "Usage: GITHUB_TOKEN=pat_xxx ./deploy.sh"
    exit 1
fi

MSG="${1:-deploy: $(date +%Y-%m-%d_%H:%M)}"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Pushing to GitHub..."
for f in main.py Dockerfile requirements.txt README.md; do
    [ -f "$DIR/$f" ] || continue
    echo "  $f"
    curl -s -o /dev/null -w "%{http_code}" -X PUT         -H "Authorization: Bearer $GITHUB_TOKEN"         -H "Accept: application/vnd.github.v3+json"         "$GITHUB_API/contents/$f"         -d "{"message":"$MSG","content":"$(base64 -w0 $DIR/$f)"}"
    echo ""
done

# Push index.html via Git Data API
if [ -f "$DIR/static/index.html" ]; then
    echo "  static/index.html"
    python3 -c "
import requests, base64
T='Bearer $GITHUB_TOKEN'
H={'Authorization':T,'Accept':'application/vnd.github.v3+json','X-GitHub-Api-Version':'2022-11-28'}
r=requests.get('https://api.github.com/repos/$REPO/git/ref/heads/main',headers=H).json()
m=r['object']['sha']
t=requests.get(f'https://api.github.com/repos/$REPO/git/commits/{m}',headers=H).json()['tree']['sha']
with open('$DIR/static/index.html','rb') as f: c=f.read()
b=requests.post(f'https://api.github.com/repos/$REPO/git/blobs',headers=H,json={'content':c.decode(),'encoding':'utf-8'}).json()['sha']
nt=requests.post(f'https://api.github.com/repos/$REPO/git/trees',headers=H,json={'base_tree':t,'tree':[{'path':'static/index.html','mode':'100644','type':'blob','sha':b}]}).json()['sha']
cm=requests.post(f'https://api.github.com/repos/$REPO/git/commits',headers=H,json={'message':'$MSG','parents':[m],'tree':nt}).json()['sha']
requests.patch(f'https://api.github.com/repos/$REPO/git/refs/heads/main',headers=H,json={'sha':cm})
print('OK')
"
fi

echo "==> GitHub Actions will auto-deploy to HF Spaces"
echo "==> Waiting 60s for build..."
sleep 60

echo "==> Verifying..."
code=$(curl -s -o /dev/null -w '%{http_code}' $HF_URL/)
echo "  Frontend: HTTP $code"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST $HF_URL/api/tools/proxy_health -H 'Content-Type: application/json' -d '{}')
echo "  API: HTTP $code"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST $HF_URL/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}')
echo "  MCP: HTTP $code"
echo "==> Done! $HF_URL"
