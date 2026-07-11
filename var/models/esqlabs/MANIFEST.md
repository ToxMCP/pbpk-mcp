# esqLABS Third-Party Model Inventory

This public directory contains provenance metadata only. The PKML files, model-specific sidecars, and smoke outputs were removed from the public repository tree because public availability of an upstream repository does not by itself grant redistribution permission.

**Release status: not approved for public redistribution.** `sources.json` records the reviewed source and license evidence. `index.json` preserves immutable source commits and content hashes for the privately retained files. These records support review; they are not legal advice.

The public-tree check must pass:

```bash
python3 scripts/esqlabs_models.py check-public-tree
```

The redistribution gate remains intentionally closed:

```bash
python3 scripts/esqlabs_models.py write-index --public-release
```

For an authorized private runtime, supply a separate local model root explicitly:

```bash
export PBPK_ESQLABS_MODELS_ROOT=/private/path/to/esqlabs-models
python3 scripts/esqlabs_models.py prepare-live-server
```

## Privately preserved inventory

- `ESQapp/Aciclovir.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Mouse.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Rabbit.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Rat.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCPKSimStandard_CPPKSimStandard_Mouse.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCPKSimStandard_CPPKSimStandard_Rabbit.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCPKSimStandard_CPPKSimStandard_Rat.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCPT_CPPKSimStandard_Mouse.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCPT_CPPKSimStandard_Rabbit.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCPT_CPPKSimStandard_Rat.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCRR_CPPKSimStandard_Mouse.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCRR_CPPKSimStandard_Rabbit.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCRR_CPPKSimStandard_Rat.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCSchmitt_CPPKSimStandard_Mouse.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCSchmitt_CPPKSimStandard_Rabbit.pkml`
- `PBPK-for-cross-species-extrapolation/Sim_Compound_PCSchmitt_CPPKSimStandard_Rat.pkml`
- `TissueTMDD/repeated dose model.pkml`
- `esqlabsR/Aciclovir.pkml`
- `esqlabsR/simple.pkml`
- `esqlabsR/simple2.pkml`
- `pregnancy-neonates-batch-run/2_weeks_simulation_PKSim.pkml`
- `pregnancy-neonates-batch-run/2_weeks_simulation_Poulin.pkml`
- `pregnancy-neonates-batch-run/2_weeks_simulation_R&R.pkml`
- `pregnancy-neonates-batch-run/2_weeks_simulation_Schmitt.pkml`
- `pregnancy-neonates-batch-run/6_month_simulation_PKSim.pkml`
- `pregnancy-neonates-batch-run/6_month_simulation_Poulin.pkml`
- `pregnancy-neonates-batch-run/6_month_simulation_R&R.pkml`
- `pregnancy-neonates-batch-run/6_month_simulation_Schmitt.pkml`
- `pregnancy-neonates-batch-run/Pregnant_simulation_PKSim.pkml`
- `pregnancy-neonates-batch-run/Pregnant_simulation_Poulin.pkml`
- `pregnancy-neonates-batch-run/Pregnant_simulation_R&R.pkml`
- `pregnancy-neonates-batch-run/Pregnant_simulation_Schmitt.pkml`

## Other upstream PKMLs not included in the inventory

These PKML files were visible in `esqLABS` repositories, but they do not load via `loadSimulation()` with the current runtime:

- `Female-Reproductive-Tract-module-training/Extension modules/Cervicovaginal administration.pkml`
- `Female-Reproductive-Tract-module-training/Extension modules/Female reproductive tract.pkml`
- `esqlabsR/ObsDataAciclovir_1.pkml`
- `esqlabsR/ObsDataAciclovir_2.pkml`
- `esqlabsR/ObsDataAciclovir_3.pkml`

The excluded files appear to be extension modules or observed-data PKMLs rather than simulation transfer files.
