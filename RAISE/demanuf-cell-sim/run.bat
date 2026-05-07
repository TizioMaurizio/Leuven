@echo off
setlocal
title Demanuf Cell Sim
cd /d "%~dp0"

echo.
echo ========================================
echo [STEP] Installing dependencies...
echo ========================================
call npm install
if errorlevel 1 (
    echo [FAIL] npm install failed!
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

echo.
echo ========================================
echo [STEP] Running safety tests...
echo ========================================
call npx tsx scripts/safety_tests.ts
if errorlevel 1 (
    echo.
    echo [WARN] Safety tests FAILED! Review output above.
    echo        Continuing anyway — you may still commit.
    echo.
    pause
) else (
    echo [OK] All safety tests passed.
)

echo.
echo ========================================
echo [STEP] Creating git commits...
echo ========================================

echo [COMMIT 1] feat(sim): add PolicyConfig and structured decision types
git add src/sim/config.ts src/sim/types.ts 2>nul
git commit -m "feat(sim): add PolicyConfig and structured decision types" || echo [skipped] nothing to commit

echo [COMMIT 2] feat(sim): rewrite policy with guarded config-driven decisions
git add src/sim/policy.ts 2>nul
git commit -m "feat(sim): rewrite policy with guarded config-driven decisions" || echo [skipped] nothing to commit

echo [COMMIT 3] feat(sim): wire config, decision logging, evidence-seeking into engine
git add src/sim/engine.ts 2>nul
git commit -m "feat(sim): wire config, decision logging, evidence-seeking into engine" || echo [skipped] nothing to commit

echo [COMMIT 4] feat(sim): add research metrics module
git add src/sim/metrics.ts 2>nul
git commit -m "feat(sim): add research metrics module" || echo [skipped] nothing to commit

echo [COMMIT 5] feat(sim): add bounded semantic mediation hook
git add src/sim/mediation.ts 2>nul
git commit -m "feat(sim): add bounded semantic mediation hook" || echo [skipped] nothing to commit

echo [COMMIT 6] feat(sim): upgrade export with metrics, decisions, and JSON output
git add src/sim/export.ts 2>nul
git commit -m "feat(sim): upgrade export with metrics, decisions, and JSON output" || echo [skipped] nothing to commit

echo [COMMIT 7] feat(ui): add DecisionPanel, MetricsPanel, policy selector
git add src/components/DecisionPanel.tsx src/components/MetricsPanel.tsx src/components/BeliefView.tsx src/components/Toolbar.tsx src/hooks/useSimulation.ts src/App.tsx 2>nul
git commit -m "feat(ui): add DecisionPanel, MetricsPanel, policy selector" || echo [skipped] nothing to commit

echo [COMMIT 8] test: add safety and causality test suite
git add scripts/safety_tests.ts 2>nul
git commit -m "test: add safety and causality test suite" || echo [skipped] nothing to commit

echo [COMMIT 9] chore: remaining changes
git add -A 2>nul
git commit -m "chore: remaining changes" || echo [skipped] nothing to commit

echo.
echo [OK] Commits done.

echo.
echo ========================================
echo [STEP] Recent git history:
echo ========================================
git log --oneline -10

echo.
echo ========================================
echo [STEP] Starting dev server...
echo ========================================
call npm run dev
