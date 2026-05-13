"""
train_policy_v2.py
Trains policy on 9-feature state space with 363k samples.
Tries 3 architectures and keeps the best by macro F1.

Architecture A: MLP-256 (baseline, same as v1 but larger data)
Architecture B: MLP-512 (deeper)
Architecture C: Residual MLP (skip connections)
"""

import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score
import os

EXPERIENCE_FILE = "ai_layer/rl/experience_v2.json"
MODEL_OUT       = "ai_layer/rl/policy_v2.pt"
EPOCHS          = 60
BATCH_SIZE      = 512
LR              = 3e-4
RANDOM_SEED     = 42
torch.manual_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

print("Loading experience...")
with open(EXPERIENCE_FILE) as f:
    data = json.load(f)

states  = np.array([d["state"]  for d in data], dtype=np.float32)
actions = np.array([d["action"] for d in data], dtype=np.int64)
rewards = np.array([d["reward"] for d in data], dtype=np.float32)
print(f"  {len(states):,} samples, {states.shape[1]} features")
print(f"  Action dist: {np.bincount(actions)}")

# ── Rebalance ─────────────────────────────────────────────────
idx_0 = np.where(actions == 0)[0]
idx_1 = np.where(actions == 1)[0]
idx_2 = np.where(actions == 2)[0]
minority = max(len(idx_1), len(idx_2))
cap      = minority * 5
idx_0_sub = np.random.choice(idx_0, size=cap, replace=False)
idx_all   = np.concatenate([idx_0_sub, idx_1, idx_2])
np.random.shuffle(idx_all)
states  = states[idx_all]
actions = actions[idx_all]
rewards = rewards[idx_all]
print(f"  {len(states):,} after rebalancing: {np.bincount(actions)}")

# ── Normalise ──────────────────────────────────────────────────
mean = states.mean(0); std = states.std(0) + 1e-8
states = (states - mean) / std
np.save("ai_layer/rl/state_mean_v2.npy", mean)
np.save("ai_layer/rl/state_std_v2.npy",  std)

X_tr, X_val, y_tr, y_val, r_tr, r_val = train_test_split(
    states, actions, rewards,
    test_size=0.2, stratify=actions, random_state=RANDOM_SEED)
print(f"  Train: {len(X_tr):,}  Val: {len(X_val):,}")

class DS(Dataset):
    def __init__(self, s, a, r):
        self.s = torch.tensor(s)
        self.a = torch.tensor(a)
        self.w = torch.tensor(np.abs(r) + 0.1, dtype=torch.float32)
    def __len__(self): return len(self.s)
    def __getitem__(self, i): return self.s[i], self.a[i], self.w[i]

tr_loader  = DataLoader(DS(X_tr,  y_tr,  r_tr),  BATCH_SIZE, shuffle=True)
val_loader = DataLoader(DS(X_val, y_val, r_val), BATCH_SIZE, shuffle=False)

# ── Architectures ──────────────────────────────────────────────
class MLP256(nn.Module):
    name = "MLP-256"
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(9,256), nn.LayerNorm(256), nn.GELU(), nn.Dropout(0.3),
            nn.Linear(256,256), nn.LayerNorm(256), nn.GELU(), nn.Dropout(0.3),
            nn.Linear(256,128), nn.LayerNorm(128), nn.GELU(),
            nn.Linear(128,3))
    def forward(self, x): return self.net(x)

class MLP512(nn.Module):
    name = "MLP-512"
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(9,512), nn.LayerNorm(512), nn.GELU(), nn.Dropout(0.3),
            nn.Linear(512,512), nn.LayerNorm(512), nn.GELU(), nn.Dropout(0.3),
            nn.Linear(512,256), nn.LayerNorm(256), nn.GELU(), nn.Dropout(0.2),
            nn.Linear(256,128), nn.LayerNorm(128), nn.GELU(),
            nn.Linear(128,3))
    def forward(self, x): return self.net(x)

class ResidualBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim,dim), nn.LayerNorm(dim), nn.GELU(), nn.Dropout(0.2),
            nn.Linear(dim,dim), nn.LayerNorm(dim))
        self.act = nn.GELU()
    def forward(self, x): return self.act(x + self.block(x))

class ResMLP(nn.Module):
    name = "Residual-MLP"
    def __init__(self):
        super().__init__()
        self.input  = nn.Linear(9, 256)
        self.res1   = ResidualBlock(256)
        self.res2   = ResidualBlock(256)
        self.res3   = ResidualBlock(256)
        self.output = nn.Linear(256, 3)
    def forward(self, x):
        x = torch.relu(self.input(x))
        x = self.res1(x); x = self.res2(x); x = self.res3(x)
        return self.output(x)

def train_model(model, name):
    print(f"\n{'='*55}")
    print(f"Training {name} "
          f"({sum(p.numel() for p in model.parameters()):,} params)")
    print(f"{'='*55}")

    crit = nn.CrossEntropyLoss(reduction='none')
    opt  = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    sch  = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=LR,
        steps_per_epoch=len(tr_loader), epochs=EPOCHS)

    best_f1, best_state = 0.0, None

    for epoch in range(EPOCHS):
        model.train()
        for s, a, w in tr_loader:
            opt.zero_grad()
            loss = (crit(model(s), a) * w).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sch.step()

        if (epoch+1) % 15 == 0 or epoch == EPOCHS-1:
            model.eval()
            preds, trues = [], []
            with torch.no_grad():
                for s, a, _ in val_loader:
                    preds.extend(model(s).argmax(1).numpy())
                    trues.extend(a.numpy())
            mf1 = f1_score(trues, preds, average='macro', zero_division=0)
            acc = np.mean(np.array(preds) == np.array(trues))
            print(f"  Epoch {epoch+1:>3}  acc={acc:.3f}  macro_f1={mf1:.3f}")
            if mf1 > best_f1:
                best_f1 = mf1
                best_state = {k: v.clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    return best_f1, model

# ── Train all three ────────────────────────────────────────────
results = {}
best_overall_f1   = 0.0
best_overall_model= None
best_overall_name = ""

for ModelClass in [MLP256, MLP512, ResMLP]:
    model = ModelClass()
    f1, trained = train_model(model, ModelClass.name)
    results[ModelClass.name] = f1
    if f1 > best_overall_f1:
        best_overall_f1    = f1
        best_overall_model = trained
        best_overall_name  = ModelClass.name

# ── Save best ──────────────────────────────────────────────────
torch.save(best_overall_model.state_dict(), MODEL_OUT)

print(f"\n{'='*55}")
print(f"Architecture comparison:")
for name, f1 in results.items():
    marker = " ← BEST" if name == best_overall_name else ""
    print(f"  {name:20s}: macro_f1 = {f1:.3f}{marker}")
print(f"{'='*55}")

# ── Final classification report ────────────────────────────────
print(f"\nFinal report ({best_overall_name}):")
best_overall_model.eval()
preds, trues = [], []
with torch.no_grad():
    for s, a, _ in val_loader:
        preds.extend(best_overall_model(s).argmax(1).numpy())
        trues.extend(a.numpy())

print(classification_report(trues, preds,
      target_names=["DELIVER","RECHARGE","WAIT"], zero_division=0))
print(f"Model saved -> {MODEL_OUT}")
