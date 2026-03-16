#!/bin/bash
# EC2 instance: c8a.12xlarge (48 vCPUs, 96GB RAM, AMD EPYC 5th gen)
#   Instance ID: i-02d0c8c6970c9915f
#   IP: 44.211.98.254
#
# Launch (or reattach):  ./run.sh ec2-user@44.211.98.254
# Detach:                Ctrl-b d
# Reattach:              ssh -t ec2-user@44.211.98.254 'tmux attach -t maxsat'
# Kill:                  ssh ec2-user@44.211.98.254 'tmux kill-session -t maxsat'
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST="$1"

if [ -n "$HOST" ]; then
  # Refresh API key from local Claude Code login if available
  if [ -f "$HOME/.claude.json" ]; then
    KEY=$(python3 -c "import json; print(json.load(open('$HOME/.claude.json'))['primaryApiKey'])")
    if grep -q "^CLAUDE_CODE_API_KEY=" "$SCRIPT_DIR/.env" 2>/dev/null; then
      sed -i '' "s|^CLAUDE_CODE_API_KEY=.*|CLAUDE_CODE_API_KEY=\"$KEY\"|" "$SCRIPT_DIR/.env"
    else
      echo "CLAUDE_CODE_API_KEY=\"$KEY\"" >> "$SCRIPT_DIR/.env"
    fi
  fi
  ssh "$HOST" "test -f ~/.env" 2>/dev/null || scp "$SCRIPT_DIR/.env" "$HOST":~/
  # Pipe the setup script, then attach to tmux
  ssh "$HOST" 'bash -s' < "$SCRIPT_DIR/run.sh"
  ssh -t "$HOST" 'tmux attach -t maxsat'
  exit 0
fi

# Load secrets
source ~/.env
export ANTHROPIC_API_KEY="$CLAUDE_CODE_API_KEY"

# Install system dependencies
if ! command -v python3.14 &> /dev/null || ! command -v git &> /dev/null; then
  sudo dnf install -y python3.14 python3.14-pip git unzip
fi

# Install Claude Code if not present
if ! command -v claude &> /dev/null; then
  curl -fsSL https://claude.ai/install.sh | bash
fi

# Make python3.14 the default (symlink in /usr/local/bin to avoid breaking dnf)
sudo ln -sf /usr/bin/python3.14 /usr/local/bin/python
sudo ln -sf /usr/bin/python3.14 /usr/local/bin/python3

# Install Python dependencies
python3.14 -m pip install -q python-sat numpy 2>/dev/null || true

# Claude Code settings
mkdir -p ~/.claude
cat > ~/.claude/settings.json <<'EOF'
{"permissions":{"defaultMode":"bypassPermissions"},"model":"opus[1m]","skipDangerousModePermissionPrompt":true}
EOF

# Clone repo (or pull if already cloned)
REPO_DIR="/tmp/np-hard-agent"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull
else
  git clone "https://${GITHUB_ACCESS_TOKEN}@github.com/iliazintchenko/np-hard-agent.git" "$REPO_DIR"
fi

# Git identity
git -C "$REPO_DIR" config user.name "Ilia Zintchenko"
git -C "$REPO_DIR" config user.email "iliazin@gmail.com"

# Download and set up benchmarks if not already present
if [ ! -d "$REPO_DIR/benchmarks/max-sat-2024/mse24-anytime-weighted" ]; then
  mkdir -p "$REPO_DIR/benchmarks/max-sat-2024/mse24-anytime-weighted"
  curl -L -o /tmp/mse24.zip https://www.cs.helsinki.fi/group/coreo/MSE2024-instances/mse24-anytime-weighted.zip
  unzip -o /tmp/mse24.zip -d "$REPO_DIR/benchmarks/max-sat-2024/"
  cd "$REPO_DIR/benchmarks/max-sat-2024"
  for f in *.wcnf.xz; do xz -d "$f" && mv "${f%.xz}" mse24-anytime-weighted/; done
  rm -f /tmp/mse24.zip
fi

# If already running, just reattach
if tmux has-session -t maxsat 2>/dev/null; then
  exit 0
fi

# Install tmux if not present
if ! command -v tmux &> /dev/null; then
  sudo dnf install -y tmux
fi

cd "$REPO_DIR"
LOG="$REPO_DIR/agent.log"

# Launch in tmux: agent log top, costs bottom-left, agent steps bottom-right
tmux new-session -s maxsat -d \
  "claude -p 'Read program.md and go.' --dangerously-skip-permissions --verbose --output-format stream-json 2>&1 | tee $LOG"
tmux split-window -v -t maxsat \
  "tail -f $LOG | jq -r 'select(.type==\"assistant\" and .message.usage) | .message.usage | \"in: \\(.input_tokens) cache: \\(.cache_read_input_tokens) out: \\(.output_tokens)\"'"
tmux split-window -h -t maxsat:0.1 \
  "tail -f $LOG | jq -r 'select(.type==\"assistant\" and .message.content) | .message.content[] | select(.type==\"text\") | .text' 2>/dev/null"
tmux select-pane -t maxsat:0.0
