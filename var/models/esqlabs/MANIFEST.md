# esqLABS Open-Source PKML Catalog

This directory contains the public `esqLABS` PKML files that loaded as runnable simulation transfers with the current `ospsuite` runtime.

## Runnable simulation PKMLs

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

## Public PKMLs excluded from the runnable set

These are public PKML files in `esqLABS` repos, but they do not load via `loadSimulation()` with the current runtime:

- `Female-Reproductive-Tract-module-training/Extension modules/Cervicovaginal administration.pkml`
- `Female-Reproductive-Tract-module-training/Extension modules/Female reproductive tract.pkml`
- `esqlabsR/ObsDataAciclovir_1.pkml`
- `esqlabsR/ObsDataAciclovir_2.pkml`
- `esqlabsR/ObsDataAciclovir_3.pkml`

The excluded files appear to be extension modules or observed-data PKMLs rather than simulation transfer files.
