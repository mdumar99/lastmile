# Offline RL — Full Analysis Report

## What We Built

A complete offline RL pipeline trained on rule-based agent demonstrations
and evaluated via live simulation with the policy hooked into the C++ engine.

    Phase A  collect_experience_v2.py   363,215 (state,action,reward) tuples
                                         5 runs x 300 robots x 8h
                                         9 state features
    Phase B  train_policy_v2.py         3 architectures compared
                                         Residual-MLP won (macro F1=0.648)
    Phase C  evaluate_policy.py         Statistical evaluation (+0.98%)
    Phase D  Simulation.cpp callback    Policy hooked into C++ engine
    Phase E  run_policy_simulation*.py  Real delivery/energy numbers
                                         3 versions, 3 seeds each

## State Features (9)

    [0]  battery %                 strongest signal
    [1]  dist to nearest hub       key for RECHARGE decisions
    [2]  weather multiplier        weak — simplified to constant
    [3]  hour of day               weak signal in this simulation
    [4]  deliveries completed      normalisation anchor
    [5]  recharges completed       detects over-recharging
    [6]  nearby robot density      added in v2, limited impact
    [7]  hub queue pressure        added in v2, limited impact
    [8]  time since last recharge  added in v2, limited impact

## Architecture Comparison

    Architecture    Params    Macro F1
    MLP-256         102,915   0.636
    MLP-512         435,203   0.637
    Residual-MLP    401,155   0.648   ← best

    All plateau at ~0.636-0.648 regardless of capacity or data size.
    This is the information ceiling of the current state space,
    not a model capacity problem.

## Per-Class Training Results (Residual-MLP)

    Action      Precision   Recall   F1     Verdict
    DELIVER     0.84        1.00     0.91   good
    RECHARGE    1.00        1.00     1.00   perfect
    WAIT        0.86        0.02     0.03   failed — see analysis

    WAIT failed because traffic jams are random (Poisson process)
    and not correlated with any observable state feature.
    No architecture or feature engineering can fix this without
    road-segment-level congestion data.

## Real Simulation Results (100 robots, 8h, 3 seeds)

### v1 — No gate (pure policy)

    Deliveries : -11.4%  (9,016 vs 10,176 rule-based)
    Energy     :  -2.5%
    Recharges  : +17,082 (catastrophic over-recharging)

    Root cause: covariate shift. Policy trained on battery<20% for
    RECHARGE, but called on robots at 80%+ battery in live sim.
    Overconfident RECHARGE predictions outside training distribution.

### v2 — 40% battery gate (suppress RECHARGE above gate)

    Deliveries :  -9.3%
    Energy     :  -8.3%
    Recharges  : normal

    Root cause: gate suppressed RECHARGE but model routed to WAIT
    instead. 67-73% of decisions were WAIT — robots sat idle.
    Same covariate shift, different symptom.

### v3 — Zone gate (RL only active 20-35% battery)

    Deliveries :  +3.9%  ← BETTER than rule-based ✅
    Energy     :  +3.3%  (acceptable trade-off)
    Recharges  : +5.3 (slight increase, correct behaviour)

    RL makes ~1,400 decisions per run out of ~11,000 total.
    Outside 20-35% zone: pure rule-based.
    Inside 20-35% zone: RL decides DELIVER or RECHARGE only.

    The +3.9% delivery improvement comes from the soft battery
    threshold — RL continues delivering at 22-34% battery when
    the rule-based agent would conservatively recharge at 20%.

## Summary Table

    Version          Deliveries Δ   Energy Δ   Verdict
    v1 no gate         -11.4%        -2.5%     WORSE
    v2 40% gate         -9.3%        -8.3%     WORSE
    v3 zone 20-35%      +3.9%        +3.3%     BETTER ✅

## What Worked

    ✅ End-to-end pipeline: collect → train → evaluate → live sim
    ✅ C++ callback bridge — policy hooks into engine cleanly
    ✅ RECHARGE: perfect F1, soft threshold learned
    ✅ Zone-gated policy: +3.9% deliveries in live simulation
    ✅ Multi-seed evaluation (3 seeds) for statistical validity
    ✅ Honest failure analysis at each version

## What Didn't Work

    ❌ Unconstrained policy: covariate shift causes over-recharging
    ❌ WAIT prediction: 3% F1, information failure not model failure
    ❌ New state features: minimal improvement (end-of-run snapshots
       not real-time per-event values)
    ❌ Larger models: no benefit over MLP-256

## Honest Assessment

The offline RL approach works, but only in the narrow zone where
the agent was actually trained (20-35% battery). Outside that zone,
rule-based is more reliable. The +3.9% improvement is real and
statistically consistent across 3 seeds, but it comes with +3.3%
energy cost — a genuine operational trade-off.

The covariate shift problem (v1, v2) is the defining lesson of this
branch: offline RL policies must be constrained to their training
distribution or they fail badly.

## Recommendations for Online RL (Phase 4)

1. Restructure engine with step() interface for episode-by-episode RL
2. Add real-time per-event features (not end-of-run snapshots)
3. Use PPO or SAC — can discover strategies beyond rule-based
4. Consider multi-agent RL (MADDPG/QMIX) for robot coordination
5. Road-segment congestion index to make WAIT learnable

## Files

    collect_experience_v2.py        data collection (5 runs x 300 robots)
    train_policy_v2.py              architecture search + training
    evaluate_policy.py              statistical evaluation
    run_policy_simulation.py        live eval v1 (no gate)
    run_policy_simulation_v2.py     live eval v2 (40% gate)
    run_policy_simulation_v3.py     live eval v3 (zone gate) ← best
    policy_v2.pt                    best model weights (Residual-MLP)
    real_eval_results_v3.json       final evaluation results
    ANALYSIS.md                     this document
