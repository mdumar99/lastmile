"""
train_policy.py
Behavioural cloning with aggressive rebalancing.
Strategy:
  - Undersample DELIVER to 5x the minority class size
  - Reward-weighted loss: weight each sample by |reward| + epsilon
  - Larger network, more regularisation
"""

import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import os

EXPERIENCE_FILE = "ai_layer/rl/experience.json"
MODEL_OUT       = "ai_layer/rl/policy.pt"
EPOCHS          = 80
BATCH_SIZE      = 128
LR              = 3e-4
HIDDEN          = 256

print("Loading experience...")
with open(EXPERIENCE_FILE) as f:
    data = json.load(f)

states  = np.array([d["state"]  for d in data], dtype=np.float32)
actions = np.array([d["action"] for d in data], dtype=np.int64)
rewards = np.array([d["reward"] for d in data], dtype=np.float32)

print(f"  {len(states):,} raw samples")

# ── Rebalance: cap DELIVER at 5x minority ─────────────────────
idx_deliver  = np.where(actions == 0)[0]
idx_recharge = np.where(actions == 1)[0]
idx_wait     = np.where(actions == 2)[0]

minority_size = max(len(idx_recharge), len(idx_wait))
cap           = minority_size * 5

np.random.seed(42)
idx_deliver_sub = np.random.choice(idx_deliver, size=cap, replace=False)
idx_all = np.concatenate([idx_deliver_sub, idx_recharge, idx_wait])
np.random.shuffle(idx_all)

states  = states[idx_all]
actions = actions[idx_all]
rewards = rewards[idx_all]

print(f"  {len(states):,} samples after rebalancing")
print(f"  Action dist: {np.bincount(actions)}")

# ── Normalise states ───────────────────────────────────────────
state_mean = states.mean(axis=0)
state_std  = states.std(axis=0) + 1e-8
states     = (states - state_mean) / state_std

# Save normalisation params for inference
np.save("ai_layer/rl/state_mean.npy", state_mean)
np.save("ai_layer/rl/state_std.npy",  state_std)

# ── Train/val split ────────────────────────────────────────────
X_train, X_val, y_train, y_val, r_train, r_val = train_test_split(
    states, actions, rewards,
    test_size=0.2, random_state=42, stratify=actions
)
print(f"  Train: {len(X_train):,}  Val: {len(X_val):,}")

# ── Dataset with sample weights ────────────────────────────────
class ExperienceDataset(Dataset):
    def __init__(self, states, actions, rewards):
        self.states  = torch.tensor(states)
        self.actions = torch.tensor(actions)
        self.weights = torch.tensor(
            np.abs(rewards) + 0.1, dtype=torch.float32)

    def __len__(self): return len(self.states)
    def __getitem__(self, i):
        return self.states[i], self.actions[i], self.weights[i]

train_ds = ExperienceDataset(X_train, y_train, r_train)
val_ds   = ExperienceDataset(X_val,   y_val,   r_val)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False)

# ── Policy network ─────────────────────────────────────────────
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

    def predict(self, state_np, mean, std):
        with torch.no_grad():
            s = torch.tensor(
                (state_np - mean) / (std + 1e-8),
                dtype=torch.float32).unsqueeze(0)
            return int(self.forward(s).argmax(1).item())

device = torch.device("cpu")
model  = PolicyNet(hidden=HIDDEN).to(device)

criterion = nn.CrossEntropyLoss(reduction='none')
optimiser = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimiser, max_lr=LR,
    steps_per_epoch=len(train_loader), epochs=EPOCHS)

# ── Training loop ──────────────────────────────────────────────
print(f"\nTraining {EPOCHS} epochs, {sum(p.numel() for p in model.parameters()):,} params")

best_macro_f1 = 0.0

for epoch in range(EPOCHS):
    model.train()
    total_loss = 0.0
    for states_b, actions_b, weights_b in train_loader:
        states_b  = states_b.to(device)
        actions_b = actions_b.to(device)
        weights_b = weights_b.to(device)

        optimiser.zero_grad()
        logits = model(states_b)
        loss   = (criterion(logits, actions_b) * weights_b).mean()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimiser.step()
        scheduler.step()
        total_loss += loss.item()

    # Validation
    if (epoch + 1) % 10 == 0:
        model.eval()
        all_preds, all_true = [], []
        with torch.no_grad():
            for states_b, actions_b, _ in val_loader:
                preds = model(states_b.to(device)).argmax(1).cpu().numpy()
                all_preds.extend(preds)
                all_true.extend(actions_b.numpy())

        from sklearn.metrics import f1_score
        macro_f1 = f1_score(all_true, all_preds, average='macro',
                            zero_division=0)
        acc = np.mean(np.array(all_preds) == np.array(all_true))
        print(f"  Epoch {epoch+1:>3}/{EPOCHS}  "
              f"loss={total_loss/len(train_loader):.4f}  "
              f"acc={acc:.3f}  macro_f1={macro_f1:.3f}")

        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            torch.save(model.state_dict(), MODEL_OUT)

print(f"\nBest macro F1: {best_macro_f1:.3f}")

# ── Final report ───────────────────────────────────────────────
print("\nClassification report (validation set):")
model.load_state_dict(torch.load(MODEL_OUT))
model.eval()
all_preds, all_true = [], []
with torch.no_grad():
    for states_b, actions_b, _ in val_loader:
        preds = model(states_b.to(device)).argmax(1).cpu().numpy()
        all_preds.extend(preds)
        all_true.extend(actions_b.numpy())

print(classification_report(
    all_true, all_preds,
    target_names=["DELIVER", "RECHARGE", "WAIT"],
    zero_division=0
))
print(f"Model saved -> {MODEL_OUT}")
