#!/bin/bash
# EC2 instance: c8a.12xlarge (48 vCPUs, 96GB RAM, AMD EPYC 5th gen)
#   Instance ID: i-02d0c8c6970c9915f
#   IP: 44.211.98.254
#
# Launch (or reattach):  ./run.sh --host ec2-user@44.211.98.254 --agents 3
# Detach:                Ctrl-b d
# Reattach:              ssh -t ec2-user@44.211.98.254 'tmux attach -t ltlsynt'
# Switch agent windows:  Ctrl-b n (next) / Ctrl-b p (prev) / Ctrl-b <number>
# Kill:                  ssh ec2-user@44.211.98.254 'tmux kill-session -t ltlsynt'
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=""
NUM_AGENTS=3

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --agents) NUM_AGENTS="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

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
  ssh "$HOST" "NUM_AGENTS=$NUM_AGENTS bash -s" < "$SCRIPT_DIR/run.sh"
  ssh -t "$HOST" 'tmux attach -t ltlsynt'
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

# Install Spot CLI tools if not present
if ! command -v ltl2tgba &> /dev/null; then
  # Try to install Spot from package manager or compile
  if command -v dnf &> /dev/null; then
    sudo dnf install -y spot || {
      # Build from source if not in repos
      cd /tmp
      curl -L -o spot.tar.gz https://www.lrde.epita.fr/dload/spot/spot-2.14.5.tar.gz
      tar xzf spot.tar.gz
      cd spot-2.14.5
      ./configure --disable-python
      make -j$(nproc)
      sudo make install
      sudo ldconfig
      cd /tmp && rm -rf spot-2.14.5 spot.tar.gz
    }
  fi
fi

# Install syfco if not present
if ! command -v syfco &> /dev/null; then
  if command -v dnf &> /dev/null; then
    sudo dnf install -y ghc cabal-install || true
    cd /tmp
    git clone https://github.com/reactive-systems/syfco.git
    cd syfco
    cabal update && cabal install
    sudo cp ~/.cabal/bin/syfco /usr/local/bin/
    cd /tmp && rm -rf syfco
  fi
fi

# Claude Code settings
mkdir -p ~/.claude
cat > ~/.claude/settings.json <<'EOF'
{"permissions":{"defaultMode":"bypassPermissions"},"model":"opus[1m]","effortLevel":"max","skipDangerousModePermissionPrompt":true}
EOF

NUM_AGENTS="${NUM_AGENTS:-3}"  # passed via env from SSH caller
BENCH_DIR="/tmp/agent-synth-benchmarks"

# Download SYNTCOMP 2025 LTL selection benchmarks once into a shared location
if [ ! -d "$BENCH_DIR/syntcomp-2025/instances" ] || [ -z "$(ls -A "$BENCH_DIR/syntcomp-2025/instances" 2>/dev/null)" ]; then
  mkdir -p "$BENCH_DIR/syntcomp-2025/instances"
  curl -L -o /tmp/selection-ltl-2025v2.zip https://github.com/SYNTCOMP/benchmarks/releases/download/v2025.1/selection-ltl-2025v2.zip
  unzip -o /tmp/selection-ltl-2025v2.zip -d "$BENCH_DIR/syntcomp-2025/"
  # Flatten if extracted into subdirectory
  if [ -d "$BENCH_DIR/syntcomp-2025/selection-ltl-2025" ]; then
    mv "$BENCH_DIR/syntcomp-2025/selection-ltl-2025/"* "$BENCH_DIR/syntcomp-2025/instances/"
    rmdir "$BENCH_DIR/syntcomp-2025/selection-ltl-2025"
  fi
  rm -f /tmp/selection-ltl-2025v2.zip
fi

# Clone repos — each agent gets its own directory
for i in $(seq 1 "$NUM_AGENTS"); do
  REPO_DIR="/tmp/autosynt-$i"
  if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull
  else
    git clone "https://${GITHUB_ACCESS_TOKEN}@github.com/SamKouteili/autosynt.git" "$REPO_DIR"
  fi
  git -C "$REPO_DIR" config user.name "Sam Kouteili"
  git -C "$REPO_DIR" config user.email "sam@kouteili.com"
  # Symlink shared benchmarks into each clone
  rm -rf "$REPO_DIR/benchmarks/syntcomp-2025/instances"
  mkdir -p "$REPO_DIR/benchmarks/syntcomp-2025"
  ln -sf "$BENCH_DIR/syntcomp-2025/instances" "$REPO_DIR/benchmarks/syntcomp-2025/instances"
done

# If already running, just reattach
if tmux has-session -t ltlsynt 2>/dev/null; then
  exit 0
fi

# Install tmux if not present
if ! command -v tmux &> /dev/null; then
  sudo dnf install -y tmux
fi

# Launch tmux session — one window per agent
for i in $(seq 1 "$NUM_AGENTS"); do
  REPO_DIR="/tmp/autosynt-$i"
  LOG="$REPO_DIR/agent.log"
  if [ "$i" -eq 1 ]; then
    tmux new-session -s ltlsynt -n "agent-$i" -d \
      "cd $REPO_DIR && claude -p 'Read program.md and go.' --dangerously-skip-permissions --verbose --output-format stream-json 2>&1 | tee $LOG"
  else
    tmux new-window -t ltlsynt -n "agent-$i" \
      "cd $REPO_DIR && claude -p 'Read program.md and go.' --dangerously-skip-permissions --verbose --output-format stream-json 2>&1 | tee $LOG"
  fi
  # Add monitoring panes: costs bottom-left, agent steps bottom-right
  tmux split-window -v -t "ltlsynt:agent-$i" \
    "tail -f $LOG | jq -r 'select(.type==\"assistant\" and .message.usage) | .message.usage | \"in: \\(.input_tokens) cache: \\(.cache_read_input_tokens) out: \\(.output_tokens)\"'"
  tmux split-window -h -t "ltlsynt:agent-$i.1" \
    "tail -f $LOG | jq -r 'select(.type==\"assistant\" and .message.content) | .message.content[] | select(.type==\"text\") | .text' 2>/dev/null"
  tmux select-pane -t "ltlsynt:agent-$i.0"
done
