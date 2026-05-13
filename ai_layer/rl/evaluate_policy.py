"""
evaluate_policy.py
Evaluates the trained RL policy against the rule-based baseline.

Since we can't hook the policy into the C++ engine in real-time
(offline RL limitation), we evaluate it statistically:
  1. Load validation experience
  2. For each state, compare policy action vs rule-based action
  3. Compute expected reward under each policy
  4. Show decision boundary analysis
"""

import json
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

EXPERIENCE_FILE = "ai_layer/rl/experience.json"
MODEL_FILE      = "ai_layer/rl/policy.pt"
MEAN_FILE       = "ai_layer/rl/state_mean.npy"
STD_FILE        = "ai_layer/rl/state_std.npy"

# ── Load model ─────────────────────────────────────────────────
class PolicyNet(nn.Module):
    def __init__(self, state_dim=6, n_actions=3, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(hidden, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(hidden, hidden // 2),
            nn.LayerNorm(hidden // 2),
            nn.GELU(),
            nn.Linear(hidden // 2, n_actions),
        )
    def forward(self, x): return self.net(x)

model = PolicyNet()
model.load_state_dict(torch.load(MODEL_FILE))
model.eval()

state_mean = np.load(MEAN_FILE)
state_std  = np.load(STD_FILE)

print("Loading experience...")
with open(EXPERIENCE_FILE) as f:
    data = json.load(f)

states  = np.array([d["state"]  for d in data], dtype=np.float32)
actions = np.array([d["action"] for d in data], dtype=np.int64)
rewards = np.array([d["reward"] for d in data], dtype=np.float32)
print(f"  {len(states):,} samples")

# ── Get policy predictions ─────────────────────────────────────
states_norm = (states - state_mean) / (state_std + 1e-8)
with torch.no_grad():
    logits = model(torch.tensor(states_norm))
    policy_actions = logits.argmax(1).numpy()
    policy_probs   = torch.softmax(logits, dim=1).numpy()

# ── Expected reward comparison ─────────────────────────────────
# Rule-based: uses the actual actions taken (with their rewards)
# RL policy: uses policy-predicted actions mapped to expected rewards

# Build reward lookup per action from data
reward_per_action = {}
for a in [0, 1, 2]:
    mask = actions == a
    if mask.sum() > 0:
        reward_per_action[a] = rewards[mask].mean()
    else:
        reward_per_action[a] = 0.0

rule_reward   = rewards.mean()
policy_reward = np.array([reward_per_action[a]
                           for a in policy_actions]).mean()

print(f"\n{'='*50}")
print(f"  Rule-based expected reward : {rule_reward:>8.4f}")
print(f"  RL policy expected reward  : {policy_reward:>8.4f}")
delta = policy_reward - rule_reward
print(f"  Delta                      : {delta:>+8.4f} "
      f"({'better' if delta > 0 else 'worse'})")
print(f"{'='*50}")

# ── Decision analysis ──────────────────────────────────────────
print("\nPolicy action distribution:")
for a, label in [(0,"DELIVER"),(1,"RECHARGE"),(2,"WAIT")]:
    rb_count  = (actions         == a).sum()
    rl_count  = (policy_actions  == a).sum()
    print(f"  {label:8s}: rule={rb_count:>6,} ({rb_count/len(actions)*100:.1f}%)  "
          f"rl={rl_count:>6,} ({rl_count/len(policy_actions)*100:.1f}%)")

# ── Battery threshold analysis ─────────────────────────────────
print("\nRecharge decision by battery level:")
print("  Battery range  | Rule-based RECHARGE% | RL RECHARGE%")
print("  " + "-"*52)
for lo, hi in [(0,10),(10,20),(20,30),(30,50),(50,100)]:
    mask = (states[:,0]*100 >= lo) & (states[:,0]*100 < hi)
    if mask.sum() == 0: continue
    rb_rech = (actions[mask]        == 1).mean() * 100
    rl_rech = (policy_actions[mask] == 1).mean() * 100
    print(f"  {lo:>3}-{hi:<3}%        | {rb_rech:>20.1f}% | {rl_rech:>12.1f}%")

# ── Plot ───────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.patch.set_facecolor("#0f1117")
fig.suptitle("RL Policy vs Rule-Based Agent — Decision Analysis",
             color="white", fontsize=13, fontweight="bold")

BG, CARD = "#0f1117", "#1a1a2e"
BLUE, GRN, RED = "#3a7bd5", "#2ecc71", "#e74c3c"

# Plot 1: Action distribution comparison
ax = axes[0]
ax.set_facecolor(CARD)
labels  = ["DELIVER", "RECHARGE", "WAIT"]
rb_dist = [float((actions == a).sum()) for a in range(3)]
rl_dist = [float((policy_actions == a).sum()) for a in range(3)]
x = np.arange(3)
ax.bar(x-0.2, rb_dist, 0.4, label="Rule-based", color=RED,  alpha=0.8)
ax.bar(x+0.2, rl_dist, 0.4, label="RL policy",  color=GRN,  alpha=0.8)
ax.set_xticks(x)
ax.set_xticklabels(labels, color="white")
ax.set_title("Action Distribution", color="white")
ax.set_ylabel("Count", color="white")
ax.tick_params(colors="white")
ax.legend(facecolor=CARD, labelcolor="white")
for s in ax.spines.values(): s.set_edgecolor("#333355")

# Plot 2: RECHARGE probability vs battery level
ax = axes[1]
ax.set_facecolor(CARD)
battery_vals = states[:, 0] * 100
bins = np.linspace(0, 100, 20)
rb_rech_by_batt, rl_rech_by_batt, bin_centres = [], [], []
for i in range(len(bins)-1):
    mask = (battery_vals >= bins[i]) & (battery_vals < bins[i+1])
    if mask.sum() < 5: continue
    rb_rech_by_batt.append((actions[mask] == 1).mean())
    rl_rech_by_batt.append((policy_actions[mask] == 1).mean())
    bin_centres.append((bins[i] + bins[i+1]) / 2)

ax.plot(bin_centres, rb_rech_by_batt, 'o-', color=RED,
        label="Rule-based", linewidth=2)
ax.plot(bin_centres, rl_rech_by_batt, 's-', color=GRN,
        label="RL policy",  linewidth=2)
ax.axvline(20, color="white", linestyle="--", alpha=0.5,
           label="Rule threshold (20%)")
ax.set_title("Recharge Rate vs Battery %", color="white")
ax.set_xlabel("Battery %", color="white")
ax.set_ylabel("P(RECHARGE)", color="white")
ax.tick_params(colors="white")
ax.legend(facecolor=CARD, labelcolor="white", fontsize=8)
for s in ax.spines.values(): s.set_edgecolor("#333355")

# Plot 3: Policy confidence (max probability)
ax = axes[2]
ax.set_facecolor(CARD)
confidence = policy_probs.max(axis=1)
ax.hist(confidence, bins=30, color=BLUE, alpha=0.85, edgecolor="white")
ax.axvline(confidence.mean(), color=GRN, linestyle="--",
           label=f"Mean: {confidence.mean():.2f}")
ax.set_title("Policy Confidence", color="white")
ax.set_xlabel("Max action probability", color="white")
ax.set_ylabel("Count", color="white")
ax.tick_params(colors="white")
ax.legend(facecolor=CARD, labelcolor="white")
for s in ax.spines.values(): s.set_edgecolor("#333355")

plt.tight_layout()
plt.savefig("data/logs/rl_evaluation.png", dpi=150,
            facecolor=BG, bbox_inches="tight")
print("\nSaved -> data/logs/rl_evaluation.png")
