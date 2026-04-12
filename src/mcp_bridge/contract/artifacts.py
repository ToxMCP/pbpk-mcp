from __future__ import annotations

import json

_CAPABILITY_MATRIX_JSON = r"""
{
  "contractVersion": "pbpk-mcp.v1",
  "entries": [
    {
      "backend": "ospsuite",
      "catalogDiscovery": "yes",
      "deterministicExecution": "yes",
      "deterministicResults": "yes",
      "id": "pkml-transfer-file",
      "label": "PK-Sim / MoBi transfer file (.pkml)",
      "loadIntoSession": "yes",
      "notes": [
        "Optional sidecars can enrich qualification metadata and parameter provenance.",
        "Population simulation is not exposed as a generic OSPSuite .pkml capability in the current public contract."
      ],
      "oecdDossierExport": "yes",
      "policy": "runtime-supported",
      "populationExecution": "no",
      "populationResults": "no",
      "requestValidation": "yes",
      "runtimeFormat": "pkml",
      "staticManifestValidation": "yes",
      "verification": "yes"
    },
    {
      "backend": "rxode2",
      "catalogDiscovery": "yes",
      "deterministicExecution": "yes",
      "deterministicResults": "yes",
      "id": "contract-complete-r-model",
      "label": "Contract-complete MCP-ready R model (.R)",
      "loadIntoSession": "yes",
      "notes": [
        "Population workflows depend on the model declaring the population capability and implementing the required runtime hook.",
        "Richer OECD-oriented evidence can be supplied through module hooks and companion bundles."
      ],
      "oecdDossierExport": "yes",
      "policy": "runtime-supported",
      "populationExecution": "conditional",
      "populationResults": "conditional",
      "requestValidation": "yes",
      "runtimeFormat": "r",
      "staticManifestValidation": "yes",
      "verification": "yes"
    },
    {
      "backend": "rxode2",
      "catalogDiscovery": "yes",
      "deterministicExecution": "no",
      "deterministicResults": "no",
      "id": "discoverable-incomplete-r-model",
      "label": "Discoverable but incomplete R module (.R)",
      "loadIntoSession": "no",
      "notes": [
        "An .R file may still appear in discovery before it satisfies the expected PBPK MCP hook contract.",
        "validate_model_manifest is the intended pre-load surface for diagnosing missing hooks and dossier gaps."
      ],
      "oecdDossierExport": "no",
      "policy": "discoverable-but-not-runnable",
      "populationExecution": "no",
      "populationResults": "no",
      "requestValidation": "no",
      "runtimeFormat": "r",
      "staticManifestValidation": "yes",
      "verification": "no"
    },
    {
      "backend": null,
      "catalogDiscovery": "no",
      "deterministicExecution": "no",
      "deterministicResults": "no",
      "id": "pksim5-project",
      "label": "PK-Sim project file (.pksim5)",
      "loadIntoSession": "no",
      "notes": [
        "Direct .pksim5 loading is rejected early.",
        "Export the project to .pkml before runtime use."
      ],
      "oecdDossierExport": "no",
      "policy": "conversion-only",
      "populationExecution": "no",
      "populationResults": "no",
      "requestValidation": "no",
      "runtimeFormat": "pksim5",
      "staticManifestValidation": "no",
      "verification": "no"
    },
    {
      "backend": null,
      "catalogDiscovery": "no",
      "deterministicExecution": "no",
      "deterministicResults": "no",
      "id": "berkeley-madonna-source",
      "label": "Berkeley Madonna source model (.mmd)",
      "loadIntoSession": "no",
      "notes": [
        "Direct .mmd loading is rejected early.",
        "Convert the model to .pkml or an MCP-ready .R module before runtime use."
      ],
      "oecdDossierExport": "no",
      "policy": "conversion-only",
      "populationExecution": "no",
      "populationResults": "no",
      "requestValidation": "no",
      "runtimeFormat": "mmd",
      "staticManifestValidation": "no",
      "verification": "no"
    }
  ],
  "statusLegend": {
    "conditional": "Supported only when the model or request satisfies declared capability conditions.",
    "no": "Not part of the published workflow for this input class.",
    "yes": "Supported directly by the published PBPK MCP workflow."
  }
}
"""

_CONTRACT_MANIFEST_JSON = r"""
{
  "artifactClasses": {
    "legacy-excluded": {
      "description": "Historical or non-PBPK-side artifacts that are intentionally outside pbpk-mcp.v1."
    },
    "normative": {
      "description": "Machine-readable artifacts that define the published pbpk-mcp.v1 contract."
    },
    "supporting": {
      "description": "Human-facing or release-facing artifacts that support the contract without defining it."
    }
  },
  "artifactCounts": {
    "examples": 8,
    "schemas": 8,
    "supporting": 34
  },
  "capabilityMatrix": {
    "classification": "normative",
    "relativePath": "docs/architecture/capability_matrix.json",
    "sha256": "bdc2169d99343f38c5a7dea91306d46704104d488442e4161812dfb63ac6da03"
  },
  "contractManifest": {
    "classification": "normative",
    "relativePath": "docs/architecture/contract_manifest.json"
  },
  "contractVersion": "pbpk-mcp.v1",
  "id": "pbpk-contract-manifest.v1",
  "legacyArtifactPolicy": [
    {
      "classification": "legacy-excluded",
      "reason": "Legacy literature extraction schema retained outside the PBPK-side pbpk-mcp.v1 object family.",
      "relativePath": "schemas/extraction-record.json"
    }
  ],
  "legacyArtifactsExcluded": [
    "schemas/extraction-record.json"
  ],
  "resourceEndpoints": {
    "capabilityMatrix": "/mcp/resources/capability-matrix",
    "contractManifest": "/mcp/resources/contract-manifest",
    "releaseBundleManifest": "/mcp/resources/release-bundle-manifest",
    "schemaCatalog": "/mcp/resources/schemas"
  },
  "schemas": [
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/assessmentContext.v1.example.json",
      "exampleSha256": "774828884b6705892187768b505b1c3f5e36ebe83d2a2f570847145297bf3d0c",
      "relativePath": "schemas/assessmentContext.v1.json",
      "schemaId": "assessmentContext.v1",
      "sha256": "2849beb31892bce04753f732e5bf538595a2a060b9c2c25d291f317640eda20c"
    },
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/berInputBundle.v1.example.json",
      "exampleSha256": "64399ce683596314bf9d32df20f8c42ffa02673830f477e7e78ea3a0bfa845ff",
      "relativePath": "schemas/berInputBundle.v1.json",
      "schemaId": "berInputBundle.v1",
      "sha256": "a46c842bfc6dd6f1e1ef4d0f5f65371182c830d478cafae3eef9a599899e9cae"
    },
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/internalExposureEstimate.v1.example.json",
      "exampleSha256": "559f0118d012d14275141d11dbb0d968ed74a0ce39002ad1094bfe87a034009e",
      "relativePath": "schemas/internalExposureEstimate.v1.json",
      "schemaId": "internalExposureEstimate.v1",
      "sha256": "830b2cf73661b67dfd0e8493c5e410e276555c05f71221db8e36722bf6cb4857"
    },
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/pbpkQualificationSummary.v1.example.json",
      "exampleSha256": "66bd8b255e52c125e72b18eaf36ea49ed95d0af5c6f4a050d483b5bb0e3697eb",
      "relativePath": "schemas/pbpkQualificationSummary.v1.json",
      "schemaId": "pbpkQualificationSummary.v1",
      "sha256": "20eb7f265c12d406d453614e8c3a704d19fb8ae6527390d9a9ed6f401cdec2d3"
    },
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/pointOfDepartureReference.v1.example.json",
      "exampleSha256": "11185de168163409fb9c22dcfbf7b10c322ff8eddf521d02d1842ee7c4994dbc",
      "relativePath": "schemas/pointOfDepartureReference.v1.json",
      "schemaId": "pointOfDepartureReference.v1",
      "sha256": "58a0e04e48ed716637aae12e972e0f92b858ff6f0cfde918942b97a1daa695aa"
    },
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/uncertaintyHandoff.v1.example.json",
      "exampleSha256": "ef372636efb1a13dd26151618eaf440bbde90fad5e600b0ab13945187fb0a03c",
      "relativePath": "schemas/uncertaintyHandoff.v1.json",
      "schemaId": "uncertaintyHandoff.v1",
      "sha256": "4547fbcd1014e439abbf5f98ce1e19e0320be8e81eb30102d6a0099fce32d86e"
    },
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/uncertaintyRegisterReference.v1.example.json",
      "exampleSha256": "652fd3674c30263e5da3e299418327ec4d06811f75f661deff63b2d152b1841f",
      "relativePath": "schemas/uncertaintyRegisterReference.v1.json",
      "schemaId": "uncertaintyRegisterReference.v1",
      "sha256": "38808ece8fa55cc3b233f5b3966d480616983d953d0f8f7290cb6191e7222bb6"
    },
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/uncertaintySummary.v1.example.json",
      "exampleSha256": "9cb008aadd06a2fb4f12dae6ea46023e6f30f30011d851ad76ad9f0f2c9bd181",
      "relativePath": "schemas/uncertaintySummary.v1.json",
      "schemaId": "uncertaintySummary.v1",
      "sha256": "ea1f95e8bd2786468c0a946f0c2dbbba0045411024292affb052efd33c9e00c3"
    }
  ],
  "supportingArtifacts": [
    {
      "classification": "supporting",
      "relativePath": "benchmarks/regulatory_goldset/README.md",
      "role": "regulatory benchmark corpus guide",
      "sha256": "3da4d18c8a96049148b26bcd17f37e14e853481b3974e21b4ab8a8dcd9baef14"
    },
    {
      "classification": "supporting",
      "relativePath": "benchmarks/regulatory_goldset/sources.lock.json",
      "role": "regulatory gold-set source lock",
      "sha256": "ba24143cfe7ddd976779d7c60d24754b35f8ecf0d361e15c8ad247e488af337b"
    },
    {
      "classification": "supporting",
      "relativePath": "benchmarks/regulatory_goldset/fetched.lock.json",
      "role": "regulatory gold-set fetch lock",
      "sha256": "949db5491f40406ab4a0fc185952795bb88f1243ac5c4a3ead1b4fda7661ddca"
    },
    {
      "classification": "supporting",
      "relativePath": "benchmarks/regulatory_goldset/regulatory_goldset_scorecard.json",
      "role": "regulatory gold-set scorecard",
      "sha256": "212987469243e7b32a06f41cdab74c21b931f4540b12ab6a492baeff6dcd967a"
    },
    {
      "classification": "supporting",
      "relativePath": "benchmarks/regulatory_goldset/regulatory_goldset_summary.md",
      "role": "regulatory gold-set benchmark summary",
      "sha256": "9bb0eb45eb571d57a30622665b8caeeaaca0e31114edf83554facbe11083d944"
    },
    {
      "classification": "supporting",
      "relativePath": "benchmarks/regulatory_goldset/regulatory_goldset_audit_manifest.json",
      "role": "regulatory gold-set audit manifest",
      "sha256": "21af57a4b41416ab79cfa86bd58c4582f5834218adad033b8c4b3bb65967931e"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/architecture/capability_matrix.md",
      "role": "human-readable capability guide",
      "sha256": "f239bd8632e5bf325f79ab530e7fa7bd7e3cff3bfc2e2d2b2bfa3bd047f97a59"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/architecture/mcp_payload_conventions.md",
      "role": "payload contract reference",
      "sha256": "2bd79754995a99b2f7c679b336a5b9e4e91373714d3e64ddc933da4edcd0ee02"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/architecture/exposure_led_ngra_role.md",
      "role": "exposure-led NGRA boundary guide",
      "sha256": "782b28c3770556b5d724f75e5135104be15faa4ce3c5023fb4676c9d6ed855f8"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/architecture/toxmcp_suite_index.md",
      "role": "cross-service suite routing guide",
      "sha256": "55484334139441cd2f806751ecb9e7e0e8ee0afd48873cc8439a2b8d31773c0e"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/architecture/release_bundle_manifest.json",
      "role": "whole release bundle hash inventory",
      "sha256": "08f3eda1b050ac440407c16dac2ab643b67d3a7141edfba0ed7cd10ac5daa233"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/hardening_migration_notes.md",
      "role": "hardening migration notes",
      "sha256": "7cb8c35e428fd1a521bd3c7dccd9ad5055389a547390568c8b431147badd1463"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/pbpk_model_onboarding_checklist.md",
      "role": "PBPK model onboarding checklist",
      "sha256": "c3ac775a33d357fceac2d74ecd65d1e7d9f3dafa2166fa71f969217b02d56185"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/github_publication_checklist.md",
      "role": "publication checklist",
      "sha256": "bc30081bb753562a1a32272fe215c092c4940941dcc99cb98c247b6f7cb6fa2f"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/pbk_reviewer_signoff_checklist.md",
      "role": "PBK reviewer sign-off checklist",
      "sha256": "12c8ff065ae36a0ae1f3a94b635d6635ad2b237ecf4755eb2ab2a457dccb336c"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/post_release_audit_plan.md",
      "role": "post-release audit plan",
      "sha256": "cfedfabd7a0943f94b8afba4d2d0f9b85c8b9225f955bea7e3c331bd316583f5"
    },
    {
      "classification": "supporting",
      "relativePath": "schemas/README.md",
      "role": "schema usage guide",
      "sha256": "2f58bea343ec1a49d9c25dbaadc3d36bfa87cebb483f280e776034d0927f4339"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/check_distribution_artifacts.py",
      "role": "distribution artifact validation script",
      "sha256": "12934c81c14241f6fb28705c97e9eb443e29c75b5c71005cc0dbb394c57f6084"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/check_release_metadata.py",
      "role": "release metadata consistency check",
      "sha256": "971bf6472a31e184ac1e55fc17886a69154dd83ac9adb7e1cfef0579ebaf896b"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/check_installed_package_contract.py",
      "role": "installed package contract validation script",
      "sha256": "e63b48f3f0b7d0f5093f31f157e1b656c62a207b23021f3dd127801094a177ea"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/check_runtime_contract_env.py",
      "role": "contract dependency preflight script",
      "sha256": "82cbd13b4c7c4fef29b06cac4d9552f7db236985c1e7c348391e7f929b35d9a0"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/release_readiness_check.py",
      "role": "live release readiness gate",
      "sha256": "1364fedf34a4adaac31187c250dd89796efd2587328ed5662fa60e1eacace234"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/wait_for_runtime_ready.py",
      "role": "runtime readiness probe",
      "sha256": "fa18ce884ba790f7d208fde156709b2735e4678e68dc75461a4cbe04569364be"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/workspace_model_smoke.py",
      "role": "workspace live smoke script",
      "sha256": "c9f201b0958028473a5434a8704130492021f7fffc8cb42e28b3b9d357257684"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/generate_contract_artifacts.py",
      "role": "contract artifact generator",
      "sha256": "c5e16e58a9c65b8e3fdb0c064dc39467f5578ca848962a998128ae65c5f2c506"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/generate_regulatory_goldset_audit.py",
      "role": "regulatory gold-set audit generator",
      "sha256": "ef244652dad5862ad46c25e1dd6b844a148389dcf7697c242577b3b268e6a0e2"
    },
    {
      "classification": "supporting",
      "relativePath": "src/mcp_bridge/trust_surface.py",
      "role": "thin-client trust-surface contract helper",
      "sha256": "4f969e87ef43bc504d51e41b83d1ae0ab536f26d2402e20f6c0484fc86773f21"
    },
    {
      "classification": "supporting",
      "relativePath": "src/mcp_bridge/benchmarking/regulatory_goldset.py",
      "role": "regulatory gold-set benchmark helper",
      "sha256": "6760efa0d01df3e79250c095d6d07d59e2bff3dd3868f8f0740728dc1eaa6420"
    },
    {
      "classification": "supporting",
      "relativePath": "tests/test_release_readiness_script.py",
      "role": "release readiness regression test",
      "sha256": "f522643b935aa1df742c460aafa3995ccbe820badeafd18ff4adbf58b6d7e66d"
    },
    {
      "classification": "supporting",
      "relativePath": "tests/test_regulatory_goldset_analysis.py",
      "role": "regulatory gold-set analysis regression test",
      "sha256": "54e6d77912b949efdd2c5f029cb37e7322f3852b5390e6a5349c4bf3d0b790f2"
    },
    {
      "classification": "supporting",
      "relativePath": "tests/test_trust_surface.py",
      "role": "trust-surface contract regression test",
      "sha256": "f431221584bffa69523fd5bd08f12038228ca248fadbe47a2c7ea5e967b7f243"
    },
    {
      "classification": "supporting",
      "relativePath": "tests/test_runtime_security_live_stack.py",
      "role": "live runtime security regression test",
      "sha256": "7117ddb351c2bdb913f91691da82c7bafeb1b57884243ae302bbf17fabf289ad"
    },
    {
      "classification": "supporting",
      "relativePath": "tests/test_model_discovery_live_stack.py",
      "role": "live model discovery regression test",
      "sha256": "cb4a385369e23a8509c66c5d75e88d6bf0b8a4d53600f26e4f3ebe6584fc6a98"
    },
    {
      "classification": "supporting",
      "relativePath": "tests/test_oecd_live_stack.py",
      "role": "live OECD workflow regression test",
      "sha256": "db5edcebc286134d6bd676ffa0d0b51ae5758d88943527e06c8535d4b1f62147"
    }
  ]
}
"""

_RELEASE_BUNDLE_MANIFEST_JSON = r"""
{
  "bundleSha256": "a6428d9e44864e4b39fcad5c3a20e7b897c1edd7e9253d8c2cf2f1580555cae3",
  "contractVersion": "pbpk-mcp.v1",
  "fileCount": 593,
  "files": [
    {
      "group": "root",
      "relativePath": ".dockerignore",
      "sha256": "972e5269292a5b841cbc919bca861a2e35f655c9dfb30af6edecb5cb246a00dd",
      "sizeBytes": 191
    },
    {
      "group": "root",
      "relativePath": ".editorconfig",
      "sha256": "6297da6b1169de32dca2f6184b4eaa63a8bb6c7e1c66c20d6e813166256e3856",
      "sizeBytes": 202
    },
    {
      "group": "root",
      "relativePath": ".env.example",
      "sha256": "3c748ea13560e1243ce2a50efa7779851518163ccb2a0dcd6524c2cf67616dff",
      "sizeBytes": 3800
    },
    {
      "group": "root",
      "relativePath": ".gitignore",
      "sha256": "f3d7e00741deb461a46968475242580344c5a1dc449d6f5c182db4f7b6f5030d",
      "sizeBytes": 693
    },
    {
      "group": "root",
      "relativePath": "CHANGELOG.md",
      "sha256": "e5797790778569faed50d9d598cc2939baafd37a4065e36d795edb3c4fd576b2",
      "sizeBytes": 25736
    },
    {
      "group": "root",
      "relativePath": "CITATION.cff",
      "sha256": "83dde4a6460d053c401a51eeb9176e8cfa8264f007dda8139cbc8f1f7309081e",
      "sizeBytes": 493
    },
    {
      "group": "root",
      "relativePath": "CODE_OF_CONDUCT.md",
      "sha256": "d8d33f5302c9e29f79a0d7251963ab96cfa4dc2c5ac08f2639531eb38d3bd453",
      "sizeBytes": 851
    },
    {
      "group": "root",
      "relativePath": "CONTRIBUTING.md",
      "sha256": "1ff6a239f04fd7671a5075aa2a9fc52fe71381f1d1f9719de42331dfe68d4594",
      "sizeBytes": 3433
    },
    {
      "group": "root",
      "relativePath": "DOCKER_SETUP.md",
      "sha256": "2c6e7166cf76673143c4aa99f2353485783d5fe230cc7e533d1cc173e6899264",
      "sizeBytes": 6343
    },
    {
      "group": "root",
      "relativePath": "Dockerfile",
      "sha256": "89394e428d02fb01b8367e3259dfc23bf345c5c107bfd8fcfe97634d02b89c7a",
      "sizeBytes": 3903
    },
    {
      "group": "root",
      "relativePath": "LICENSE",
      "sha256": "63145120ee00b23a582679276e00d8815f992bfc188341490e310eb872b30a59",
      "sizeBytes": 9156
    },
    {
      "group": "root",
      "relativePath": "MANIFEST.in",
      "sha256": "4124f4d0476112d55d20162314d6578d9a3bdd521cdb4a5eead505f009df4253",
      "sizeBytes": 2732
    },
    {
      "group": "root",
      "relativePath": "Makefile",
      "sha256": "3d6b953d8462a09fabd299a100733277b7fd83220fb06ba4337046ea13dd749d",
      "sizeBytes": 8134
    },
    {
      "group": "root",
      "relativePath": "OECD_PBPK_guidelines.pdf",
      "sha256": "8624df7a04bef600b325fed55f1fe70ac5af1ffdee77d6283d9dfba73d7b4ab6",
      "sizeBytes": 8122921
    },
    {
      "group": "root",
      "relativePath": "README.md",
      "sha256": "8c38813c06858f0d2662d25bc7faa8d38fdc45e785342bc2385b7959cda35c20",
      "sizeBytes": 56272
    },
    {
      "group": "root",
      "relativePath": "SECURITY.md",
      "sha256": "68caf30aeb8889be9ac68579a18eeab31bb9801a2eddb1d11e67e2713c5baadc",
      "sizeBytes": 1415
    },
    {
      "group": "root",
      "relativePath": "SUPPORT.md",
      "sha256": "c9c52839663aa1576ee360dfe5ab2a2dfec11cc94a98d4179d34ae367f8f1eb1",
      "sizeBytes": 438
    },
    {
      "group": "root",
      "relativePath": "docker-compose.celery.yml",
      "sha256": "3f5bdba50097bc18f378ad4faca4f44fcdaf823d172089970485997e3b9431b4",
      "sizeBytes": 2153
    },
    {
      "group": "root",
      "relativePath": "docker-compose.hardened.yml",
      "sha256": "7cdebdfa6ae19840b31d5e6dd5b57d38a3f175839442236ea839e282ce18e51c",
      "sizeBytes": 1923
    },
    {
      "group": "root",
      "relativePath": "docker-compose.overlay.yml",
      "sha256": "0cb751421608bf384dcc68c58f40abbbd8a94391290c68d6b9d3e1e174cf8a69",
      "sizeBytes": 650
    },
    {
      "group": "root",
      "relativePath": "docker-compose.s3-audit-smoke.yml",
      "sha256": "0550afe637c1084099fd69c2a95f337eda74fe98ec8976c81fa5dd2b8dba8708",
      "sizeBytes": 2361
    },
    {
      "group": "root",
      "relativePath": "pyproject.toml",
      "sha256": "9b751bfbe917c135a48949224b09008064bea1a679c7dd361bd446868a0beafb",
      "sizeBytes": 2530
    },
    {
      "group": "root",
      "relativePath": "run_agent.py",
      "sha256": "e98892da1e80f84e02ec4bf1d0ec975ab58ee732535579d48123aa73c77d299a",
      "sizeBytes": 5382
    },
    {
      "group": "root",
      "relativePath": "v0.3.4.md",
      "sha256": "840a858c5abdc942c540af2876612311d6939d269218cdaeb81af8802ba27c09",
      "sizeBytes": 2339
    },
    {
      "group": "root",
      "relativePath": ".devcontainer/devcontainer.json",
      "sha256": "4ee9b136d18cc7ae37a635bb45e56fec7bb4151a980aa17e4641f277895eaf2d",
      "sizeBytes": 488
    },
    {
      "group": "governance",
      "relativePath": ".github/CODEOWNERS",
      "sha256": "74e831fc8112e5d6607108985dc10af8adb563d81ce7284b7e1b42a80be23d4d",
      "sizeBytes": 71
    },
    {
      "group": "governance",
      "relativePath": ".github/pull_request_template.md",
      "sha256": "ca53dc2bc45ecb1c2fdae13b8e34e1e631802764aeb9c54ddc6329b3cf8d258b",
      "sizeBytes": 671
    },
    {
      "group": "governance",
      "relativePath": ".github/ISSUE_TEMPLATE/bug_report.md",
      "sha256": "7d37b7a69995b20fe64f57b1a387a3ebcc383058a8ef6d63d6c2d31a1509b95b",
      "sizeBytes": 765
    },
    {
      "group": "governance",
      "relativePath": ".github/ISSUE_TEMPLATE/config.yml",
      "sha256": "761df0749a3e67d2f81d0b78d079f6d1298824d2e394303225ccd8bb62d607a4",
      "sizeBytes": 240
    },
    {
      "group": "governance",
      "relativePath": ".github/ISSUE_TEMPLATE/docs_or_reviewability.md",
      "sha256": "d9eec1ad1693aa02255a4e182c3029c19b3705352f6b5783997693addb59bd57",
      "sizeBytes": 606
    },
    {
      "group": "governance",
      "relativePath": ".github/workflows/ci.yml",
      "sha256": "7e76a0224e87ea7a21009cca3f68463a04184b991a9affdfece4681f691c6e32",
      "sizeBytes": 1717
    },
    {
      "group": "governance",
      "relativePath": ".github/workflows/model-smoke.yml",
      "sha256": "dbb917b4bca1fc4c12924d1818f38f001074c296804dab4d72fe73a9ae908f5c",
      "sizeBytes": 2499
    },
    {
      "group": "governance",
      "relativePath": ".github/workflows/release-artifacts.yml",
      "sha256": "8568d1e668844f199b409e7f1b610baee3a33f034459e97e3f313941e2aad1cd",
      "sizeBytes": 1465
    },
    {
      "group": "root",
      "relativePath": "assets/pbpk-mcp-architecture-overview.jpg",
      "sha256": "5dd83e07dcde0f703841c8d8f4e7dbdd95ecb7e92efb6029ff301d36974066ca",
      "sizeBytes": 56010
    },
    {
      "group": "root",
      "relativePath": "assets/pbpk-mcp-architecture.jpg",
      "sha256": "431f9b7ea0cddca39629d20379b78d93e6488de2dbadeeae446609fc67e869bd",
      "sizeBytes": 98260
    },
    {
      "group": "root",
      "relativePath": "benchmarks/regulatory_goldset/.gitignore",
      "sha256": "86532d2a1590a157435fe3c5bde20ea6f64aba8bfbf694858b6de8c48d702a0e",
      "sizeBytes": 22
    },
    {
      "group": "root",
      "relativePath": "benchmarks/regulatory_goldset/README.md",
      "sha256": "3da4d18c8a96049148b26bcd17f37e14e853481b3974e21b4ab8a8dcd9baef14",
      "sizeBytes": 3890
    },
    {
      "group": "root",
      "relativePath": "benchmarks/regulatory_goldset/fetched.lock.json",
      "sha256": "949db5491f40406ab4a0fc185952795bb88f1243ac5c4a3ead1b4fda7661ddca",
      "sizeBytes": 26593
    },
    {
      "group": "root",
      "relativePath": "benchmarks/regulatory_goldset/regulatory_goldset_audit_manifest.json",
      "sha256": "21af57a4b41416ab79cfa86bd58c4582f5834218adad033b8c4b3bb65967931e",
      "sizeBytes": 24492
    },
    {
      "group": "root",
      "relativePath": "benchmarks/regulatory_goldset/regulatory_goldset_scorecard.json",
      "sha256": "212987469243e7b32a06f41cdab74c21b931f4540b12ab6a492baeff6dcd967a",
      "sizeBytes": 84980
    },
    {
      "group": "root",
      "relativePath": "benchmarks/regulatory_goldset/regulatory_goldset_summary.md",
      "sha256": "9bb0eb45eb571d57a30622665b8caeeaaca0e31114edf83554facbe11083d944",
      "sizeBytes": 8415
    },
    {
      "group": "root",
      "relativePath": "benchmarks/regulatory_goldset/sources.lock.json",
      "sha256": "ba24143cfe7ddd976779d7c60d24754b35f8ecf0d361e15c8ad247e488af337b",
      "sizeBytes": 4225
    },
    {
      "group": "root",
      "relativePath": "benchmarks/thresholds/smoke.json",
      "sha256": "5ed1ca3d81b8f8905e8a15d4e69a9e9ebde23f19f46345cc58ec6bcd91e79f55",
      "sizeBytes": 364
    },
    {
      "group": "root",
      "relativePath": "compliance/sbom.json",
      "sha256": "51d1cc78c8c9ee50002459ea29521ee42c758deb8c2087f22352b9a04e76b33a",
      "sizeBytes": 224118
    },
    {
      "group": "container",
      "relativePath": "docker/runtime-refresh.Dockerfile",
      "sha256": "e4994e1a9aea205d009ca48abfb0f1c9e4816bf61c9600fa73e72f596bfa7235",
      "sizeBytes": 982
    },
    {
      "group": "container",
      "relativePath": "docker/rxode2-worker.Dockerfile",
      "sha256": "df5dc72543840410c9b0bcc66f6332169269e6bd94f0e6d5979a69c632b4ec4e",
      "sizeBytes": 2794
    },
    {
      "group": "documentation",
      "relativePath": "docs/github_branch_protection.md",
      "sha256": "a5ba0c3f74f201b215e5bedd019c7402a7f70b84c03652b27a6112f03fa4c062",
      "sizeBytes": 1900
    },
    {
      "group": "documentation",
      "relativePath": "docs/github_publication_checklist.md",
      "sha256": "bc30081bb753562a1a32272fe215c092c4940941dcc99cb98c247b6f7cb6fa2f",
      "sizeBytes": 5217
    },
    {
      "group": "documentation",
      "relativePath": "docs/hardening_migration_notes.md",
      "sha256": "7cb8c35e428fd1a521bd3c7dccd9ad5055389a547390568c8b431147badd1463",
      "sizeBytes": 5359
    },
    {
      "group": "documentation",
      "relativePath": "docs/pbk_reviewer_signoff_checklist.md",
      "sha256": "12c8ff065ae36a0ae1f3a94b635d6635ad2b237ecf4755eb2ab2a457dccb336c",
      "sizeBytes": 3372
    },
    {
      "group": "documentation",
      "relativePath": "docs/pbpk_model_onboarding_checklist.md",
      "sha256": "c3ac775a33d357fceac2d74ecd65d1e7d9f3dafa2166fa71f969217b02d56185",
      "sizeBytes": 5727
    },
    {
      "group": "documentation",
      "relativePath": "docs/post_release_audit_plan.md",
      "sha256": "cfedfabd7a0943f94b8afba4d2d0f9b85c8b9225f955bea7e3c331bd316583f5",
      "sizeBytes": 2831
    },
    {
      "group": "documentation",
      "relativePath": "docs/release_readiness.md",
      "sha256": "0f163cfda361e833c18f82591b4ddedcde7316f965def32810a99f28f7e685eb",
      "sizeBytes": 3879
    },
    {
      "group": "documentation",
      "relativePath": "docs/adr/0001-audit-storage-boundary.md",
      "sha256": "cd8ca8f330ef911cd0c4b4cd6087323e85dc136247a4f77c9dd81871d0646666",
      "sizeBytes": 1933
    },
    {
      "group": "documentation",
      "relativePath": "docs/architecture/capability_matrix.json",
      "sha256": "bdc2169d99343f38c5a7dea91306d46704104d488442e4161812dfb63ac6da03",
      "sizeBytes": 4092
    },
    {
      "group": "documentation",
      "relativePath": "docs/architecture/capability_matrix.md",
      "sha256": "f239bd8632e5bf325f79ab530e7fa7bd7e3cff3bfc2e2d2b2bfa3bd047f97a59",
      "sizeBytes": 2721
    },
    {
      "group": "documentation",
      "relativePath": "docs/architecture/dual_backend_pbpk_mcp.md",
      "sha256": "4a68ce06000174ba1e2379fc4f008ceb7a1f1cba8d4cd418ba8a72adb3e567ab",
      "sizeBytes": 19578
    },
    {
      "group": "documentation",
      "relativePath": "docs/architecture/exposure_led_ngra_role.md",
      "sha256": "782b28c3770556b5d724f75e5135104be15faa4ce3c5023fb4676c9d6ed855f8",
      "sizeBytes": 4612
    },
    {
      "group": "documentation",
      "relativePath": "docs/architecture/mcp_payload_conventions.md",
      "sha256": "2bd79754995a99b2f7c679b336a5b9e4e91373714d3e64ddc933da4edcd0ee02",
      "sizeBytes": 18585
    },
    {
      "group": "documentation",
      "relativePath": "docs/architecture/ospsuite_population_feasibility.md",
      "sha256": "5e9ced2e8fff2afb17473a7231c587599bbddf505017307b21661d8ed22d6988",
      "sizeBytes": 2247
    },
    {
      "group": "documentation",
      "relativePath": "docs/architecture/sensitivity_v2.md",
      "sha256": "5340acad459c247e6c968e42a5139eb0ea1e35af92b3f5e0a9a27795d8083658",
      "sizeBytes": 2619
    },
    {
      "group": "documentation",
      "relativePath": "docs/architecture/toxmcp_suite_index.md",
      "sha256": "55484334139441cd2f806751ecb9e7e0e8ee0afd48873cc8439a2b8d31773c0e",
      "sizeBytes": 2684
    },
    {
      "group": "documentation",
      "relativePath": "docs/compliance/license-review.md",
      "sha256": "bfe66ba25a65c284160291ac220fb2103c641c22ac4ff5c2fceb8ce317f75825",
      "sizeBytes": 2389
    },
    {
      "group": "documentation",
      "relativePath": "docs/deployment/runtime_patch_flow.md",
      "sha256": "3ff324ab6b039c32690ef7f0a7de4f6543ce5d8524c557eb91b70d73fe01a32c",
      "sizeBytes": 9450
    },
    {
      "group": "documentation",
      "relativePath": "docs/deployment/rxode2_worker_image.md",
      "sha256": "daa2d9d531663abe5de8559fada45c98c251f3fdd150a1d6c62ea5dbd437f219",
      "sizeBytes": 4854
    },
    {
      "group": "documentation",
      "relativePath": "docs/deployment/s3_object_lock_audit.md",
      "sha256": "e7538d8fcf32f2b6e5f140d1b09bb77bc7200c3f64a396f760136021272b3d3d",
      "sizeBytes": 3596
    },
    {
      "group": "documentation",
      "relativePath": "docs/governance/retention.md",
      "sha256": "0129e2fdbd37d13cd3c0f2a55cea928a2ebc5bf7d0117f3dc963ef6f86d62b68",
      "sizeBytes": 1833
    },
    {
      "group": "documentation",
      "relativePath": "docs/integration_guides/ospsuite_profile_sidecars.md",
      "sha256": "f968f67bf69baf08ee70ee2a62997d915b744f280056f61dfb80e67e9bbde1a4",
      "sizeBytes": 6952
    },
    {
      "group": "documentation",
      "relativePath": "docs/integration_guides/parameter_table_bundles.md",
      "sha256": "82a258a35db32a4b5e7fa15177510af0f593e8fa0756eea425f2e3b411d7fcd6",
      "sizeBytes": 5055
    },
    {
      "group": "documentation",
      "relativePath": "docs/integration_guides/performance_evidence_bundles.md",
      "sha256": "5d217cf711892ce068e2d51e15a9b4462cd2c6d54f19568f6789145d9920d2e0",
      "sizeBytes": 8081
    },
    {
      "group": "documentation",
      "relativePath": "docs/integration_guides/rxode2_adapter.md",
      "sha256": "2e8e2ea0e9d941944d1b0c1db34e517734ec1c7cfb2af715413703d1bcca7bcd",
      "sizeBytes": 11871
    },
    {
      "group": "documentation",
      "relativePath": "docs/integration_guides/uncertainty_evidence_bundles.md",
      "sha256": "1627966c2fb0563e2414b9e41f486d736084113fd8e5649cb30455488ebf7801",
      "sizeBytes": 5649
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/agent-architecture.md",
      "sha256": "f9788221e829d9b78aae3f05b8c539de0792707e6b3992720d3a0023a934e566",
      "sizeBytes": 7836
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/agent-prompts.md",
      "sha256": "0303038db96f6c0c56672290f38299610593a2d275c4207fec4d947795722272",
      "sizeBytes": 4030
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/agent-usage.md",
      "sha256": "930777b8769913d122ecdee278f3e50f9900aa6f2fa1af4a9b242c04c18dfa2b",
      "sizeBytes": 4468
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/architecture.md",
      "sha256": "a3da8c3b392fb3a8c85295d2f0770dd8722a5fc3f33ecc8992ff5335a9cda236",
      "sizeBytes": 5962
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/audit-trail.md",
      "sha256": "bb9b975278852b446db42d816e654682bfb0cd6772f059d799a5a4a3868cef98",
      "sizeBytes": 7716
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/authentication.md",
      "sha256": "bdbe1bca7f990c6c84cefdc53a658ab5d6472ae84cd4d08a93ce67f4ee1fbd3d",
      "sizeBytes": 7162
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/deployment-checklist.md",
      "sha256": "05214d65d3cc18bab4e49261c080a0a6e90b97443e8ada54e6942b8595db9b49",
      "sizeBytes": 2876
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/distributed-job-architecture.md",
      "sha256": "be5d043393378e76ca7749bd4f7ddbc2da9b45805890d0f3b1341e4abc210b89",
      "sizeBytes": 5760
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/documentation-plan.md",
      "sha256": "55a0f51d1e2af569c19308bb7f0fb96293556bef41d45e263d7cd92ec9be5e73",
      "sizeBytes": 6072
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/monitoring.md",
      "sha256": "c28054174663eb592849c5f80766994389e1d2ddbb64f161bb1353aa4c6aab3e",
      "sizeBytes": 2105
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/pdf-literature-pipeline.md",
      "sha256": "2be644c8a4575a37f1529a284526dd859e4121a2c4f1829183cc8147e05e0f79",
      "sizeBytes": 10365
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/performance-plan.md",
      "sha256": "d42163d3e952fade3dc97858d7578378bc3ae728fcb9d737d13c8cf82eb214a7",
      "sizeBytes": 11083
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/performance-profiling.md",
      "sha256": "8d02427a284143d96923b4610a720ffcf9d11aeac358dd7de89cba10125ba49e",
      "sizeBytes": 3664
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/performance-roadmap.md",
      "sha256": "1e7041f683ee053d48144be06f79aafdf0faf192daa0e44692cc032654039ed8",
      "sizeBytes": 6243
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/population-simulation.md",
      "sha256": "c3086d3e7cf243b98dbde319bf186004a9883e09569d8e07ee211459bc2f19e4",
      "sizeBytes": 6605
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/requirements.md",
      "sha256": "a330d7c3e234094d3fe543f76406735ae3836f2515c40f594026a1c2b82a5d99",
      "sizeBytes": 3782
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/security.md",
      "sha256": "125b51ac84f9be2fc5524d71ca1855c00e0ea1b5f4e3587136e9b3ab3350d830",
      "sizeBytes": 1326
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/sensitivity-analysis.md",
      "sha256": "2cc7f56291d17135e8a24a1ad34ea7899d40bf93440539fa6456adf8e7431620",
      "sizeBytes": 4401
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/threat-model.md",
      "sha256": "6fa83e802963860ddf9385cb06bbcbd7f64e394db2105857f9f55d29e8ee8023",
      "sizeBytes": 7490
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/contracts/README.md",
      "sha256": "20f9dddb82165c87355769c69ddcbfcd983d4bc8def13072b49ed4db7d3b2bde",
      "sizeBytes": 523
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/contracts/adapter.md",
      "sha256": "fe91c27d7c5e006d503fc421753a4faa2db081b1bba8249e241a5b9658e9fc92",
      "sizeBytes": 5204
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/contracts/error-taxonomy.md",
      "sha256": "78516e7f6b6a070e3af8fb3d3e7db07f2c1779a51e93278d55017ff5c4f44ff2",
      "sizeBytes": 3139
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/contracts/openapi.json",
      "sha256": "2cdae40512efcf0bdf7b4ba5c4d4c73a2f4e869a5ecd8f6622fcf8e5a0ada760",
      "sizeBytes": 94687
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/contracts/sequencediagrams.md",
      "sha256": "d5b4244865b0e9eba60732c0740f7aac00234c231f1881cf868c800e6f6a7395",
      "sizeBytes": 4494
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/getting-started/quickstart-agent.md",
      "sha256": "acd2582c8634127f2f2aba1531dacffb3d8c1df2bf42eddb771c2980b4d15282",
      "sizeBytes": 5684
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/getting-started/quickstart-cli.md",
      "sha256": "09f5f36999785d3e7020151311192a2f46e56aed116b961f06f824e2d4dc4d98",
      "sizeBytes": 9842
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/integration_guides/CLI_TESTING_RESULTS.md",
      "sha256": "27a5064b03ddfe54e8b6ebd1af18ee1644054de5b35a54d99158990445aa7ed0",
      "sizeBytes": 6134
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/integration_guides/OSPSUITE_VALIDATION_PLAN.md",
      "sha256": "d7f14193ed46abc80dbaee60e13551fdc9cb4de65d5b8b244c7f919f484104d9",
      "sizeBytes": 7567
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/integration_guides/codex-cli-workflow.md",
      "sha256": "5df2b0a72f8ed51ae01306ad0810aaaf14845548b5ffba42d295cbfe8a2aafa9",
      "sizeBytes": 12813
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/integration_guides/gemini-cli-workflow.md",
      "sha256": "de274ef40b3cbcb37101e15874e6fcbc65dc4dfe9100b808b368b6a84145bb7b",
      "sizeBytes": 9922
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/integration_guides/mcp_integration.md",
      "sha256": "4024fb141286ec312410a589195b27ca639f798d74f4403f3d6c4a32002ef836",
      "sizeBytes": 4394
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/jobs/celery-ga.md",
      "sha256": "c1b0342d5c55ad10c84482e2c88862f858df9f6973a21a8a660c823955b2fe4b",
      "sizeBytes": 4529
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/jobs/retention.md",
      "sha256": "ca18806aecd48078b1f375409e262d0883483412fa52d1b94a21ebab52e38d9d",
      "sizeBytes": 2597
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/literature/goldset.md",
      "sha256": "3e3005bb9730df064f5f430022c29cd19863aefe06f26dad6dfc0a2db4f3aae8",
      "sizeBytes": 1949
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/monitoring/grafana-dashboard.json",
      "sha256": "2e50d064f049dbcb59c23b5fe984b5f81e2752d8d93c7ee05b5b23a07e14ce91",
      "sizeBytes": 1902
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/notebooks/population_simulation_walkthrough.ipynb",
      "sha256": "ad4c5fbd5e02f799486758f04e8b609b49f374fd9e43d5d185dac6c0eeebaeed",
      "sizeBytes": 5984
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/notebooks/sensitivity_analysis_walkthrough.ipynb",
      "sha256": "3ae50bf2362144f923010605e192821cf107c87583a509369fdfdc87664ebbd8",
      "sizeBytes": 5927
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/operations/audit-runbook.md",
      "sha256": "2f76803c8ad3a8ceaa9d4464e3f5fc971c3c37df17b4c7eae5cbcc6bb4051876",
      "sizeBytes": 5100
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/operations/celery-runbook.md",
      "sha256": "8002e8ce2c0cbc9ad90cb98d72a80d635fce8918edf1a220a32665b2522b488c",
      "sizeBytes": 4905
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/operations/change-management.md",
      "sha256": "f4243ec76b88594cb8f6386a202a09776ab85e5e61d89849a925de8c6af66051",
      "sizeBytes": 2924
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/api.md",
      "sha256": "cedb4672cedeb49cf5e3f72dfb8e8e1b9d89a2964fbb5e123dd92db7ccf7349c",
      "sizeBytes": 6509
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/compatibility.md",
      "sha256": "327a835369458fec04eb63f8d35cfcfcaffef13d92ce7dfc4c334da1b1e9a2b3",
      "sizeBytes": 2110
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/configuration.md",
      "sha256": "4fe387f93ed8a2e218598fbc11ef09ed72ff047cdc7bf60715453f4e149b3668",
      "sizeBytes": 4762
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/calculate_pk_parameters-request.json",
      "sha256": "53bc6546fecbc109503114d5f6d4116662029cb3e9a7412d87350b4b68ddf1ce",
      "sizeBytes": 549
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/calculate_pk_parameters-response.json",
      "sha256": "516594800d45f66e9fae9ce4002697e21bc4780821b2ce941511cdaf5d261501",
      "sizeBytes": 1663
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/cancel_job-request.json",
      "sha256": "38087c662de0e590325e7a27d6fa0deb51bd00b0a2ef2a21d261fcfbefe29a95",
      "sizeBytes": 284
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/cancel_job-response.json",
      "sha256": "40dd3e67d820a36d8651dc28c548a1f08567940075af9c4d90f1feb66ebe5bcc",
      "sizeBytes": 340
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/discover_models-request.json",
      "sha256": "512cf5053040f4135baf995eacbae45e23ed1a2463d8cb85227db74a05519ea9",
      "sizeBytes": 808
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/discover_models-response.json",
      "sha256": "863fbaf60dbcda0a2286d4a6abd16c3730d55fa631de27ad1c172bdea8dccef7",
      "sizeBytes": 4563
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/export_oecd_report-request.json",
      "sha256": "4199086589f008ee4349f38811cee0ced8222033db1317221bca8c86ecddb425",
      "sizeBytes": 847
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/export_oecd_report-response.json",
      "sha256": "a19e5356449f312428360ebef7abeb89e661505f76f0abfb7c3697aebf4c25ce",
      "sizeBytes": 1301
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/get_job_status-request.json",
      "sha256": "46e5bc645478335701270a57c5da4008fe55c0ba688638eeef9e15f9bb03b6d4",
      "sizeBytes": 299
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/get_job_status-response.json",
      "sha256": "e4c56f74273c647ed2801ca5bde0a13341f34423130ec08f57a016e2b60c8831",
      "sizeBytes": 5481
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/get_parameter_value-request.json",
      "sha256": "7f3a3600f53e2e732df1ef3e6dc6dbd804b91dd994853bf9274d179cabd16139",
      "sizeBytes": 460
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/get_parameter_value-response.json",
      "sha256": "1444cec6cbe77ccec792d9488597573e230799801647228aafb0e8ab0e6bface",
      "sizeBytes": 1405
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/get_population_results-request.json",
      "sha256": "a83920edef8ed8832427e000626fe3ade4ae5352b8f2f3f62fb810a8793aab9d",
      "sizeBytes": 223
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/get_population_results-response.json",
      "sha256": "f7a7020ed2d09acb7ca0c8a330cfbc59a1c06744c8cd953b45e0fed3eb7f99bb",
      "sizeBytes": 3220
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/get_results-request.json",
      "sha256": "8334a906b4ad83ee61c0caec3c771b629a5ad320f4e47fb65429040fb8d98435",
      "sizeBytes": 213
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/get_results-response.json",
      "sha256": "a99e5213a855c30652506c9f9614d606f74564515815f780843516be4647da9d",
      "sizeBytes": 1683
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/ingest_external_pbpk_bundle-request.json",
      "sha256": "f42bffd5b82818a3337a1c7ac93434a279afc94238eb6d525322ed07932722e2",
      "sizeBytes": 3549
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/ingest_external_pbpk_bundle-response.json",
      "sha256": "b7d994d11d8e30887a5e7b385ae2e9cdfcbdd137f68cf9d5ae97e14d5c9c0b45",
      "sizeBytes": 687
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/list_parameters-request.json",
      "sha256": "4ed8c6e1000ee09fe407e6c22e4cb5d38bd6a3e9303ad8f2c84aa4cb9928ffb7",
      "sizeBytes": 526
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/list_parameters-response.json",
      "sha256": "8b9adf0a7dd87fbe0c738fe8ce90262ddd43cc8821e71ab0b3ee75df7069a7c8",
      "sizeBytes": 249
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/load_simulation-request.json",
      "sha256": "197fbd57ae6ceb69cd34f48a743c5efdce93fade2da930aa644f3422debd4ac6",
      "sizeBytes": 520
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/load_simulation-response.json",
      "sha256": "9ed7b601da30445eeb003e88f300434bc47f9a0a85bb62c3c1fc6fc6fdd606db",
      "sizeBytes": 3053
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/run_population_simulation-request.json",
      "sha256": "481138e4899a2af49f16808d923561d7fa151096ad4f728ddba4ad4007495e1e",
      "sizeBytes": 2568
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/run_population_simulation-response.json",
      "sha256": "665e8dc109ca3ed3988f603685afecc3f25cf170973ed9f7ff6ad43a131bb91b",
      "sizeBytes": 679
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/run_sensitivity_analysis-request.json",
      "sha256": "b9d08583f1e14eeee447f60266c28edb10d36d9b11c15a37a3fdafe3df448b55",
      "sizeBytes": 2928
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/run_sensitivity_analysis-response.json",
      "sha256": "8b42ee6faf2b9ca44b2527e758939b33beead1dc0f7bc2d1af08ccd973d52302",
      "sizeBytes": 1185
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/run_simulation-request.json",
      "sha256": "ff03a7cefeeee0d92ff622e7e955a496ae04c29a309856916aa83a5285ea3308",
      "sizeBytes": 1015
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/run_simulation-response.json",
      "sha256": "8b245623a4a09ab8b9f30ad0961b7e9124005601ab5e133f6f3e166b774f4e7a",
      "sizeBytes": 664
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/run_verification_checks-request.json",
      "sha256": "205175d9fd5ff698008e88873465a92e0dbca06f0a31911d6685160ffce69f8f",
      "sizeBytes": 749
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/run_verification_checks-response.json",
      "sha256": "d99d6d5c25e5830cb521528fdc06a41c63c981d7169089b07a07c50ed9904e88",
      "sizeBytes": 1674
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/set_parameter_value-request.json",
      "sha256": "41460671bc3d43af3f1452af273a0f19846078f62c736bae924eae229b2edf38",
      "sizeBytes": 1118
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/set_parameter_value-response.json",
      "sha256": "ecd3427dc4917ecc60427cec0b7091add47699286fdad8582577fea08aaada81",
      "sizeBytes": 1405
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/validate_model_manifest-request.json",
      "sha256": "a70aa3370b9b613b03649361d16070e313640605d64288110c13c3b874c2dd43",
      "sizeBytes": 221
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/validate_model_manifest-response.json",
      "sha256": "8edf8a60261baf85ef3209e2d084858b97d260b4ec3912117e96b01ca029a4d3",
      "sizeBytes": 862
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/validate_simulation_request-request.json",
      "sha256": "ee45460b69048dadcf9c5f1e3c20af31027a743f9fbb7b54cbe123a90f4cf2f2",
      "sizeBytes": 556
    },
    {
      "group": "documentation",
      "relativePath": "docs/mcp-bridge/reference/schemas/validate_simulation_request-response.json",
      "sha256": "d119131d7c6352355f0b69a41dfe28e34def4fc5f1041507e4c3a03336345d41",
      "sizeBytes": 1481
    },
    {
      "group": "documentation",
      "relativePath": "docs/monitoring/README.md",
      "sha256": "d6fb59d3c36df2e45622a8b1dd670e318151029c2c6b7da32b2874e44514f028",
      "sizeBytes": 2078
    },
    {
      "group": "documentation",
      "relativePath": "docs/monitoring/grafana-mcp-bridge-dashboard.json",
      "sha256": "14726b03863df27f0e694744caffe7ba442565aa942c6c329a9b84b0de75d9b3",
      "sizeBytes": 9204
    },
    {
      "group": "documentation",
      "relativePath": "docs/operations/hpc.md",
      "sha256": "80e05a9ba2ead4930fe46f9703d618d5fd0e7ae384d7dd06c275ee7434fc674c",
      "sizeBytes": 3096
    },
    {
      "group": "documentation",
      "relativePath": "docs/operations/runbook.md",
      "sha256": "83c8490f2ed7decdb40f8eb0fb26bac30b0793bac660ef8fcc509d1d281d2eb3",
      "sizeBytes": 6484
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.2.0.md",
      "sha256": "215480cd86234f2814ea69048fed36cbe0f10868693d24fe3bdc4b255d0acdce",
      "sizeBytes": 2847
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.2.1.md",
      "sha256": "26621b1c5f33eac681d2feb9ef09cbb4e028dcf80d5e6aef60c83dcf8d170326",
      "sizeBytes": 1463
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.2.2.md",
      "sha256": "53bee37d11dfe7225644f612fa00ff80e363d1c6ad9e5544c079bf164b14386f",
      "sizeBytes": 3047
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.2.3.md",
      "sha256": "d1bbffe9959df7058764a60d589af660bf32469d9ff7dd2e00620f0a85bbec06",
      "sizeBytes": 1720
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.2.4.md",
      "sha256": "54b77ec32e1e53995335d242f8ebeb775b8790976463a4be1de8d02e9c8db59f",
      "sizeBytes": 3080
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.3.0.md",
      "sha256": "4f3c93838d27cc42ae24f46a4548ee5d9aa3355f1465ae2ecddeb5ea83fa9ab3",
      "sizeBytes": 3225
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.3.1.md",
      "sha256": "46ba36a2b5266b48c2fa1eea3957b5b5046f5422368530ebf6b6a66383f3ba15",
      "sizeBytes": 3298
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.3.2.md",
      "sha256": "c0eb95e77d0b068608b95f2625d0a1d6fd72b6d00f661b7e9a888c462a41a336",
      "sizeBytes": 1689
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.3.3.md",
      "sha256": "374b8a2b53012acb969778a9d25c1f52faba34e276e6b59aa495db319ac83068",
      "sizeBytes": 2199
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.3.4.md",
      "sha256": "840a858c5abdc942c540af2876612311d6939d269218cdaeb81af8802ba27c09",
      "sizeBytes": 2339
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.3.5.md",
      "sha256": "5a8e179425d42a8d62f5ee2bf748cc8ae7ca8b996406e3ef40e550ed34ba8d4e",
      "sizeBytes": 2635
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.4.0.md",
      "sha256": "fc1ae6194fba91e39b586c4de1105a3130b606e8573d9cb230c9a462408530d9",
      "sizeBytes": 3891
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.4.1.md",
      "sha256": "658d7a25178aa0dddfc0bd4c5e1dd24f9b4fc26186f8aa741752c83555c5912c",
      "sizeBytes": 2336
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.4.2.md",
      "sha256": "fa0d6eb9eeabbf715bb673a2fd43bc057d479e9be7ff5d29c9f2cbd3fde46108",
      "sizeBytes": 1884
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.4.3.md",
      "sha256": "48265243ab0123bcc3b12b270492bdaa98ae4a73de8d43adb704ac329b68ca95",
      "sizeBytes": 2974
    },
    {
      "group": "documentation",
      "relativePath": "docs/releases/v0.4.4.md",
      "sha256": "356dac1f44b05a2d3da6a39fdc5772a3fa847d6174557b59a7d7f128d46e822a",
      "sizeBytes": 3730
    },
    {
      "group": "documentation",
      "relativePath": "docs/research/ocr-benchmark.md",
      "sha256": "4a9467018cbf619d0157006e5940bd3c334b02e31eb221e090d83275bc0b5816",
      "sizeBytes": 2348
    },
    {
      "group": "documentation",
      "relativePath": "docs/research/ocr_benchmark.json",
      "sha256": "62190155cef49207b5caa71a3c3dcfbc32ce0acba1ae7fee8ef04bf9a85d0035",
      "sizeBytes": 439
    },
    {
      "group": "documentation",
      "relativePath": "docs/security/hardening_baseline.md",
      "sha256": "6da1916d95bf5884362e33393a5b73a46ea0ed401ac183c929e89a0f4ea5b00a",
      "sizeBytes": 4713
    },
    {
      "group": "documentation",
      "relativePath": "docs/tools/cancel_job.md",
      "sha256": "6a9a134bf2971468e5c8cf645d766b19f6cb0222368d343cc997d2b4ac4e4bfe",
      "sizeBytes": 2330
    },
    {
      "group": "documentation",
      "relativePath": "docs/tools/get_parameter_value.md",
      "sha256": "a0854fcbe538b9204e28e41480174ba93345978976dbec8c8a34ff6b428ca43e",
      "sizeBytes": 1654
    },
    {
      "group": "documentation",
      "relativePath": "docs/tools/list_parameters.md",
      "sha256": "d5d08bfd7e3633f99a56c0a2699f6f03b998d71c857b969de0511bbc14833a84",
      "sizeBytes": 1846
    },
    {
      "group": "documentation",
      "relativePath": "docs/tools/load_simulation.md",
      "sha256": "c18a4376570e5634c416536424e562c767c30f3a8c9f70ac1e0de7699cc8771d",
      "sizeBytes": 2589
    },
    {
      "group": "documentation",
      "relativePath": "docs/tools/run_sensitivity_analysis.md",
      "sha256": "6f051bcb4306e87fbe6d163e2bd426f88d7ef24e6165e7e2b62cf90a72198290",
      "sizeBytes": 2916
    },
    {
      "group": "root",
      "relativePath": "examples/01_brain_barrier_distribution.py",
      "sha256": "624d49a2f38d485c26ebe4b894918fe92589b6f10cff1ff28ce59e707a8f391f",
      "sizeBytes": 3393
    },
    {
      "group": "root",
      "relativePath": "examples/02_liver_volume_sensitivity.py",
      "sha256": "3699b642e73a6d6ea9f4b81bb6fabd44f501826a444d93fec68b89ad037ed014",
      "sizeBytes": 4601
    },
    {
      "group": "root",
      "relativePath": "examples/03_virtual_population_variability.py",
      "sha256": "663ffbb01e04f76865aebb81a8541be4b65318519371be788fb4e2384a24dd42",
      "sizeBytes": 3303
    },
    {
      "group": "root",
      "relativePath": "examples/04_parameter_exploration.py",
      "sha256": "8bfbfa59d86da684c22cb59cba5c2fd13520aa7aff6d3e663a79d24128fb7a64",
      "sizeBytes": 3254
    },
    {
      "group": "root",
      "relativePath": "examples/05_job_control.py",
      "sha256": "d61006d69dd26623d3fbb7a4d799a472cb52492408a21b0dca359e0d39fa20c7",
      "sizeBytes": 2155
    },
    {
      "group": "root",
      "relativePath": "examples/06_sensitivity_tool_demo.py",
      "sha256": "b1b39f2d5b15159eccb5b56dba74ebd1cfe2963c2f8df82f9fc39fb7dccc8067",
      "sizeBytes": 2601
    },
    {
      "group": "root",
      "relativePath": "examples/07_chlorpyrifos_risk_assessment.py",
      "sha256": "5e828c361de1b57c49aa6dd18a3bc692733673a3bfb5e96903709f7e6447ce63",
      "sizeBytes": 4140
    },
    {
      "group": "root",
      "relativePath": "examples/README.md",
      "sha256": "9ea725b849627b50144faa928880d902d50adc83a5a4b0365c6725987b096b59",
      "sizeBytes": 2697
    },
    {
      "group": "root",
      "relativePath": "examples/output_01.txt",
      "sha256": "5ceffe2de366117b3d4c5f26cd9c2a634c8dea12511fb8deebe74c07174701d5",
      "sizeBytes": 768
    },
    {
      "group": "root",
      "relativePath": "examples/output_02.txt",
      "sha256": "f7f27dc07b399f3aef87f26bb2bd8a542148310e6083b595e54dac880b9075c9",
      "sizeBytes": 416
    },
    {
      "group": "root",
      "relativePath": "examples/output_03.txt",
      "sha256": "b8b389566026c2b9e1dec5e43c02e61a3b2f86b440f2084d6f06a0a5dcc27fee",
      "sizeBytes": 383
    },
    {
      "group": "root",
      "relativePath": "examples/output_04.txt",
      "sha256": "31d24e713f19cc5aad1974637607eec4f14a34b5e2e9ebb576a732c56ab763f6",
      "sizeBytes": 430
    },
    {
      "group": "root",
      "relativePath": "examples/output_05.txt",
      "sha256": "c26149d5805984e890c7d813de8da51106797f9defd659882459291a15af91ad",
      "sizeBytes": 375
    },
    {
      "group": "root",
      "relativePath": "examples/output_06.txt",
      "sha256": "1c79b77c5bba69b2672b7726c656a26f774ff86ab474c928871032f336409ccc",
      "sizeBytes": 514
    },
    {
      "group": "root",
      "relativePath": "examples/output_07.txt",
      "sha256": "1d17e105f436c41f446c3e3f81cd4aede9c5e8dce84c657479a3da8f78810405",
      "sizeBytes": 776
    },
    {
      "group": "root",
      "relativePath": "examples/parameter_table_bundle.template.json",
      "sha256": "aab70959a1d5a5d86b27d0d78ca450c9774331926dda7d21ae2878c9635f62ee",
      "sizeBytes": 2567
    },
    {
      "group": "root",
      "relativePath": "examples/performance_evidence_bundle.template.json",
      "sha256": "dc5d8d4cd09b801f6edd8656cb3ed6838893df5120517bd373e2d90e0c44f134",
      "sizeBytes": 3632
    },
    {
      "group": "root",
      "relativePath": "examples/uncertainty_evidence_bundle.template.json",
      "sha256": "8acb3b54c24d447d237255acc20fb115b46d7fdf385ddd14c68e850f3246985d",
      "sizeBytes": 2402
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/index.json",
      "sha256": "cc949bba016c5270866cf4dc522502bb67490968ce69e619339b9b549d7561a0",
      "sizeBytes": 6475
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-001.json",
      "sha256": "33043213fedd2f9b1d8568d97329cb6265fae5b8c3346ddd857eb8c8c8d96485",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-002.json",
      "sha256": "fdb1800c9b2117a322fcfdbccaad78abeb23bfb8b4beb465e9f9a2e1bfd13756",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-003.json",
      "sha256": "0a79f835ae62b977fa13cc3a173dfc3c2e247843ab5b1f439415d4da4ff18602",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-004.json",
      "sha256": "962022a5f8abbeff427fb0be3dde3a6552659ed6952510272a4cabd7cead5264",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-005.json",
      "sha256": "9ca74877367a77ff8106681539a5773a0918f92b44cda1e624b6b5893b8c0713",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-006.json",
      "sha256": "39cfae6a15b2592323051b20d254f67834ea8eea0ab5f1cab0c457b35bbc8da3",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-007.json",
      "sha256": "daa4c9c18041c7ade3e47f0b986c778dcbabb8f4713802053d271832ac6a360f",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-008.json",
      "sha256": "c6271639d06f623e25f884d373077938a7d140b24f2fa550f596ee69c176f8b0",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-009.json",
      "sha256": "2d1050e1157a968ce26e546867e72b3d6e5ed6d8f5b863c1b4ba229d0133c98a",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-010.json",
      "sha256": "cc69615f3b170eb2eacdab98459c56aa611229f30a89ea154191e825711da81f",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-011.json",
      "sha256": "46c63677f2c5de844ab891ceca12b495bbe4f4807b7c4b8fa67e34af561aff24",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-012.json",
      "sha256": "8b37f4bd507cbe13d819bc3fb1314eacefae5a383f58174e7eb2693883308141",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-013.json",
      "sha256": "a07152a5117a82e1e4644851b01b6b6b15e7cff0b765f4dfed24a484360ced9b",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-014.json",
      "sha256": "c8097df00434574d23bff2332f2b8a7f4901888995010d115e0d0bf0ddfd5511",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-015.json",
      "sha256": "06981a9779b891589ed72ff14958ec67a8e261290ff2eb43e9a4afb64478a4a3",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-016.json",
      "sha256": "f98111beff0a1a9eb468ba1d87d4bdd941d1c9bcb75b2423cf8f0309c6af03b1",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-017.json",
      "sha256": "ff3675bd2d37854d533d681e522e6767a7f81baa0c3777ecc85fd2d46c3fa4d7",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-018.json",
      "sha256": "8ef731e0be990fe2dee9adb4e144bf535cd0f63c3afbc7a20fab7bfd0ee8f4bb",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-019.json",
      "sha256": "490e595f94b55ce9518cd6bfda7772618b9b0af53509bffe774015ace8068ec5",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-020.json",
      "sha256": "bb260d3e32bbd60fcdbd51e09ab971f6fcb943a4e5ea36294e8c6e4a5c97749b",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-021.json",
      "sha256": "2f524e3007c607d7d705e84e18d56b437400502f3a22e81a7cfa1de1efac78d5",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-022.json",
      "sha256": "a5f5617b53a045e719aa5597045f594d0f2731189c90d8bf0aacdbc6175964f4",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-023.json",
      "sha256": "b2eb74623324256089a30a3ee01699ddf36285b724f5c6885d1dd8c04c372302",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-024.json",
      "sha256": "053b9ba6e900a74f10fb28321f1cbedb31debf0900a51f39c8ec2137f22993a1",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-025.json",
      "sha256": "a7a98c26751c0f0f556cf8a9730fb7f96d23a6f28e6937700cbd14b1611e67b2",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-026.json",
      "sha256": "bca2d801b6e426c3de3fe4f0a5ca0395fa5dba88fa789fd578b73c42bbacb208",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-027.json",
      "sha256": "0665c51175dd0631c10bf2de92c46ad55c4b0efc3b7f2101cebc9b3cf2395e04",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-028.json",
      "sha256": "11ed466bda9dd189c8b8c322e030100527268f1c9b7992e10eb39de6a399ab3d",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-029.json",
      "sha256": "b5397f0a4275c9e3c522bd81273ef85a32800426350074b4f6808d8139b50c22",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/annotations/paper-030.json",
      "sha256": "ac2c158e6f00974b69273802756fd972f5bc94b08f21e1bd0b414854542ce699",
      "sizeBytes": 673
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-001.pdf",
      "sha256": "24aca105de8f961f96e5da6cccf40fea91dabb3b12515062c46cf88ff61263c8",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-001.pdf.json",
      "sha256": "b1818c9f595cd5c948f5e298d58524de20baa6951f34fbf2348b31c0e795d17b",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-002.pdf",
      "sha256": "26135e952e169b7655fdfd22a0c4ca6dcdf2d456fff452e558fe7e177a7e5197",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-002.pdf.json",
      "sha256": "eb3ab4f9fc4d51586e6e8b9fcf4f66a83fa6a10ca321ff1309221486c0c4cbb8",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-003.pdf",
      "sha256": "d9ebcf91287175d0c6793effb0053ad747eb27efd27dee9218347f40e6322090",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-003.pdf.json",
      "sha256": "e0efb1aafdb0375f512b82b693f2a5290ca68b5d49028862b79d46208e287138",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-004.pdf",
      "sha256": "3c5cda17f08f6ed8a1ae7725d6a918d3067219656f3f71efabe60d51b5e25e5b",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-004.pdf.json",
      "sha256": "326fb861fc040f6cc0ed58cc4a7583b3d515d8e59625a4a219fb7d0fdd906f3b",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-005.pdf",
      "sha256": "5adfc73995c5403e3cb22a34767be3964883c3343a7b873bf9ac03e48aef4262",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-005.pdf.json",
      "sha256": "c24820cd705feb23b2b9416bdd2f11fccae6dae46e5b5220ea5a6dc1f24a598a",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-006.pdf",
      "sha256": "f115cf5651469285ee2e99a541002707f243545a9400ddcab262220d3ff5dd10",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-006.pdf.json",
      "sha256": "701b727cedf33b2a75b60e50065576563bff97630982f846fefc40fd2196049a",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-007.pdf",
      "sha256": "e2b2dc0a4bfece3bd235aa606f89d1f444e1e827a771885cddbd7fb0e6725bbc",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-007.pdf.json",
      "sha256": "af6a8281c10915ba52ede6add255ac0dfeaf34b11c1c5b725884cd4a2e6d86c9",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-008.pdf",
      "sha256": "10993aad7d350a6b2d5de658019602f110d09542a86a0ef7042bdcc6ed4d559e",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-008.pdf.json",
      "sha256": "abce2a0e30aa07f3652e86a0c2163cb7cf166bac8b7c7faf090b9dae1185fa00",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-009.pdf",
      "sha256": "9ea520e0957d33a8456588ebe8903232aa23296f6c977ba3f90bf0aa50e8b6a2",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-009.pdf.json",
      "sha256": "f351761753794222f39f4e85dfdfd1d666f151e58798c69ffd9db2f26d7206a2",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-010.pdf",
      "sha256": "902ed72a223776eb6334a70a14d6a823c0309a7c25e8a9836c4db568d3018b1d",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-010.pdf.json",
      "sha256": "027cff22c01aa17477470a90daf343979de1c4a4643b9c98c7e754e1014a7b98",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-011.pdf",
      "sha256": "58271e90a78d462073e02ddef31650abc5c80dd495190820fb45af10d328db10",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-011.pdf.json",
      "sha256": "78d9fd8bd3911268f8479591690aede5e7b5dc5ce5fa1e3539e0f1a331c442d0",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-012.pdf",
      "sha256": "5b019d7c65d17f1107c10b664f9fcc2629b1cadcf0e43af86a3e99a4f907372f",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-012.pdf.json",
      "sha256": "0c9f6f282a0abcc5031e56ea789d18ce669611802fb9b0cda74a6cbbb50bee68",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-013.pdf",
      "sha256": "078dea2c262ef9cc00734d25dc6a9d237a3beda8d55a4dfa194b13621b9b21ea",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-013.pdf.json",
      "sha256": "d813fb48881efa0b0d74e17f9f1da7df391125a20831845de747c6c19c29b5ac",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-014.pdf",
      "sha256": "576978b426dea9d0f1012642c10091021840fbfbd4aef4c20f857cf850692e8c",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-014.pdf.json",
      "sha256": "5f3fddc9a325d52ccd705253b61d8973355458ef7191e8361398b3de48d05137",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-015.pdf",
      "sha256": "730cbb7ca8e7d27110dd89ed206c3064b9d1672bfab36e06d466d2cd7cf355f4",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-015.pdf.json",
      "sha256": "ed25389126faf6d9e0eb87cbfbd956c75f8af50d2171302b0afa9adfcff3cb35",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-016.pdf",
      "sha256": "83d57b5e74b40c2f0077ad97e87e32fcd6ded89077adeb7845e2ae3e671fa35b",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-016.pdf.json",
      "sha256": "b03a39180452fa22e907c5cf81eed17c31a703ebd473cb26a8e4992a8d756af3",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-017.pdf",
      "sha256": "dc2b1e06dc02c0eeeb5b4207419af6ba530252013324d67040c2a289c9e83abe",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-017.pdf.json",
      "sha256": "5d53cb5896fc2c39d0589550d132b96015d12ace2226f300343579c3c7b54752",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-018.pdf",
      "sha256": "3e8919524642a2ae1422482ef084099b0f74824ba5345132d3c6c34a3430938b",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-018.pdf.json",
      "sha256": "d6de75f934de4d6084d60e43e7504683ed9ab2288095afe046a2c58e4011effe",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-019.pdf",
      "sha256": "32050a44182b34765c864a91a1e40bd59f9d9283a3b1b6d8cc031ca5008fce30",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-019.pdf.json",
      "sha256": "f9e34530bac41ff1e074932b7ebd62e36fe28706a748392a9920dbacaacc10f1",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-020.pdf",
      "sha256": "ab6bf32fec886e8bd994c6514f373dd4b44c59cdf17cbf2873a169ec43c67387",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-020.pdf.json",
      "sha256": "3af38b5454127fcf3b1835db561bbfb51f1d295fddcff064333bb6babd0d6aeb",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-021.pdf",
      "sha256": "f755586d4b93d9ba443c38c25f3705025e3970efc83e595fa745903436d87c39",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-021.pdf.json",
      "sha256": "ed83205e75e0f90097f08977cdc905ac973c22ab89115aeaeb6ca2ddb453772f",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-022.pdf",
      "sha256": "2555e16d831ccf51bcf2d9e331a61a0220a29d6dc4e356831b398d993e34a8d4",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-022.pdf.json",
      "sha256": "63fb2e484a3eb0d7b839b120903fabcfbfb2c50a469eaf488797fe13f78cfcc3",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-023.pdf",
      "sha256": "3b9ebc920824fdc520660631b34fb114f18da15afcf1a2fe2601f54c09cb76dd",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-023.pdf.json",
      "sha256": "61461792bb3097a03d10600648ffac0a6ca8d6b04a62122fc64ed6896bec3236",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-024.pdf",
      "sha256": "858742aacc00d5df1f7a61f9751f69e6191800667aa7158d83481aae8d6e847d",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-024.pdf.json",
      "sha256": "b44cacb6de3ee11471bf9c190c0bca363c398c44701214642ad2a604349fc6f3",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-025.pdf",
      "sha256": "60fe16c96d8013f333c31df0b684166b60735362c6dcac4dbf35d1858756b6db",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-025.pdf.json",
      "sha256": "7b0bafd989fe263633228b0fd19ec1275b79632e1975c88d4b42b57035129cbc",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-026.pdf",
      "sha256": "c1acb791fc92a7161d7279d5dbb824a20ee6c1d3da99a5efd00c9c3b249cfa32",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-026.pdf.json",
      "sha256": "77cfd1986bbdfc626340fc2f6013cccd712400db7d502800eeef8929cc49ccfd",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-027.pdf",
      "sha256": "772c65834785199c8379b51ded404df187d4c0010125bd26d03bcd0affe619c4",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-027.pdf.json",
      "sha256": "f1bfb0301ddaf765c95bcce0167798a81612ca3887fc33dc762ebfcc17670507",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-028.pdf",
      "sha256": "945ab61663d91a3b077b6be4340ab07c350693d34e56de07aaf763741885d53e",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-028.pdf.json",
      "sha256": "3c4886c2b8a5de64c6ebda93e495d1d34c5a8bce54e439453e8bee495c6c21dd",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-029.pdf",
      "sha256": "bbdad137b26ab86e4f2911e8e0de19b3212b2d7a6abe0d75516eb049bb0e8c06",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-029.pdf.json",
      "sha256": "326088a444dc686ddf071b87376cdb3ecf106d08a0fa7eef92f30a7070d43d0b",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-030.pdf",
      "sha256": "2b1c5541d324961174048b9224fe3511beb6cb2e9135cdc896abbe0bd16b69f5",
      "sizeBytes": 717
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/papers/paper-030.pdf.json",
      "sha256": "7e80891cb4c223d792bec3f45122af2d08264dc1602029f7ccb29fdbe4115184",
      "sizeBytes": 1674
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-001.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-002.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-003.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-004.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-005.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-006.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-007.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-008.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-009.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-010.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-011.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-012.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-013.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-014.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-015.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-016.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-017.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-018.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-019.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-020.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-021.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-022.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-023.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-024.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-025.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-026.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-027.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-028.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-029.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/goldset/thumbnails/paper-030.png",
      "sha256": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
      "sizeBytes": 67
    },
    {
      "group": "root",
      "relativePath": "reference/models/standard/caffeine.pkml",
      "sha256": "18b4616b96bbeadf0494050597b97b7ccf6b8db779348bee46087b9c9bdfa551",
      "sizeBytes": 31
    },
    {
      "group": "root",
      "relativePath": "reference/models/standard/midazolam_adult.pkml",
      "sha256": "7f32df70693c86e0d4e6615d60448063b94ffa3232ab62a18c46ef4ab12cb09b",
      "sizeBytes": 38
    },
    {
      "group": "root",
      "relativePath": "reference/models/standard/warfarin.pkml",
      "sha256": "4837b24eee157b3434eabd4ed4063b8e3cbf7a2287c689a14618913f4995f8eb",
      "sizeBytes": 31
    },
    {
      "group": "root",
      "relativePath": "reference/parity/canonical_metrics.json",
      "sha256": "8913bcdc6abff402732f99772fa504f436803bd2039e91a1902a27a5f4659112",
      "sizeBytes": 1606
    },
    {
      "group": "root",
      "relativePath": "reference/parity/expected_metrics.json",
      "sha256": "f44b84c936841f9211ef16b773cbcb1317c13f5ffa192ca81e339e6efdd7401e",
      "sizeBytes": 1301
    },
    {
      "group": "root",
      "relativePath": "reference_models/reference_compound_population_rxode2_model.R",
      "sha256": "89b6c44e75ebf77f66906e910c2118bfa33475b7b8b0a03ca43c6f3d9c773e22",
      "sizeBytes": 58551
    },
    {
      "group": "contract",
      "relativePath": "schemas/README.md",
      "sha256": "2f58bea343ec1a49d9c25dbaadc3d36bfa87cebb483f280e776034d0927f4339",
      "sizeBytes": 1143
    },
    {
      "group": "contract",
      "relativePath": "schemas/assessmentContext.v1.json",
      "sha256": "2849beb31892bce04753f732e5bf538595a2a060b9c2c25d291f317640eda20c",
      "sizeBytes": 5466
    },
    {
      "group": "contract",
      "relativePath": "schemas/berInputBundle.v1.json",
      "sha256": "a46c842bfc6dd6f1e1ef4d0f5f65371182c830d478cafae3eef9a599899e9cae",
      "sizeBytes": 5212
    },
    {
      "group": "contract",
      "relativePath": "schemas/extraction-record.json",
      "sha256": "46f2024647b304d885a9b968bcaeded2566acc0f50e6754d856ff4422a1ba7de",
      "sizeBytes": 2655
    },
    {
      "group": "contract",
      "relativePath": "schemas/internalExposureEstimate.v1.json",
      "sha256": "830b2cf73661b67dfd0e8493c5e410e276555c05f71221db8e36722bf6cb4857",
      "sizeBytes": 5480
    },
    {
      "group": "contract",
      "relativePath": "schemas/pbpkQualificationSummary.v1.json",
      "sha256": "20eb7f265c12d406d453614e8c3a704d19fb8ae6527390d9a9ed6f401cdec2d3",
      "sizeBytes": 10701
    },
    {
      "group": "contract",
      "relativePath": "schemas/pointOfDepartureReference.v1.json",
      "sha256": "58a0e04e48ed716637aae12e972e0f92b858ff6f0cfde918942b97a1daa695aa",
      "sizeBytes": 3625
    },
    {
      "group": "contract",
      "relativePath": "schemas/uncertaintyHandoff.v1.json",
      "sha256": "4547fbcd1014e439abbf5f98ce1e19e0320be8e81eb30102d6a0099fce32d86e",
      "sizeBytes": 2955
    },
    {
      "group": "contract",
      "relativePath": "schemas/uncertaintyRegisterReference.v1.json",
      "sha256": "38808ece8fa55cc3b233f5b3966d480616983d953d0f8f7290cb6191e7222bb6",
      "sizeBytes": 2655
    },
    {
      "group": "contract",
      "relativePath": "schemas/uncertaintySummary.v1.json",
      "sha256": "ea1f95e8bd2786468c0a946f0c2dbbba0045411024292affb052efd33c9e00c3",
      "sizeBytes": 4735
    },
    {
      "group": "contract",
      "relativePath": "schemas/examples/assessmentContext.v1.example.json",
      "sha256": "774828884b6705892187768b505b1c3f5e36ebe83d2a2f570847145297bf3d0c",
      "sizeBytes": 2771
    },
    {
      "group": "contract",
      "relativePath": "schemas/examples/berInputBundle.v1.example.json",
      "sha256": "64399ce683596314bf9d32df20f8c42ffa02673830f477e7e78ea3a0bfa845ff",
      "sizeBytes": 1602
    },
    {
      "group": "contract",
      "relativePath": "schemas/examples/internalExposureEstimate.v1.example.json",
      "sha256": "559f0118d012d14275141d11dbb0d968ed74a0ce39002ad1094bfe87a034009e",
      "sizeBytes": 1300
    },
    {
      "group": "contract",
      "relativePath": "schemas/examples/pbpkQualificationSummary.v1.example.json",
      "sha256": "66bd8b255e52c125e72b18eaf36ea49ed95d0af5c6f4a050d483b5bb0e3697eb",
      "sizeBytes": 6962
    },
    {
      "group": "contract",
      "relativePath": "schemas/examples/pointOfDepartureReference.v1.example.json",
      "sha256": "11185de168163409fb9c22dcfbf7b10c322ff8eddf521d02d1842ee7c4994dbc",
      "sizeBytes": 1140
    },
    {
      "group": "contract",
      "relativePath": "schemas/examples/uncertaintyHandoff.v1.example.json",
      "sha256": "ef372636efb1a13dd26151618eaf440bbde90fad5e600b0ab13945187fb0a03c",
      "sizeBytes": 1682
    },
    {
      "group": "contract",
      "relativePath": "schemas/examples/uncertaintyRegisterReference.v1.example.json",
      "sha256": "652fd3674c30263e5da3e299418327ec4d06811f75f661deff63b2d152b1841f",
      "sizeBytes": 829
    },
    {
      "group": "contract",
      "relativePath": "schemas/examples/uncertaintySummary.v1.example.json",
      "sha256": "9cb008aadd06a2fb4f12dae6ea46023e6f30f30011d851ad76ad9f0f2c9bd181",
      "sizeBytes": 2021
    },
    {
      "group": "operations",
      "relativePath": "scripts/backfill_review_signoff_index.py",
      "sha256": "c3f20a0199db28dc8ac7384774ef6be7a2df9becc586e2a02ad9f0b08f9c802e",
      "sizeBytes": 2879
    },
    {
      "group": "operations",
      "relativePath": "scripts/benchmark_ocr_backbones.py",
      "sha256": "73484525b2c60f583667ff2776879f3a2757e5013770f65496ef4488320eb9f1",
      "sizeBytes": 2245
    },
    {
      "group": "operations",
      "relativePath": "scripts/build_cimetidine_cross_system_demo.py",
      "sha256": "3d837b3905526ed252020120e3ae0d8d03ec6005f20461ea944a4a4d85d96a9f",
      "sizeBytes": 27768
    },
    {
      "group": "operations",
      "relativePath": "scripts/build_goldset.py",
      "sha256": "56ef5a4f205035c7a42b121a667ce2ac40848a5900a72031e224aa0e8b8548f8",
      "sizeBytes": 7777
    },
    {
      "group": "operations",
      "relativePath": "scripts/build_rxode2_worker_image.sh",
      "sha256": "5174a4bc04a96f68cbcfdf6e45729f987875eb3df0d918cebeb8d366284cad2f",
      "sizeBytes": 702
    },
    {
      "group": "operations",
      "relativePath": "scripts/check_benchmark_regression.py",
      "sha256": "ebb1fb44cbe5f3a4abba303bc60a319c117d6804d190e29178b546f97095c195",
      "sizeBytes": 4754
    },
    {
      "group": "operations",
      "relativePath": "scripts/check_distribution_artifacts.py",
      "sha256": "12934c81c14241f6fb28705c97e9eb443e29c75b5c71005cc0dbb394c57f6084",
      "sizeBytes": 12404
    },
    {
      "group": "operations",
      "relativePath": "scripts/check_installed_package_contract.py",
      "sha256": "e63b48f3f0b7d0f5093f31f157e1b656c62a207b23021f3dd127801094a177ea",
      "sizeBytes": 7169
    },
    {
      "group": "operations",
      "relativePath": "scripts/check_release_metadata.py",
      "sha256": "971bf6472a31e184ac1e55fc17886a69154dd83ac9adb7e1cfef0579ebaf896b",
      "sizeBytes": 5670
    },
    {
      "group": "operations",
      "relativePath": "scripts/check_runtime_contract_env.py",
      "sha256": "82cbd13b4c7c4fef29b06cac4d9552f7db236985c1e7c348391e7f929b35d9a0",
      "sizeBytes": 1515
    },
    {
      "group": "operations",
      "relativePath": "scripts/contract_stage_utils.py",
      "sha256": "56e4c7236e5a343ffddc5cfce5b52ca48ffaf13b28325b4d29cb8c2ec5b63c3c",
      "sizeBytes": 1208
    },
    {
      "group": "operations",
      "relativePath": "scripts/convert_pksim_to_pkml.R",
      "sha256": "3291edd590682817eed76c83e8d88edb4af7569a0dd58a7724290eb789dcdf3d",
      "sizeBytes": 2341
    },
    {
      "group": "operations",
      "relativePath": "scripts/deploy_hardened_stack.sh",
      "sha256": "a40c597ddb4d6c64f6f6cd5e17e7d03620843d8ba37431ff9681fbbed005c90f",
      "sizeBytes": 678
    },
    {
      "group": "operations",
      "relativePath": "scripts/deploy_rxode2_stack.sh",
      "sha256": "92fd30ccacadd104b428b6e7523db5a5185a90d7d2c7db3e8402107447c329aa",
      "sizeBytes": 479
    },
    {
      "group": "operations",
      "relativePath": "scripts/deploy_s3_audit_smoke_stack.sh",
      "sha256": "426227487ad2db0a264a749b77c67061a96554de61c79351dfaeb6c637b9002e",
      "sizeBytes": 1667
    },
    {
      "group": "operations",
      "relativePath": "scripts/deploy_source_overlay_stack.sh",
      "sha256": "496721a5c06985e791a1e980555229d05e632858e4a819f6c0ef4feba7f9b3f6",
      "sizeBytes": 570
    },
    {
      "group": "operations",
      "relativePath": "scripts/esqlabs_models.py",
      "sha256": "c7927973573b2d5ecb955b8eba1db6c14088d532c0fb32d3ddc68f3d5c9d194e",
      "sizeBytes": 18084
    },
    {
      "group": "operations",
      "relativePath": "scripts/evaluate_goldset.py",
      "sha256": "c62563a748e3a5392f6f83976268882697b2dc71b250191b42f57d9e45f4f633",
      "sizeBytes": 3986
    },
    {
      "group": "operations",
      "relativePath": "scripts/export_api_docs.py",
      "sha256": "27c9b60cb4f2e9d3f595935c8598eacf7a9507d7597806ead31b55659ce12783",
      "sizeBytes": 13848
    },
    {
      "group": "operations",
      "relativePath": "scripts/fetch_regulatory_goldset.py",
      "sha256": "fc76b285b99b7308c617bd7e3444ab2676d580fccc708b5104b7dda7b0aec5fd",
      "sizeBytes": 8909
    },
    {
      "group": "operations",
      "relativePath": "scripts/generate_cisplatin_progress_figures.py",
      "sha256": "373b8d86fd7d665b648f73b7c2be1d94f2c1b60089b73c597a2867bcfc32942b",
      "sizeBytes": 12585
    },
    {
      "group": "operations",
      "relativePath": "scripts/generate_contract_artifacts.py",
      "sha256": "c5e16e58a9c65b8e3fdb0c064dc39467f5578ca848962a998128ae65c5f2c506",
      "sizeBytes": 16310
    },
    {
      "group": "operations",
      "relativePath": "scripts/generate_reference_model_live_audit_pdf.py",
      "sha256": "04848fbe20a293c668cad4fea7eccfbc585d29f14b7bfac90146205c9ab6f5c7",
      "sizeBytes": 44697
    },
    {
      "group": "operations",
      "relativePath": "scripts/generate_regulatory_goldset_audit.py",
      "sha256": "ef244652dad5862ad46c25e1dd6b844a148389dcf7697c242577b3b268e6a0e2",
      "sizeBytes": 9701
    },
    {
      "group": "operations",
      "relativePath": "scripts/generate_repo_concat.py",
      "sha256": "3d79fc32d44a44377aa4e02abe7b430ff1015663e226199a1a8788fa9d86a40c",
      "sizeBytes": 3921
    },
    {
      "group": "operations",
      "relativePath": "scripts/generate_sbom.py",
      "sha256": "51a7139d534a4194272422900edfea76e84e5fc04ea79092b57fa32386ce464b",
      "sizeBytes": 3900
    },
    {
      "group": "operations",
      "relativePath": "scripts/mcp_http_smoke.sh",
      "sha256": "7a99d336f103b3bfa576949da0d1486aca8eb2996fc0957fbb6fe7396c2127ea",
      "sizeBytes": 1522
    },
    {
      "group": "operations",
      "relativePath": "scripts/monitor_docker_build.sh",
      "sha256": "1f2d1c2b89f5a07d7078a355bd770f51134564aba7a772abe253aaa3b0fe8dfd",
      "sizeBytes": 933
    },
    {
      "group": "operations",
      "relativePath": "scripts/ospsuite_bridge.R",
      "sha256": "e9d121279d3042e90bd259ae7b218cc7234fa3a2db6355f1bd238cf60b00ff5c",
      "sizeBytes": 341953
    },
    {
      "group": "operations",
      "relativePath": "scripts/public_release_preflight.py",
      "sha256": "a2d922793175a097f807403b0c77d8447c12ccb648c236bf7cf5685606fe3c99",
      "sizeBytes": 13620
    },
    {
      "group": "operations",
      "relativePath": "scripts/refresh_rxode2_worker_image.sh",
      "sha256": "9477aefe375d3b2e35e7cc12550a957ac0fc8a4d4cca9fbce3f34be92ee8bcb9",
      "sizeBytes": 558
    },
    {
      "group": "operations",
      "relativePath": "scripts/release_readiness_check.py",
      "sha256": "1364fedf34a4adaac31187c250dd89796efd2587328ed5662fa60e1eacace234",
      "sizeBytes": 72867
    },
    {
      "group": "operations",
      "relativePath": "scripts/render_cimetidine_case_study_figures.py",
      "sha256": "f2a07162ee682206a6b7f457846621f5397ea3558223c44f17086d81529c11e6",
      "sizeBytes": 15113
    },
    {
      "group": "operations",
      "relativePath": "scripts/retention_report.py",
      "sha256": "05cf6c32d10556244092d0a28ec7731f58af70aab0495a10729097e3d0033ef3",
      "sizeBytes": 2110
    },
    {
      "group": "operations",
      "relativePath": "scripts/runtime_src_overlay.pth",
      "sha256": "716b898bb8a6ff3a5b1661741d9d174363dc9ace877544bee0f18d9882965ab7",
      "sizeBytes": 240
    },
    {
      "group": "operations",
      "relativePath": "scripts/s3_audit_smoke.py",
      "sha256": "8edbce50c7fa40426907af842908eda76fd1c2ab5e58508ee0783eafcd9e0341",
      "sizeBytes": 7973
    },
    {
      "group": "operations",
      "relativePath": "scripts/test_cli_integration.sh",
      "sha256": "a9c45db44251a8adcf1ce693fc2427204b690d8e1803abd579d2440249cfb2b2",
      "sizeBytes": 6147
    },
    {
      "group": "operations",
      "relativePath": "scripts/validate_model_manifests.py",
      "sha256": "773d26392adcae0e748a3f5c3738e61ec7798eb6a0a8da779f9535f8985f6001",
      "sizeBytes": 7954
    },
    {
      "group": "operations",
      "relativePath": "scripts/wait_for_runtime_ready.py",
      "sha256": "fa18ce884ba790f7d208fde156709b2735e4678e68dc75461a4cbe04569364be",
      "sizeBytes": 5658
    },
    {
      "group": "operations",
      "relativePath": "scripts/workspace_model_smoke.py",
      "sha256": "c9f201b0958028473a5434a8704130492021f7fffc8cb42e28b3b9d357257684",
      "sizeBytes": 13656
    },
    {
      "group": "source",
      "relativePath": "src/mcp/__init__.py",
      "sha256": "cfbacb4d06b9ceed2339304629ba0a8bb80ed9e69ea1e9e0ad93a82ae77a39dd",
      "sizeBytes": 3832
    },
    {
      "group": "source",
      "relativePath": "src/mcp/session_registry.py",
      "sha256": "3a893ea7ccc06ac68c22b816cf699847ae536414910ea96474d40d42b9a62d9a",
      "sizeBytes": 10862
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/__init__.py",
      "sha256": "72198d5ebbf0cf6d84ca132423d71aeaf4ab16257c0701796d247d899b7808f0",
      "sizeBytes": 68
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/calculate_pk_parameters.py",
      "sha256": "39132a41a0acffe9b1a130cc431ea4edeee757250479ddfbb4a752ee671f8d80",
      "sizeBytes": 14230
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/cancel_job.py",
      "sha256": "4c2ab92e5be22018a1749fc4dfd9ecd3ad08cd1d3968a0249dbc6fe1a5626eeb",
      "sizeBytes": 1449
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/discover_models.py",
      "sha256": "162ace13e0473220d683350b6bcf9656d6ecdc8ab02a0ad25c6d0a0aaa45b8f5",
      "sizeBytes": 3836
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/export_oecd_report.py",
      "sha256": "99a54e052055f9c346e98058b00adfe724e4857e76fb149415a932d06656089d",
      "sizeBytes": 3969
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/get_job_status.py",
      "sha256": "7fe92f3a91290eebf52b8dcc6d4e5eb8a6a005cfd848b8e73729d21d1222a1b9",
      "sizeBytes": 4735
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/get_parameter_value.py",
      "sha256": "c57e1e8279f10bea11d9c09dabb3e8ec61f0a597e1cf6009b8b798fccf08932d",
      "sizeBytes": 2358
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/get_population_results.py",
      "sha256": "4575abe1dd23eb3b16f57cd7cf025f6c22a3f8165d8468a2f496916eb8bc0b73",
      "sizeBytes": 2164
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/get_results.py",
      "sha256": "527a367817f9db29a20b8445fa4dbf801ea3ea2cbab0b2a7cf4077949190e0f0",
      "sizeBytes": 2779
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/ingest_external_pbpk_bundle.py",
      "sha256": "84464a598002def7fc5e47b9f4a7caf4ad3d0190dc8879c66b88927469e1eebc",
      "sizeBytes": 83376
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/list_parameters.py",
      "sha256": "60c56e65594164e5a8d3627d6bc112930b735397b076e22db1868cf3954f1515",
      "sizeBytes": 2277
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/load_simulation.py",
      "sha256": "f428a9f666873071df351ea97f93e6166a5e59b67b505c5f03428e316717b1f3",
      "sizeBytes": 8993
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/run_population_simulation.py",
      "sha256": "4d3fd94b48999529c624ea4fe472b10fd0761255966689847ecf16b80fa9189b",
      "sizeBytes": 5962
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/run_sensitivity_analysis.py",
      "sha256": "d455f54af62ee0583e2c2602006d9fd3c8653bd5c99c812f643775a4a3baa8d9",
      "sizeBytes": 10744
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/run_simulation.py",
      "sha256": "2e2ef4f467f50a28e64e7812dcca50fe0caa21c1e27dae0e25cb588b65fdedc9",
      "sizeBytes": 2917
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/run_verification_checks.py",
      "sha256": "13848581a4d2b148fdb32e4a99244e8b9b46eaa56423d76af93eac58e88f540c",
      "sizeBytes": 6042
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/set_parameter_value.py",
      "sha256": "9276791c26e38ff0cf7531dc631320a8d5296f4d50815e9329c47bc6ada174f0",
      "sizeBytes": 2809
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/validate_model_manifest.py",
      "sha256": "7711e3542cb7e4794f331013495e62d032bf28ac20f1c786e2d3efc32ca327b9",
      "sizeBytes": 2060
    },
    {
      "group": "source",
      "relativePath": "src/mcp/tools/validate_simulation_request.py",
      "sha256": "e5bf413b0528cb01d6d0612307208f7d9138f9b12053a01d554f4ec7ba39e026",
      "sizeBytes": 5303
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/__init__.py",
      "sha256": "d7e657911d806b1b9d5b2e07431711cc3ccee84c9660f554874f39745e22d305",
      "sizeBytes": 311
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/app.py",
      "sha256": "ac87a3b292d9c156674db0c986ae37916ca307ed234854926df3c062e53d018f",
      "sizeBytes": 13126
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/config.py",
      "sha256": "7452e44bd305bc4136108cc4233e9f0845691d5e5e014b8a3c41dde845f5f7bc",
      "sizeBytes": 24091
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/constants.py",
      "sha256": "cbc357731d7dc67082c32f79d91d0a253cc3fc47ff41fb86dc0a9ffde838bdd6",
      "sizeBytes": 158
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/curated_publication.py",
      "sha256": "03d4e07c141b61f096a7ef163f40cab62931dbd47c8b4a63831f9f1bb909ded9",
      "sizeBytes": 909
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/dependencies.py",
      "sha256": "4692581d24417f8061a5864472115efc248f3ed6bd8631a8a76093aacb4beb3b",
      "sizeBytes": 1737
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/errors.py",
      "sha256": "8a8a661e3b82c9688414622a8e46e073275a710cb78f1b99572da2fe1010bc0e",
      "sizeBytes": 7816
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/logging.py",
      "sha256": "d3da2da31d7d5a97cc22ca53e4c505a4f308b2ccb6729e9e89e0d1b4f6358208",
      "sizeBytes": 1490
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/main.py",
      "sha256": "f8dbbc8f378d29755fd8309b5adaf966a48b93277036451f9379dac881490edd",
      "sizeBytes": 499
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/model_catalog.py",
      "sha256": "3bf0233bb16ae8e5715a2294e01e733aca8b78b7036a2d6ebf1af98312b1e6dd",
      "sizeBytes": 12143
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/model_manifest.py",
      "sha256": "e2d1b9732edc940a21021341ee99f6f9e9fbd7e02862eb58a7bb3e389e6adfdc",
      "sizeBytes": 89457
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/review_signoff.py",
      "sha256": "1dfa1c929987354fb7f1fa0f9805041c87eb59c89a07688d75580e8090bc00df",
      "sizeBytes": 19152
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/reviewer_advisory.py",
      "sha256": "cc7a172e71726a16976301229baa7bd975d9b345bc176ccdbed4891f6aff03f5",
      "sizeBytes": 4058
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/trust_surface.py",
      "sha256": "4f969e87ef43bc504d51e41b83d1ae0ab536f26d2402e20f6c0484fc86773f21",
      "sizeBytes": 14316
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/adapter/__init__.py",
      "sha256": "50e2c0841f419c57390b1628eb49ab209db08740aac3b609de2302cafbe7fbf6",
      "sizeBytes": 331
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/adapter/environment.py",
      "sha256": "4483a37cfbf991800b33cc38e538f8f9ec7dc80ece9e208e05a350756252ec04",
      "sizeBytes": 3254
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/adapter/errors.py",
      "sha256": "3a17fd6b38082aad8f59bba11dedd1a374a7c3e846e42c03a1c7b8f091fb67ff",
      "sizeBytes": 776
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/adapter/interface.py",
      "sha256": "51ac8394124b55880339db9b0a028ff7599c34c61ab05a0ca47077e1e3a40e93",
      "sizeBytes": 4977
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/adapter/mock.py",
      "sha256": "788ac05af8d37d6c1368d09cc2ab079ab4e0333c6d7bc0ed700ca6dc3249b91c",
      "sizeBytes": 12656
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/adapter/ospsuite.py",
      "sha256": "3778e7bba63b0b2cb723bfca19c666581c30c6d9c31704bf1d7708a7711cba84",
      "sizeBytes": 27156
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/adapter/schema.py",
      "sha256": "ccb81a3f8cf72fa0b925c9c190df6a7ca94023e1efa89b6a0eaace7d598cb0d4",
      "sizeBytes": 3089
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/agent/__init__.py",
      "sha256": "876f3a768c80a05466b89ffb12a170926adecc44e6a00d054c1c83cf60971ac5",
      "sizeBytes": 1851
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/agent/langchain_scaffolding.py",
      "sha256": "34521de49a73b769215f91e6318dfaf8590f86815168a1d4365fb44780af287c",
      "sizeBytes": 39647
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/agent/prompts.py",
      "sha256": "4042448017bad80c6773b1c179ea423c38327acb263ab194ea38e5e1a2aad2a4",
      "sizeBytes": 6782
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/agent/sensitivity.py",
      "sha256": "c16fd3a47a3d472a437cbe109b0dd6a4bf7068b70504f12a9c345b68f626e5e5",
      "sizeBytes": 17874
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/audit/__init__.py",
      "sha256": "e93692eba387e51189188a132154d48a949d388b6e97a4a9776cb6c3abf03bd4",
      "sizeBytes": 491
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/audit/jobs.py",
      "sha256": "69723be390695e122a303782afc861f3499c8803f7902a16c0bb8f68f1c89a87",
      "sizeBytes": 2475
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/audit/middleware.py",
      "sha256": "d72e96b5cb0065118c799ef04574bccaed4215e657780bef1d437fe2e693ccac",
      "sizeBytes": 3938
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/audit/trail.py",
      "sha256": "ea8fb3e84697ddb7b35822302d0918922df1eb63dab9979b194b8e2e6d04dbd4",
      "sizeBytes": 32967
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/audit/verify.py",
      "sha256": "578251fd9051960a7f188cca35a021a22e766503ba861e4362a0ae20e808bb97",
      "sizeBytes": 13070
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/benchmarking/__init__.py",
      "sha256": "62fb79a3b8b4eabf773ea302301011084c74fc08dea65cd77904639c407c0c9b",
      "sizeBytes": 201
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/benchmarking/__main__.py",
      "sha256": "c51470c373ced0958343482c6adfb1ae30841974138d31374d21b1f35d6af8df",
      "sizeBytes": 172
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/benchmarking/cli.py",
      "sha256": "6f89071c568e8ee596a135fd2564741ff2daa25895932844e760ad3a060710bd",
      "sizeBytes": 31789
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/benchmarking/regulatory_goldset.py",
      "sha256": "6760efa0d01df3e79250c095d6d07d59e2bff3dd3868f8f0740728dc1eaa6420",
      "sizeBytes": 53551
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/contract/__init__.py",
      "sha256": "4243ff28761358c0d031c13e9246f368c23198fc6ed1ba6289419838182fba31",
      "sizeBytes": 537
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/contract/publication_inventory.py",
      "sha256": "60339a923f15b3f51888c7a756b0ba117c05421980d15e212c8b63ce48e5f189",
      "sizeBytes": 863
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/literature/actions.py",
      "sha256": "857b82b61127013c3479566aec2a980c76847aba3c4115ac66b259c2a103ac68",
      "sizeBytes": 5502
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/literature/evaluation.py",
      "sha256": "8064e40f7d175b3c473468a99365ffc437585d3d2045b2415b51e5dc0766914b",
      "sizeBytes": 4196
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/literature/extractors.py",
      "sha256": "17e9af7f0fb75d1b63e5a40cf1c4e5dd61063e28f32afdcfd42aa3a900a8e193",
      "sizeBytes": 6374
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/literature/interfaces.py",
      "sha256": "9ffc28959709f4cf590109030d079e1c1f9aef5971ed610b2c0911a19294ab3f",
      "sizeBytes": 1251
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/literature/models.py",
      "sha256": "84755d705ee8f812d83324db6b9535379399eafd2a4b3afceb06c681b110813a",
      "sizeBytes": 1901
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/literature/pipeline.py",
      "sha256": "4437d6e4b3b711063a67dc2a74ed55d2ec8c6b812d9fad3c65a10159a1049fea",
      "sizeBytes": 2853
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/literature/validation.py",
      "sha256": "c0c939db7105c3db5310d80681a1f7387e9d57aff4257239abd7c6b90ba838b2",
      "sizeBytes": 2508
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/parity/__init__.py",
      "sha256": "4b07a414f60d8e610785f644a4a018e43f8d32ab6fe71442a6f4188280d47f54",
      "sizeBytes": 166
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/parity/data.py",
      "sha256": "12e5b74bc66b26fa941dc58d27edeaba5152170828fe654f599882cf9570ca42",
      "sizeBytes": 5908
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/parity/suite.py",
      "sha256": "faa8020b084f92cbc7310b97025a4ea3b7b69ee4364b7d323dab3483109bf929",
      "sizeBytes": 11879
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/routes/__init__.py",
      "sha256": "9f9c8ff32209047fe8fa2e5e620126b4cafa9a239755a258dd235e785d084bb4",
      "sizeBytes": 73
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/routes/audit.py",
      "sha256": "f2012dd0fc4f2bf40d9807e724084125e5b1026ff38c64f08439329d670c3c7d",
      "sizeBytes": 999
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/routes/console.py",
      "sha256": "c50ca5d955c1e0857e67aec340872d542546a63a0bbc5865c205a9936df996f0",
      "sizeBytes": 6870
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/routes/jsonrpc.py",
      "sha256": "fe6ae3b434c9cf8dc49e0c178774bc8257bb35a60220eb8c69bce0da95839198",
      "sizeBytes": 12215
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/routes/mcp.py",
      "sha256": "1bb4f3474528381806cabf8bce78fc8b43cdb28da56bcefa149cc926932bdcf7",
      "sizeBytes": 22106
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/routes/resources.py",
      "sha256": "1777d1ad872b793cd44d1f4a04ceb434054bab2c74fc91f26d4eccd5bbf59778",
      "sizeBytes": 86
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/routes/resources_base.py",
      "sha256": "a6cdbed6094b50c3c38a991b5c5ae4bbbdb70b07c91660c0cec806971de8c35c",
      "sizeBytes": 34528
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/routes/simulation.py",
      "sha256": "65836e013d8d93951b2f03718859c2f9753d65149564d9c3a99cad3fd798c5e6",
      "sizeBytes": 49966
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/runtime/__init__.py",
      "sha256": "7940713de76978b045ace4bff165886ca38d7009b7cc5e2f44294842e79b5894",
      "sizeBytes": 274
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/runtime/factory.py",
      "sha256": "b53c8cf4a032c58f32e6183333fb62f9b9fd3ff3cf9419d29d18b9e26c5fd1af",
      "sizeBytes": 3172
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/runtime/session_cli.py",
      "sha256": "279237a5ee2d65e2f2a5a2a9f881ec8ed7d3d95b7d1ceae394adc54c1870ef23",
      "sizeBytes": 3143
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/schemas/__init__.py",
      "sha256": "d0b49334a5992a2697fc99a3b6570a2a978aa93c878f4c5a97608c5dfac513c7",
      "sizeBytes": 60
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/schemas/extraction-record.json",
      "sha256": "46f2024647b304d885a9b968bcaeded2566acc0f50e6754d856ff4422a1ba7de",
      "sizeBytes": 2655
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/security/__init__.py",
      "sha256": "abf958184fa45b6de39252fa046a65e33c29672686f3e35f3964346b4dfb7484",
      "sizeBytes": 223
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/security/auth.py",
      "sha256": "9263a3da60d0d2dc953df617c5a03940033e3b79cdff330ac684ce7884afe21c",
      "sizeBytes": 8493
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/security/confirmation.py",
      "sha256": "ef01caa5c11b969a0520b35751e32f2638d06f4e4201beee70e04b691dc5366d",
      "sizeBytes": 1233
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/security/phi.py",
      "sha256": "8dae5ce7e85adaefaa8dbead8b3d09d995e5b847169c53d44d55b1fb2a82a7c0",
      "sizeBytes": 2599
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/security/simple_jwt.py",
      "sha256": "f831776868d4b19ec62ea4e6f25fcd5379441859da9b0b1ce37c87c9a9353532",
      "sizeBytes": 2225
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/services/celery_app.py",
      "sha256": "fc055e703726123cede07246906f17bea78d9459b1e46eb1a918f76d3014a166",
      "sizeBytes": 3092
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/services/job_service.py",
      "sha256": "450b8faa722e6f924b755aa32d532a100782606a61e1575fa8d014a0be594ff5",
      "sizeBytes": 52253
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/services/llm.py",
      "sha256": "a970d62be64bc822f2b1994e624ca6f02fdd9c1a65e54dab7a1bdb2a784954d9",
      "sizeBytes": 3249
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/services/snapshot_service.py",
      "sha256": "9e93bd27131e8c14c837bdb90e171e7a1283dc0b2c3b3abb02fd499a1078984f",
      "sizeBytes": 1666
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/storage/population_store.py",
      "sha256": "3a32dd1385614609a089fc1e3d50d04cfcc08e37c558d2196e5052ff40f82e3f",
      "sizeBytes": 4743
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/storage/snapshot_store.py",
      "sha256": "b02e5b7119b57e2e01d4f3fb892863500d53817d845cceb8d54e18eae555ef3c",
      "sizeBytes": 5338
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/tools/__init__.py",
      "sha256": "5ca2ce8f6e4750df85208f6aabb1edf80a90166356782155b0cf4cdd25989fe4",
      "sizeBytes": 155
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/tools/registry.py",
      "sha256": "b8c4d0cf161e728f520acb89073a79e005ec4c2e20d489567efa05b87b67d2a1",
      "sizeBytes": 417
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/tools/registry_base.py",
      "sha256": "085c8521d241e5f21f7ed84d8fa2ffa64ffa39af3707204e7eb9068e30e79b0e",
      "sizeBytes": 16405
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/util/__init__.py",
      "sha256": "6992a93318005c92e1c7d5f37364b233fb8b7883f516de401c454440d8354af2",
      "sizeBytes": 111
    },
    {
      "group": "source",
      "relativePath": "src/mcp_bridge/util/concurrency.py",
      "sha256": "9e5a3481efcb2e212cc6536a928c3fdc08d2209ce7a8bcb84f6c019177eeff8d",
      "sizeBytes": 481
    },
    {
      "group": "verification",
      "relativePath": "tests/conftest.py",
      "sha256": "ca5e482e1b73f42488fe725b57f4a328669eb4b14ff738753abcf914696a1e54",
      "sizeBytes": 292
    },
    {
      "group": "verification",
      "relativePath": "tests/test_audit_trail.py",
      "sha256": "8f3c6d77a1f574157448deb2f3cc4806e43f4b9a699cca11379896d6783b1664",
      "sizeBytes": 22509
    },
    {
      "group": "verification",
      "relativePath": "tests/test_backfill_review_signoff_index_script.py",
      "sha256": "a152f7c04083efbbc02627da48a4b75237fb851c1832e53cc8ba9d4ee2b3843f",
      "sizeBytes": 2508
    },
    {
      "group": "verification",
      "relativePath": "tests/test_calculate_pk_parameters.py",
      "sha256": "48628241d849815abf60fe90c6b07512d1cdb7c15f7b35704503c6050877be46",
      "sizeBytes": 5009
    },
    {
      "group": "verification",
      "relativePath": "tests/test_capability_matrix.py",
      "sha256": "307eb57a401af87e4861d24d7c9994179cf6f3541ba5f49591f11f3a25c1ae82",
      "sizeBytes": 3597
    },
    {
      "group": "verification",
      "relativePath": "tests/test_celery_runtime_contract.py",
      "sha256": "489f204090263791c7beb3201e55961aceecd986916543952741271bdc169abe",
      "sizeBytes": 697
    },
    {
      "group": "verification",
      "relativePath": "tests/test_config_contract.py",
      "sha256": "8503396838bc91695e27eece18bfa1b6e38725af7f33bad468948bfda4ec496c",
      "sizeBytes": 3078
    },
    {
      "group": "verification",
      "relativePath": "tests/test_deployment_profiles.py",
      "sha256": "4a45c785afd9b370a0fb122352d53a7d89ef45f930c5bd1265ed401c8d63629d",
      "sizeBytes": 14769
    },
    {
      "group": "verification",
      "relativePath": "tests/test_distribution_artifacts.py",
      "sha256": "a3db829bb67d9681ed81041548d0ff78b37826f26e7f10aa9870f2bb69ddcec0",
      "sizeBytes": 10675
    },
    {
      "group": "verification",
      "relativePath": "tests/test_docs_reference_drift.py",
      "sha256": "4db7e83173d0650bb3ffff68dd8d40c836585c2ca191feb59a193838667154ed",
      "sizeBytes": 1130
    },
    {
      "group": "verification",
      "relativePath": "tests/test_export_api_docs.py",
      "sha256": "551a24392a43ee490630ed73a78aaa87c2362454a6025c0ab692a8ea43e11d37",
      "sizeBytes": 2197
    },
    {
      "group": "verification",
      "relativePath": "tests/test_external_pbpk_bundle.py",
      "sha256": "3a56dda98bb1f0fa4deef930784baaeace7f0ac6cf23a83b2ca8d548876c506c",
      "sizeBytes": 13621
    },
    {
      "group": "verification",
      "relativePath": "tests/test_generate_repo_concat_script.py",
      "sha256": "7921c17dfaf9ef405581f342af60d5cec8143d6defec6de0e44dd93b4666d4b7",
      "sizeBytes": 2822
    },
    {
      "group": "verification",
      "relativePath": "tests/test_github_contributor_surface.py",
      "sha256": "ee68e052bfbc6dec966674d2d01a811924f9ec52918615686925e18a42f5aa11",
      "sizeBytes": 2046
    },
    {
      "group": "verification",
      "relativePath": "tests/test_import_footprint.py",
      "sha256": "05d04c1face29f5c21008f640f7df40d02b9806ea656aaa9a1a9cea3e12708fa",
      "sizeBytes": 1888
    },
    {
      "group": "verification",
      "relativePath": "tests/test_load_simulation_contract.py",
      "sha256": "342a9e8412462b79226ee231de72b099ff9117cdb7db687542b0712bc863aaad",
      "sizeBytes": 958
    },
    {
      "group": "verification",
      "relativePath": "tests/test_model_discovery_live_stack.py",
      "sha256": "cb4a385369e23a8509c66c5d75e88d6bf0b8a4d53600f26e4f3ebe6584fc6a98",
      "sizeBytes": 23636
    },
    {
      "group": "verification",
      "relativePath": "tests/test_model_manifest.py",
      "sha256": "b9dcd3ce10a29e96e179c6c3fd5d1a7e76c3da8067d7264963d0c3b039e7e725",
      "sizeBytes": 52314
    },
    {
      "group": "verification",
      "relativePath": "tests/test_model_path_env_resolution.py",
      "sha256": "74537aa8b178ca3a6c9f9d779ba1c7f00eb748277985c93ec264436c1c15087b",
      "sizeBytes": 3216
    },
    {
      "group": "verification",
      "relativePath": "tests/test_ngra_object_schemas.py",
      "sha256": "d5e03c3245f6d8de9778032ceb18277ccfe443be2078c8494ac63a3376b0934e",
      "sizeBytes": 6900
    },
    {
      "group": "verification",
      "relativePath": "tests/test_oecd_bridge.py",
      "sha256": "32745e990b0434fa608db66b29667a4337834a42b1cfd86208bfb984b655308a",
      "sizeBytes": 98108
    },
    {
      "group": "verification",
      "relativePath": "tests/test_oecd_live_stack.py",
      "sha256": "db5edcebc286134d6bd676ffa0d0b51ae5758d88943527e06c8535d4b1f62147",
      "sizeBytes": 44270
    },
    {
      "group": "verification",
      "relativePath": "tests/test_packaged_adapter_namespace.py",
      "sha256": "5c1d6cc7d36940d8c5183c9a1dcdc160f3e74abba165fb9f535de4715165286a",
      "sizeBytes": 1217
    },
    {
      "group": "verification",
      "relativePath": "tests/test_packaged_contract_artifacts.py",
      "sha256": "d32b073041a4c11bd976648cf31672de47276dcb03009522acce2a367275b18e",
      "sizeBytes": 5841
    },
    {
      "group": "verification",
      "relativePath": "tests/test_packaged_mcp_namespace.py",
      "sha256": "989518becb87c3f8c3bd438230463252fea6ae38c8cc99940ea3caf88bcc3cba",
      "sizeBytes": 1253
    },
    {
      "group": "verification",
      "relativePath": "tests/test_packaged_resource_routes.py",
      "sha256": "0cb7bd22a711c485c7e7484dff3404bbc6c858ae0d4e24b3fb61cfd7d1bec2de",
      "sizeBytes": 4369
    },
    {
      "group": "verification",
      "relativePath": "tests/test_packaged_tool_registry.py",
      "sha256": "a8b8787df18ca23023210917e29c17b3c9795b9f9302b9aa9dea4ec814811f3b",
      "sizeBytes": 2083
    },
    {
      "group": "verification",
      "relativePath": "tests/test_public_release_preflight_script.py",
      "sha256": "5e83718c3f39ddcf12dcecc6de1bcce8391ed9afaf486374d18355f8ff5758a0",
      "sizeBytes": 3460
    },
    {
      "group": "verification",
      "relativePath": "tests/test_regulatory_goldset_analysis.py",
      "sha256": "54e6d77912b949efdd2c5f029cb37e7322f3852b5390e6a5349c4bf3d0b790f2",
      "sizeBytes": 7730
    },
    {
      "group": "verification",
      "relativePath": "tests/test_regulatory_goldset_manifest.py",
      "sha256": "2ec1e05aa31b756a0f687f0917174f6d96f2061fd4d2446f27e4e07e24e8b929",
      "sizeBytes": 1659
    },
    {
      "group": "verification",
      "relativePath": "tests/test_release_metadata.py",
      "sha256": "6e7213203360cf196a5303252ea0e0b3a8cb19e45ae31e506cccbace2774152c",
      "sizeBytes": 5123
    },
    {
      "group": "verification",
      "relativePath": "tests/test_release_readiness_script.py",
      "sha256": "f522643b935aa1df742c460aafa3995ccbe820badeafd18ff4adbf58b6d7e66d",
      "sizeBytes": 3462
    },
    {
      "group": "verification",
      "relativePath": "tests/test_review_signoff.py",
      "sha256": "20a51bbfb566e724747753df725a046353a767b09d6bc4be8664789c0704579c",
      "sizeBytes": 20277
    },
    {
      "group": "verification",
      "relativePath": "tests/test_reviewer_advisory.py",
      "sha256": "834339a0df264360cee353821996c16ebd1aa7a6a9dc074afcc7c4fd60908555",
      "sizeBytes": 1010
    },
    {
      "group": "verification",
      "relativePath": "tests/test_runtime_security_live_stack.py",
      "sha256": "7117ddb351c2bdb913f91691da82c7bafeb1b57884243ae302bbf17fabf289ad",
      "sizeBytes": 13762
    },
    {
      "group": "verification",
      "relativePath": "tests/test_s3_audit_smoke_script.py",
      "sha256": "805efac5b58c5708e795e82a7b86a86b2ef480d176f92a14268b04f79c54a26e",
      "sizeBytes": 2398
    },
    {
      "group": "verification",
      "relativePath": "tests/test_security_posture.py",
      "sha256": "7ac4ac99b31380188e2f523f2a83f5ac78135a5add5349f499994525085caf10",
      "sizeBytes": 5652
    },
    {
      "group": "verification",
      "relativePath": "tests/test_sensitivity_analysis.py",
      "sha256": "e1596572389b40281297af1bdf7abe3debe7532fe46b57ca21f2627857a47cf2",
      "sizeBytes": 4642
    },
    {
      "group": "verification",
      "relativePath": "tests/test_trust_surface.py",
      "sha256": "f431221584bffa69523fd5bd08f12038228ca248fadbe47a2c7ea5e967b7f243",
      "sizeBytes": 8088
    },
    {
      "group": "verification",
      "relativePath": "tests/test_validate_model_manifests_script.py",
      "sha256": "ba103676a4865dd034a0cf94431a25499af07e9c9288ec103ffcda60bc82ece2",
      "sizeBytes": 6712
    },
    {
      "group": "verification",
      "relativePath": "tests/test_workspace_model_smoke_script.py",
      "sha256": "252aed1d7ede9b48a6e6d6151cf2b3ce44a9c74ac56bca16026319c5d63a838f",
      "sizeBytes": 1782
    },
    {
      "group": "verification",
      "relativePath": "tests/data/agent_dialogues/ambiguous_request.json",
      "sha256": "b9a06e94e6043d0167135b53da39cfbf718c1adf28c0e53844b0650ca6512962",
      "sizeBytes": 471
    },
    {
      "group": "verification",
      "relativePath": "tests/data/agent_dialogues/denied_confirmation.json",
      "sha256": "5f879b6b0d0f2226420015207d2372a2763b7a29678709a9382392599416970b",
      "sizeBytes": 326
    },
    {
      "group": "verification",
      "relativePath": "tests/data/agent_dialogues/happy_path.json",
      "sha256": "7a53b0e5e0445364ffb6c22eebd5ccab558f61b712a59534b9f9cd97f9c4d743",
      "sizeBytes": 858
    },
    {
      "group": "verification",
      "relativePath": "tests/docs/test_export_api_docs.py",
      "sha256": "095637db18e21f9ab91343849eeb591d72d280136576cc53d444b958d1e75a06",
      "sizeBytes": 994
    },
    {
      "group": "verification",
      "relativePath": "tests/e2e/test_end_to_end.py",
      "sha256": "4a217f7e72dd73235c703b91b196966dee0f249919f76804fafa8a4de5b2a4dc",
      "sizeBytes": 4852
    },
    {
      "group": "verification",
      "relativePath": "tests/fixtures/demo.pkml",
      "sha256": "0a569e8351162f3f0c03550ebd90420ab5350733e28db2067945d29346e77dcb",
      "sizeBytes": 27
    },
    {
      "group": "verification",
      "relativePath": "tests/fixtures/demo.txt",
      "sha256": "e9bf2098c83087e46d6ead1afd060e08e438cbca8ba09478a59ae0bc0e602a1c",
      "sizeBytes": 25
    },
    {
      "group": "verification",
      "relativePath": "tests/fixtures/golden_dialogues/clarification_required.json",
      "sha256": "b0984a6e5a41a060dfae513f19bb454d5ae3c2caeffc80ead2e52dc9588bd41f",
      "sizeBytes": 464
    },
    {
      "group": "verification",
      "relativePath": "tests/fixtures/golden_dialogues/confirmation_approved.json",
      "sha256": "929cf7117754df7fe83fdc2014a345c325948f031acff4224a20799d4b27e5fe",
      "sizeBytes": 1433
    },
    {
      "group": "verification",
      "relativePath": "tests/fixtures/golden_dialogues/confirmation_denied.json",
      "sha256": "300d8f4e5e20fba57334f2d0984f2143dcd65643293a3190b1803d87000e5b03",
      "sizeBytes": 799
    },
    {
      "group": "verification",
      "relativePath": "tests/fixtures/literature/gold_standard.json",
      "sha256": "e7815fb25e2b0d4b622c72f2766a4f4ffde5912d6783664a89cda736deaa3dd2",
      "sizeBytes": 561
    },
    {
      "group": "verification",
      "relativePath": "tests/fixtures/literature/pdf_extract_kit_sample.pdf",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "sizeBytes": 0
    },
    {
      "group": "verification",
      "relativePath": "tests/fixtures/literature/pdf_extract_kit_sample.pdf.json",
      "sha256": "769998ae24659fe9f32b86d8e688329f5b1c758a1dcda67e085a7aacaa0d22bd",
      "sizeBytes": 808
    },
    {
      "group": "verification",
      "relativePath": "tests/integration/test_agent_dialogues.py",
      "sha256": "d1f280cb12d9c16d087b74a6cacf2518a62248bf691319443b2bb02ffee23704",
      "sizeBytes": 3184
    },
    {
      "group": "verification",
      "relativePath": "tests/integration/test_auth_rbac.py",
      "sha256": "4a500af4fd8fa2d23ddf2acb982f8837b8cb18da630aab2faaca74e1713b92cb",
      "sizeBytes": 3150
    },
    {
      "group": "verification",
      "relativePath": "tests/integration/test_auth_security.py",
      "sha256": "0ddeefe59daa15eb4a80d34aeb057b3f709e0063ee4939026ca97fe0d65e5c8c",
      "sizeBytes": 3056
    },
    {
      "group": "verification",
      "relativePath": "tests/integration/test_console_routes.py",
      "sha256": "31d6b655783895a24537cd34ed9db18e66218101b619a736734e7596c3c45b37",
      "sizeBytes": 2932
    },
    {
      "group": "verification",
      "relativePath": "tests/integration/test_mcp_endpoints.py",
      "sha256": "4f5082918b614323d31c753238706c5b68af754b7e4ce7fff94e97d4597a7683",
      "sizeBytes": 6929
    },
    {
      "group": "verification",
      "relativePath": "tests/integration/test_mcp_jsonrpc.py",
      "sha256": "6d44dfcec03d7c5b51f1a80845befbf4792ec63145f94c37eea46f297cb52270",
      "sizeBytes": 5156
    },
    {
      "group": "verification",
      "relativePath": "tests/integration/test_simulation_routes.py",
      "sha256": "8e9f17df4a2a092d719a6795aa62d3e5d169bba0de7017b563b8edafdb8bbf5c",
      "sizeBytes": 10879
    },
    {
      "group": "verification",
      "relativePath": "tests/integration/test_subprocess_adapter_routes.py",
      "sha256": "3cb394d63f40d906f061f0e29313a2d7c11ebd77a61205e0c3025ec2655f240d",
      "sizeBytes": 10541
    },
    {
      "group": "verification",
      "relativePath": "tests/perf/test_benchmark_thresholds.py",
      "sha256": "5ae498f9b5b173b89956d690acf1a55171cdbaa5ff9c08bd8321a0e67ad5c89d",
      "sizeBytes": 1420
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_adapter_interface.py",
      "sha256": "ea8ff31d6714576dce67df4e480a4b7d35947d507614e2c1621c9b08ec9632e9",
      "sizeBytes": 3673
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_agent_prompts.py",
      "sha256": "e9d66e6316421b94b4f6ce523e7daf9269f95d2f70e7dc2f6798e6463aa5c6ea",
      "sizeBytes": 1935
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_agent_scaffolding.py",
      "sha256": "382973c9f60f1f4582e5df47a81cda1df43d4168edf0f483f4af7209434c54c3",
      "sizeBytes": 9264
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_agent_workflow.py",
      "sha256": "8548ca51f84d6d9fe2f8ee8edc14ce2c3c6861b2566a79f3d303c671a3a9ab93",
      "sizeBytes": 3261
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_audit_events_api.py",
      "sha256": "414b7e2b8b1d638dd8a834ca4501919fe2fd1799b471a57b958a314d295e1406",
      "sizeBytes": 1322
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_audit_jobs.py",
      "sha256": "7b14f1b0b76a5f856cbd5482a59ac277864c12725ed442ffd612b68821c93500",
      "sizeBytes": 1351
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_audit_s3.py",
      "sha256": "626e4f90b10b605f52451b386bc771261c9c20d09495927f2024f1aa44a8cc9c",
      "sizeBytes": 2253
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_audit_trail.py",
      "sha256": "8128c1773e4cf118cea745a45f54defb4ad55fda4c14d1e8fc52bc55a91c5b0c",
      "sizeBytes": 1184
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_audit_verify.py",
      "sha256": "5f6470c320973b82b40b61b16e67de941cd57302867b22c9b3cef1a79e96c669",
      "sizeBytes": 1197
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_audit_verify_s3.py",
      "sha256": "60c1c53c353a3887370c27f69ab2d444fede6fcf5a7ee902f2ac3cdb163d6c22",
      "sizeBytes": 4618
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_auth_config.py",
      "sha256": "6f96b44391f139104c787eafc96be82f2f91567274bd2529020faf434bbe6102",
      "sizeBytes": 602
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_calculate_pk_parameters_tool.py",
      "sha256": "1d4c5973232e3e45f4ee7c79bac1516eeaa23c6c4781c407464c60ae4f78464a",
      "sizeBytes": 2802
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_celery_job_service.py",
      "sha256": "234a2d9aea53fd62d2169d9c175bbf92569887f9417fd098b20f29eb51da2c3b",
      "sizeBytes": 4514
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_config.py",
      "sha256": "d66be771585a4274a965845c6d4942c3f5c7c56d23a0b4688e6e9c9f1493f419",
      "sizeBytes": 4689
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_environment_detection.py",
      "sha256": "605938a648cb5ba7e3c7b2bbf32bf71ace7487d89b4a77d61554f575c57b20d4",
      "sizeBytes": 1943
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_error_handling.py",
      "sha256": "01526af3de269c83541752f886f520917d344a4be936370fe93a4c450c870538",
      "sizeBytes": 2058
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_get_job_status_tool.py",
      "sha256": "0b01c015e0a1444d4e7a52dcdcf98cf4f5aca52290f4bdbae71843aa00907d53",
      "sizeBytes": 1478
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_get_parameter_value_tool.py",
      "sha256": "df65307a18f0c8811205f07b7c195f3dd9b05c77b5376e8d4a8183327ee5f3a8",
      "sizeBytes": 1606
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_health_endpoint.py",
      "sha256": "547496649eae8dbf5cfcf8cf26a13b9effa73c7d0e999787bbb37ee8cbe651ec",
      "sizeBytes": 1590
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_hpc_stub.py",
      "sha256": "4991add8171dcd51787cd65e0b65310b818700d216a570f5d2d50dfbcd3d90eb",
      "sizeBytes": 1801
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_idempotency.py",
      "sha256": "1768a8a2185d011d6501a8fa453437dad12aca58371823eb816d0ec7cada97e7",
      "sizeBytes": 3087
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_job_registry_persistence.py",
      "sha256": "cd8767cc874b54dd34f7a1e27748d035cf44520269ced86f3c10ee9c0e1b9703",
      "sizeBytes": 2954
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_job_service.py",
      "sha256": "ceb33dcfeede4549833634e6da4dfba7dffb0ae6ab1ed7fc5d7de9e25d16e3dd",
      "sizeBytes": 6046
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_list_parameters_tool.py",
      "sha256": "171d7112db546aaa2c7ed769f4d62ac303d87f0de47c3bdcc021f60e3de60763",
      "sizeBytes": 1506
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_literature_actions.py",
      "sha256": "2c8a450613bcb667f1495300203cee3f608efacfedce723a4b882ad1ae3de970",
      "sizeBytes": 2239
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_literature_evaluation.py",
      "sha256": "1c0029c5216e1e2b078ca3588df1990ea6b076d3c02efdaeb404a0bd7ce415e9",
      "sizeBytes": 1898
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_literature_extractors.py",
      "sha256": "56227b3bcd80a96389d793ab1add96e0f80771ac369dc4a1c7b7fdfd61ab2641",
      "sizeBytes": 1952
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_literature_pipeline.py",
      "sha256": "56d2815347463da1dd30b8d58266f2c4a4d569d21e14331af7a7c0fa34f9a630",
      "sizeBytes": 4001
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_llm_client.py",
      "sha256": "6ef08a067ba59c179860d6ca165a32d537fb6cb79e5f6f753a7bd37666719379",
      "sizeBytes": 1527
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_load_simulation_tool.py",
      "sha256": "1a4503725fa0c0c2062bc41ccde084e3ca359c525624cf4a897d8118d3eb5ba6",
      "sizeBytes": 1438
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_load_simulation_validation.py",
      "sha256": "acca24110bc7830150bb3810ec509d64090f996bb98fff13c00f673fecc4a52d",
      "sizeBytes": 2081
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_metrics_endpoint.py",
      "sha256": "107de5758e1e6a043ef73c50ed3f73e53b86a6b5c3b2a08b4655e65d81156599",
      "sizeBytes": 1542
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_parity_suite.py",
      "sha256": "8467c940121e0c4d7a6b05e5162d2fa2ccae29bee6358cf7fe2677b308b973ed",
      "sizeBytes": 1088
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_pksim_support.py",
      "sha256": "bc71e7ba13e311453e1d401f1dbccff61a1b155fa21aefd66b1e0cbaa3877015",
      "sizeBytes": 2738
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_placeholder.py",
      "sha256": "bf64bdc9e1c6dbf68a608e756efb7fd7fa933fba4c5723cbb6ad04b3469b98dc",
      "sizeBytes": 245
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_population_store.py",
      "sha256": "77abf6a684a1fae70e8b00943817a3ff33e5cdbae15803af41c1f41a22d098d9",
      "sizeBytes": 1592
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_population_tools.py",
      "sha256": "11361be7180e367909f673785707ca415d9175893ff907418635b57ad2c99272",
      "sizeBytes": 2593
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_redaction.py",
      "sha256": "c8c35ccda29b4cd6e660de5344c520de47062877301096557666fd738471dc36",
      "sizeBytes": 543
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_resource_endpoints.py",
      "sha256": "21bcb6519399479fc9e5374c5145cf06bb8e0e78c5428ac5037e8f40fdfc5f83",
      "sizeBytes": 5062
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_run_sensitivity_analysis_tool.py",
      "sha256": "a5c0864b81657a2f57acd7fbe288e5fa766605eaf77772f264959d94ddf624a8",
      "sizeBytes": 1635
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_run_simulation_tool.py",
      "sha256": "f5a4c4f500f48745b7f57fe8e89a661b90b675b40943ffcfd108d0b964329b84",
      "sizeBytes": 2873
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_sensitivity_analysis.py",
      "sha256": "a1089918adca458f648fcd2bf8ae053c82af81d8fbd31555da44160b7ef5b191",
      "sizeBytes": 3197
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_session_registry.py",
      "sha256": "35e617d3e227bfa4b162458f6c4bcc6bbc791c6ff743d7dfcc4ec6462a82f9e4",
      "sizeBytes": 1588
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_session_registry_redis.py",
      "sha256": "9769edf07d35d236fbe8eca9d50c6c81767c69bdc813fa8b3e1ad7d0c9b14121",
      "sizeBytes": 2193
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_set_parameter_value_tool.py",
      "sha256": "33e97d4cf91211ae6fa97f289c18dc1df0762fa6798de81c564d63e9c1c99f25",
      "sizeBytes": 1758
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_snapshot_store.py",
      "sha256": "00fc8f9240922d313d89bd23387e27d968afcaa4693d4ba4447566cb26dd8d43",
      "sizeBytes": 1037
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_subprocess_adapter.py",
      "sha256": "9030315f50274036fd4943f490d9a8856eb384b34aebd1179d7d946c5bbd6b3c",
      "sizeBytes": 16625
    },
    {
      "group": "verification",
      "relativePath": "tests/unit/test_tools_cancel_job.py",
      "sha256": "ac2f6d3178c329168dc6b6fc9fcaa4ef7d16b079ee1a829fe643dbdac9dc2ee7",
      "sizeBytes": 1435
    },
    {
      "group": "root",
      "relativePath": "use-cases/README.md",
      "sha256": "fd04ba85a8995d65968f08d9009a8100026b99b40837c0fe5d3a570a3e076458",
      "sizeBytes": 1612
    },
    {
      "group": "root",
      "relativePath": "use-cases/literature-assisted-calibration.ipynb",
      "sha256": "d89ce76bccd1a7157ee2b9d1258e81458bf3203af7ad3a03be869fa8bc8919a7",
      "sizeBytes": 3765
    },
    {
      "group": "root",
      "relativePath": "use-cases/population-scale.ipynb",
      "sha256": "5d06234a9fb0950ba9b7aba16db20d2df208d0585c254c6b85e66c430371a120",
      "sizeBytes": 3699
    },
    {
      "group": "root",
      "relativePath": "use-cases/sensitivity-in-minutes.ipynb",
      "sha256": "fbf35891b04ae71727f38fcbcfb53c3702d562279a0237d464f274563faa0aa3",
      "sizeBytes": 3313
    }
  ],
  "groupCounts": {
    "container": 2,
    "contract": 18,
    "documentation": 133,
    "governance": 8,
    "operations": 40,
    "root": 185,
    "source": 96,
    "verification": 111
  },
  "id": "pbpk-release-bundle-manifest.v1",
  "packageVersion": "0.4.4",
  "selectionPolicy": {
    "acyclicIntegrityExclusions": [
      "docs/architecture/release_bundle_manifest.json",
      "docs/architecture/contract_manifest.json",
      "src/mcp_bridge/contract/artifacts.py"
    ],
    "excludedPatterns": [
      ".git",
      ".mypy_cache",
      ".pytest_cache",
      ".ruff_cache",
      "__pycache__",
      ".tox",
      ".nox",
      ".venv",
      "venv",
      "env",
      ".tmp_codex_*",
      "build",
      "dist",
      "*.egg-info",
      "var",
      "reports",
      "output",
      "tmp",
      "private_models",
      "figures",
      "downloads",
      "extracted",
      "~"
    ],
    "mode": "staged-source-tree-equivalent"
  },
  "totalBytes": 11905279
}
"""

_SCHEMA_JSON = {
    'assessmentContext.v1': r"""
{
  "$defs": {
    "backend": {
      "enum": [
        "ospsuite",
        "rxode2",
        "external-import"
      ],
      "type": "string"
    },
    "selectionTriplet": {
      "additionalProperties": true,
      "properties": {
        "declared": {
          "type": [
            "string",
            "null"
          ]
        },
        "effective": {
          "type": [
            "string",
            "null"
          ]
        },
        "requested": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "effective"
      ],
      "type": "object"
    },
    "stringArray": {
      "items": {
        "type": "string"
      },
      "type": "array"
    }
  },
  "$id": "https://raw.githubusercontent.com/ToxMCP/pbpk-mcp/main/schemas/assessmentContext.v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "description": "PBPK-side context-alignment object emitted by PBPK MCP.",
  "properties": {
    "assessmentBoundary": {
      "const": "pbpk-context-alignment-only"
    },
    "backend": {
      "$ref": "#/$defs/backend"
    },
    "contextOfUse": {
      "additionalProperties": true,
      "properties": {
        "decisionContext": {
          "$ref": "#/$defs/selectionTriplet"
        },
        "regulatoryUse": {
          "$ref": "#/$defs/selectionTriplet"
        },
        "scientificPurpose": {
          "$ref": "#/$defs/selectionTriplet"
        }
      },
      "required": [
        "regulatoryUse",
        "scientificPurpose",
        "decisionContext"
      ],
      "type": "object"
    },
    "decisionBoundary": {
      "const": "no-ngra-decision-policy"
    },
    "domain": {
      "additionalProperties": true,
      "properties": {
        "compound": {
          "$ref": "#/$defs/selectionTriplet"
        },
        "lifeStage": {
          "$ref": "#/$defs/selectionTriplet"
        },
        "population": {
          "$ref": "#/$defs/selectionTriplet"
        },
        "route": {
          "$ref": "#/$defs/selectionTriplet"
        },
        "species": {
          "$ref": "#/$defs/selectionTriplet"
        }
      },
      "required": [
        "species",
        "route",
        "lifeStage",
        "population",
        "compound"
      ],
      "type": "object"
    },
    "doseScenario": {
      "additionalProperties": true,
      "type": [
        "object",
        "null"
      ]
    },
    "objectId": {
      "minLength": 1,
      "type": "string"
    },
    "objectType": {
      "const": "assessmentContext.v1"
    },
    "populationSupport": {
      "additionalProperties": true,
      "properties": {
        "extrapolationPolicy": {
          "type": [
            "string",
            "null"
          ]
        },
        "supportedGenotypesOrPhenotypes": {
          "$ref": "#/$defs/stringArray"
        },
        "supportedLifeStages": {
          "$ref": "#/$defs/stringArray"
        },
        "supportedPhysiologyContexts": {
          "$ref": "#/$defs/stringArray"
        },
        "supportedSpecies": {
          "$ref": "#/$defs/stringArray"
        },
        "variabilityRepresentation": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "type": [
        "object",
        "null"
      ]
    },
    "simulationId": {
      "type": [
        "string",
        "null"
      ]
    },
    "sourcePlatform": {
      "type": [
        "string",
        "null"
      ]
    },
    "supports": {
      "additionalProperties": true,
      "properties": {
        "decisionRecommendation": {
          "type": "boolean"
        },
        "declaredProfileComparison": {
          "type": "boolean"
        },
        "requestContextAlignment": {
          "type": "boolean"
        },
        "typedNgraHandoff": {
          "type": "boolean"
        }
      },
      "required": [
        "declaredProfileComparison",
        "requestContextAlignment",
        "typedNgraHandoff",
        "decisionRecommendation"
      ],
      "type": "object"
    },
    "targetOutput": {
      "additionalProperties": true,
      "properties": {
        "declared": {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "requested": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "requested",
        "declared"
      ],
      "type": "object"
    },
    "validationDecision": {
      "type": [
        "string",
        "null"
      ]
    },
    "workflowRole": {
      "additionalProperties": true,
      "properties": {
        "downstreamOutputs": {
          "$ref": "#/$defs/stringArray"
        },
        "nonGoals": {
          "$ref": "#/$defs/stringArray"
        },
        "role": {
          "type": [
            "string",
            "null"
          ]
        },
        "upstreamDependencies": {
          "$ref": "#/$defs/stringArray"
        },
        "workflow": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "type": [
        "object",
        "null"
      ]
    }
  },
  "required": [
    "objectType",
    "objectId",
    "backend",
    "assessmentBoundary",
    "decisionBoundary",
    "contextOfUse",
    "domain",
    "targetOutput",
    "supports"
  ],
  "title": "assessmentContext.v1",
  "type": "object"
}
""",
    'berInputBundle.v1': r"""
{
  "$defs": {
    "backend": {
      "enum": [
        "ospsuite",
        "rxode2",
        "external-import"
      ],
      "type": "string"
    },
    "stringArray": {
      "items": {
        "type": "string"
      },
      "type": "array"
    },
    "trueDoseAdjustment": {
      "additionalProperties": true,
      "properties": {
        "applied": {
          "type": "boolean"
        },
        "basis": {
          "type": [
            "string",
            "null"
          ]
        },
        "summary": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "applied"
      ],
      "type": "object"
    }
  },
  "$id": "https://raw.githubusercontent.com/ToxMCP/pbpk-mcp/main/schemas/berInputBundle.v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "description": "Thin BER-ready PBPK-side handoff bundle emitted by PBPK MCP.",
  "properties": {
    "assessmentBoundary": {
      "const": "external-ber-calculation-only"
    },
    "backend": {
      "$ref": "#/$defs/backend"
    },
    "blockingReasons": {
      "$ref": "#/$defs/stringArray"
    },
    "comparisonMetric": {
      "minLength": 1,
      "type": "string"
    },
    "decisionBoundary": {
      "const": "ber-calculation-and-decision-owned-by-external-orchestrator"
    },
    "decisionOwner": {
      "const": "external-orchestrator"
    },
    "internalExposureEstimateRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "internalExposureMetric": {
      "additionalProperties": true,
      "properties": {
        "metric": {
          "minLength": 1,
          "type": "string"
        },
        "outputPath": {
          "type": [
            "string",
            "null"
          ]
        },
        "unit": {
          "type": [
            "string",
            "null"
          ]
        },
        "value": {
          "type": [
            "number",
            "null"
          ]
        }
      },
      "required": [
        "metric",
        "value",
        "outputPath"
      ],
      "type": [
        "object",
        "null"
      ]
    },
    "objectId": {
      "minLength": 1,
      "type": "string"
    },
    "objectType": {
      "const": "berInputBundle.v1"
    },
    "podMetadata": {
      "additionalProperties": true,
      "properties": {
        "basis": {
          "type": [
            "string",
            "null"
          ]
        },
        "metric": {
          "type": [
            "string",
            "null"
          ]
        },
        "ref": {
          "type": [
            "string",
            "null"
          ]
        },
        "source": {
          "type": [
            "string",
            "null"
          ]
        },
        "summary": {
          "type": [
            "string",
            "null"
          ]
        },
        "unit": {
          "type": [
            "string",
            "null"
          ]
        },
        "value": {
          "type": [
            "number",
            "null"
          ]
        }
      },
      "type": "object"
    },
    "podRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "pointOfDepartureReferenceRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "qualificationSummaryRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "requiredExternalInputs": {
      "$ref": "#/$defs/stringArray"
    },
    "simulationId": {
      "type": [
        "string",
        "null"
      ]
    },
    "sourcePlatform": {
      "type": [
        "string",
        "null"
      ]
    },
    "status": {
      "enum": [
        "ready-for-external-ber-calculation",
        "incomplete"
      ],
      "type": "string"
    },
    "supports": {
      "additionalProperties": true,
      "properties": {
        "decisionRecommendation": {
          "type": "boolean"
        },
        "externalBerCalculation": {
          "type": "boolean"
        },
        "externalPodReferenceAttached": {
          "type": "boolean"
        },
        "internalExposureMetricAttached": {
          "type": "boolean"
        },
        "trueDoseMetadataAttached": {
          "type": "boolean"
        }
      },
      "required": [
        "internalExposureMetricAttached",
        "externalPodReferenceAttached",
        "trueDoseMetadataAttached",
        "externalBerCalculation",
        "decisionRecommendation"
      ],
      "type": "object"
    },
    "trueDoseAdjustment": {
      "$ref": "#/$defs/trueDoseAdjustment"
    },
    "trueDoseAdjustmentApplied": {
      "type": "boolean"
    },
    "uncertaintySummaryRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "warnings": {
      "$ref": "#/$defs/stringArray"
    }
  },
  "required": [
    "objectType",
    "objectId",
    "backend",
    "assessmentBoundary",
    "decisionBoundary",
    "decisionOwner",
    "status",
    "comparisonMetric",
    "trueDoseAdjustment",
    "trueDoseAdjustmentApplied",
    "supports",
    "requiredExternalInputs",
    "blockingReasons"
  ],
  "title": "berInputBundle.v1",
  "type": "object"
}
""",
    'internalExposureEstimate.v1': r"""
{
  "$defs": {
    "backend": {
      "enum": [
        "ospsuite",
        "rxode2",
        "external-import"
      ],
      "type": "string"
    },
    "outputSummary": {
      "additionalProperties": true,
      "properties": {
        "auc0Tlast": {
          "type": [
            "number",
            "null"
          ]
        },
        "aucUnitBasis": {
          "type": [
            "string",
            "null"
          ]
        },
        "cmax": {
          "type": [
            "number",
            "null"
          ]
        },
        "outputPath": {
          "type": [
            "string",
            "null"
          ]
        },
        "pointCount": {
          "minimum": 0,
          "type": "integer"
        },
        "tmax": {
          "type": [
            "number",
            "null"
          ]
        },
        "unit": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "outputPath",
        "pointCount",
        "cmax",
        "tmax",
        "auc0Tlast",
        "aucUnitBasis"
      ],
      "type": "object"
    },
    "stringArray": {
      "items": {
        "type": "string"
      },
      "type": "array"
    }
  },
  "$id": "https://raw.githubusercontent.com/ToxMCP/pbpk-mcp/main/schemas/internalExposureEstimate.v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "description": "PBPK-side deterministic internal-exposure estimate emitted by PBPK MCP.",
  "properties": {
    "analyte": {
      "type": [
        "string",
        "null"
      ]
    },
    "assessmentBoundary": {
      "const": "pbpk-side-internal-exposure-estimate-only"
    },
    "backend": {
      "$ref": "#/$defs/backend"
    },
    "candidateOutputCount": {
      "minimum": 0,
      "type": "integer"
    },
    "candidateOutputs": {
      "items": {
        "$ref": "#/$defs/outputSummary"
      },
      "type": "array"
    },
    "candidateOutputsTruncated": {
      "type": [
        "boolean",
        "null"
      ]
    },
    "decisionBoundary": {
      "const": "no-ngra-decision-policy"
    },
    "distribution": {
      "additionalProperties": true,
      "type": [
        "object",
        "null"
      ]
    },
    "doseScenario": {
      "additionalProperties": true,
      "type": [
        "object",
        "null"
      ]
    },
    "objectId": {
      "minLength": 1,
      "type": "string"
    },
    "objectType": {
      "const": "internalExposureEstimate.v1"
    },
    "population": {
      "type": [
        "string",
        "null"
      ]
    },
    "requestedTargetOutput": {
      "type": [
        "string",
        "null"
      ]
    },
    "resultsId": {
      "type": [
        "string",
        "null"
      ]
    },
    "route": {
      "type": [
        "string",
        "null"
      ]
    },
    "selectedOutput": {
      "additionalProperties": true,
      "properties": {
        "auc0Tlast": {
          "type": [
            "number",
            "null"
          ]
        },
        "aucUnitBasis": {
          "type": [
            "string",
            "null"
          ]
        },
        "cmax": {
          "type": [
            "number",
            "null"
          ]
        },
        "outputPath": {
          "type": [
            "string",
            "null"
          ]
        },
        "pointCount": {
          "minimum": 0,
          "type": "integer"
        },
        "tmax": {
          "type": [
            "number",
            "null"
          ]
        },
        "unit": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "outputPath",
        "pointCount",
        "cmax",
        "tmax",
        "auc0Tlast",
        "aucUnitBasis"
      ],
      "type": [
        "object",
        "null"
      ]
    },
    "selectionReason": {
      "type": [
        "string",
        "null"
      ]
    },
    "selectionStatus": {
      "type": [
        "string",
        "null"
      ]
    },
    "simulationId": {
      "type": [
        "string",
        "null"
      ]
    },
    "source": {
      "minLength": 1,
      "type": "string"
    },
    "sourcePlatform": {
      "type": [
        "string",
        "null"
      ]
    },
    "species": {
      "type": [
        "string",
        "null"
      ]
    },
    "status": {
      "enum": [
        "available",
        "not-available"
      ],
      "type": "string"
    },
    "supports": {
      "additionalProperties": true,
      "properties": {
        "decisionRecommendation": {
          "type": "boolean"
        },
        "deterministicMetricSelection": {
          "type": "boolean"
        },
        "externalBerHandoff": {
          "type": "boolean"
        },
        "populationDistributionSummary": {
          "type": "boolean"
        }
      },
      "required": [
        "deterministicMetricSelection",
        "populationDistributionSummary",
        "externalBerHandoff",
        "decisionRecommendation"
      ],
      "type": "object"
    },
    "warnings": {
      "$ref": "#/$defs/stringArray"
    }
  },
  "required": [
    "objectType",
    "objectId",
    "backend",
    "assessmentBoundary",
    "decisionBoundary",
    "status",
    "source",
    "candidateOutputCount",
    "candidateOutputs",
    "supports",
    "warnings"
  ],
  "title": "internalExposureEstimate.v1",
  "type": "object"
}
""",
    'pbpkQualificationSummary.v1': r"""
{
  "$defs": {
    "backend": {
      "enum": [
        "ospsuite",
        "rxode2",
        "external-import"
      ],
      "type": "string"
    },
    "stringArray": {
      "items": {
        "type": "string"
      },
      "type": "array"
    }
  },
  "$id": "https://raw.githubusercontent.com/ToxMCP/pbpk-mcp/main/schemas/pbpkQualificationSummary.v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "description": "PBPK-side qualification summary emitted by PBPK MCP.",
  "properties": {
    "assessmentBoundary": {
      "enum": [
        "pbpk-execution-and-qualification-substrate-only",
        "external-pbpk-normalization-only"
      ],
      "type": "string"
    },
    "backend": {
      "$ref": "#/$defs/backend"
    },
    "cautionSummary": {
      "additionalProperties": true,
      "properties": {
        "advisoryCount": {
          "minimum": 0,
          "type": [
            "integer",
            "null"
          ]
        },
        "blockingCount": {
          "minimum": 0,
          "type": [
            "integer",
            "null"
          ]
        },
        "blockingRecommended": {
          "type": [
            "boolean",
            "null"
          ]
        },
        "cautions": {
          "items": {
            "additionalProperties": true,
            "properties": {
              "cautionType": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "code": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "currentStatus": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "handling": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "message": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "requiresHumanReview": {
                "type": [
                  "boolean",
                  "null"
                ]
              },
              "scope": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "severity": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "sourceSurface": {
                "type": [
                  "string",
                  "null"
                ]
              }
            },
            "type": "object"
          },
          "type": "array"
        },
        "highestSeverity": {
          "type": [
            "string",
            "null"
          ]
        },
        "requiresHumanReview": {
          "type": [
            "boolean",
            "null"
          ]
        },
        "summaryVersion": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "type": [
        "object",
        "null"
      ]
    },
    "checklistScore": {
      "type": [
        "number",
        "null"
      ]
    },
    "decisionBoundary": {
      "const": "no-ngra-decision-policy"
    },
    "evidenceBasis": {
      "additionalProperties": true,
      "properties": {
        "basisType": {
          "type": [
            "string",
            "null"
          ]
        },
        "inVivoSupportStatus": {
          "type": [
            "string",
            "null"
          ]
        },
        "iviveLinkageStatus": {
          "type": [
            "string",
            "null"
          ]
        },
        "parameterizationBasis": {
          "type": [
            "string",
            "null"
          ]
        },
        "populationVariabilityStatus": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "type": [
        "object",
        "null"
      ]
    },
    "evidenceStatus": {
      "minLength": 1,
      "type": "string"
    },
    "executableVerificationStatus": {
      "type": [
        "string",
        "null"
      ]
    },
    "exportBlockPolicy": {
      "additionalProperties": true,
      "properties": {
        "blockReasons": {
          "items": {
            "additionalProperties": true,
            "properties": {
              "appliesTo": {
                "$ref": "#/$defs/stringArray"
              },
              "code": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "currentStatus": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "message": {
                "type": [
                  "string",
                  "null"
                ]
              },
              "requiredFields": {
                "$ref": "#/$defs/stringArray"
              },
              "severity": {
                "type": [
                  "string",
                  "null"
                ]
              }
            },
            "type": "object"
          },
          "type": "array"
        },
        "blockedViewModes": {
          "$ref": "#/$defs/stringArray"
        },
        "contextualizedRenderOnly": {
          "type": [
            "boolean",
            "null"
          ]
        },
        "defaultAction": {
          "type": [
            "string",
            "null"
          ]
        },
        "notes": {
          "$ref": "#/$defs/stringArray"
        },
        "policyVersion": {
          "type": [
            "string",
            "null"
          ]
        },
        "requiredFields": {
          "$ref": "#/$defs/stringArray"
        },
        "workflow": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "type": [
        "object",
        "null"
      ]
    },
    "label": {
      "type": [
        "string",
        "null"
      ]
    },
    "limitations": {
      "$ref": "#/$defs/stringArray"
    },
    "missingEvidenceCount": {
      "minimum": 0,
      "type": "integer"
    },
    "objectId": {
      "minLength": 1,
      "type": "string"
    },
    "objectType": {
      "const": "pbpkQualificationSummary.v1"
    },
    "oecdReadiness": {
      "minLength": 1,
      "type": "string"
    },
    "performanceEvidenceBoundary": {
      "type": [
        "string",
        "null"
      ]
    },
    "platformClass": {
      "type": [
        "string",
        "null"
      ]
    },
    "profileSource": {
      "type": [
        "string",
        "null"
      ]
    },
    "qualificationLevel": {
      "minLength": 1,
      "type": "string"
    },
    "requiredExternalInputs": {
      "$ref": "#/$defs/stringArray"
    },
    "reviewStatus": {
      "additionalProperties": true,
      "properties": {
        "declaredStatus": {
          "type": [
            "string",
            "null"
          ]
        },
        "focusTopics": {
          "$ref": "#/$defs/stringArray"
        },
        "priorUseCount": {
          "minimum": 0,
          "type": [
            "integer",
            "null"
          ]
        },
        "requiresReviewerAttention": {
          "type": [
            "boolean",
            "null"
          ]
        },
        "resolvedDissentCount": {
          "minimum": 0,
          "type": [
            "integer",
            "null"
          ]
        },
        "reviewRecordCount": {
          "minimum": 0,
          "type": [
            "integer",
            "null"
          ]
        },
        "revisionEntryCount": {
          "minimum": 0,
          "type": [
            "integer",
            "null"
          ]
        },
        "revisionStatus": {
          "type": [
            "string",
            "null"
          ]
        },
        "status": {
          "type": [
            "string",
            "null"
          ]
        },
        "summary": {
          "type": [
            "string",
            "null"
          ]
        },
        "unresolvedDissentCount": {
          "minimum": 0,
          "type": [
            "integer",
            "null"
          ]
        }
      },
      "type": [
        "object",
        "null"
      ]
    },
    "riskAssessmentReady": {
      "type": "boolean"
    },
    "scientificProfile": {
      "type": "boolean"
    },
    "simulationId": {
      "type": [
        "string",
        "null"
      ]
    },
    "sourcePlatform": {
      "type": [
        "string",
        "null"
      ]
    },
    "state": {
      "minLength": 1,
      "type": "string"
    },
    "summary": {
      "type": [
        "string",
        "null"
      ]
    },
    "supports": {
      "additionalProperties": true,
      "properties": {
        "externalBerHandoff": {
          "type": "boolean"
        },
        "oecdDossierExport": {
          "type": "boolean"
        },
        "regulatoryDecision": {
          "type": "boolean"
        },
        "typedNgraHandoff": {
          "type": "boolean"
        }
      },
      "required": [
        "typedNgraHandoff",
        "oecdDossierExport",
        "externalBerHandoff",
        "regulatoryDecision"
      ],
      "type": "object"
    },
    "validationDecision": {
      "type": [
        "string",
        "null"
      ]
    },
    "validationReferences": {
      "items": {
        "type": "string"
      },
      "type": "array"
    },
    "withinDeclaredContext": {
      "type": [
        "boolean",
        "null"
      ]
    },
    "workflowClaimBoundaries": {
      "additionalProperties": true,
      "properties": {
        "directRegulatoryDoseDerivation": {
          "type": [
            "string",
            "null"
          ]
        },
        "exposureLedPrioritization": {
          "type": [
            "string",
            "null"
          ]
        },
        "forwardDosimetry": {
          "type": [
            "string",
            "null"
          ]
        },
        "reverseDosimetry": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "type": [
        "object",
        "null"
      ]
    }
  },
  "required": [
    "objectType",
    "objectId",
    "backend",
    "assessmentBoundary",
    "decisionBoundary",
    "state",
    "qualificationLevel",
    "oecdReadiness",
    "evidenceStatus",
    "missingEvidenceCount",
    "supports",
    "requiredExternalInputs",
    "limitations"
  ],
  "title": "pbpkQualificationSummary.v1",
  "type": "object"
}
""",
    'pointOfDepartureReference.v1': r"""
{
  "$defs": {
    "backend": {
      "enum": [
        "ospsuite",
        "rxode2",
        "external-import"
      ],
      "type": "string"
    },
    "stringArray": {
      "items": {
        "type": "string"
      },
      "type": "array"
    },
    "trueDoseAdjustment": {
      "additionalProperties": true,
      "properties": {
        "applied": {
          "type": "boolean"
        },
        "basis": {
          "type": [
            "string",
            "null"
          ]
        },
        "summary": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "applied"
      ],
      "type": "object"
    }
  },
  "$id": "https://raw.githubusercontent.com/ToxMCP/pbpk-mcp/main/schemas/pointOfDepartureReference.v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "description": "Typed external point-of-departure reference emitted by PBPK MCP.",
  "properties": {
    "assessmentBoundary": {
      "const": "external-pod-reference-only"
    },
    "backend": {
      "$ref": "#/$defs/backend"
    },
    "basis": {
      "type": [
        "string",
        "null"
      ]
    },
    "decisionBoundary": {
      "const": "pod-interpretation-and-ber-policy-owned-by-external-orchestrator"
    },
    "decisionOwner": {
      "const": "external-orchestrator"
    },
    "metric": {
      "type": [
        "string",
        "null"
      ]
    },
    "objectId": {
      "minLength": 1,
      "type": "string"
    },
    "objectType": {
      "const": "pointOfDepartureReference.v1"
    },
    "podRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "requiredExternalInputs": {
      "$ref": "#/$defs/stringArray"
    },
    "simulationId": {
      "type": [
        "string",
        "null"
      ]
    },
    "source": {
      "type": [
        "string",
        "null"
      ]
    },
    "sourcePlatform": {
      "type": [
        "string",
        "null"
      ]
    },
    "status": {
      "enum": [
        "attached-external-reference",
        "not-attached"
      ],
      "type": "string"
    },
    "summary": {
      "type": [
        "string",
        "null"
      ]
    },
    "supports": {
      "additionalProperties": true,
      "properties": {
        "decisionRecommendation": {
          "type": "boolean"
        },
        "externalBerCalculation": {
          "type": "boolean"
        },
        "metricMetadataAttached": {
          "type": "boolean"
        },
        "trueDoseMetadataAttached": {
          "type": "boolean"
        },
        "typedReference": {
          "type": "boolean"
        }
      },
      "required": [
        "typedReference",
        "metricMetadataAttached",
        "trueDoseMetadataAttached",
        "externalBerCalculation",
        "decisionRecommendation"
      ],
      "type": "object"
    },
    "trueDoseAdjustment": {
      "$ref": "#/$defs/trueDoseAdjustment"
    },
    "trueDoseAdjustmentApplied": {
      "type": "boolean"
    },
    "unit": {
      "type": [
        "string",
        "null"
      ]
    },
    "value": {
      "type": [
        "number",
        "null"
      ]
    },
    "warnings": {
      "$ref": "#/$defs/stringArray"
    }
  },
  "required": [
    "objectType",
    "objectId",
    "backend",
    "assessmentBoundary",
    "decisionBoundary",
    "decisionOwner",
    "status",
    "trueDoseAdjustment",
    "trueDoseAdjustmentApplied",
    "supports",
    "requiredExternalInputs",
    "warnings"
  ],
  "title": "pointOfDepartureReference.v1",
  "type": "object"
}
""",
    'uncertaintyHandoff.v1': r"""
{
  "$defs": {
    "backend": {
      "enum": [
        "ospsuite",
        "rxode2",
        "external-import"
      ],
      "type": "string"
    },
    "stringArray": {
      "items": {
        "type": "string"
      },
      "type": "array"
    }
  },
  "$id": "https://raw.githubusercontent.com/ToxMCP/pbpk-mcp/main/schemas/uncertaintyHandoff.v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "description": "PBPK-to-cross-domain uncertainty handoff object emitted by PBPK MCP.",
  "properties": {
    "assessmentBoundary": {
      "const": "pbpk-to-cross-domain-uncertainty-handoff-only"
    },
    "backend": {
      "$ref": "#/$defs/backend"
    },
    "blockingReasons": {
      "$ref": "#/$defs/stringArray"
    },
    "decisionBoundary": {
      "const": "cross-domain-uncertainty-synthesis-owned-by-external-orchestrator"
    },
    "decisionOwner": {
      "const": "external-orchestrator"
    },
    "internalExposureEstimateRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "objectId": {
      "minLength": 1,
      "type": "string"
    },
    "objectType": {
      "const": "uncertaintyHandoff.v1"
    },
    "pbpkQualificationSummaryRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "pointOfDepartureReferenceRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "requiredExternalInputs": {
      "$ref": "#/$defs/stringArray"
    },
    "simulationId": {
      "type": [
        "string",
        "null"
      ]
    },
    "sourcePlatform": {
      "type": [
        "string",
        "null"
      ]
    },
    "status": {
      "minLength": 1,
      "type": "string"
    },
    "supports": {
      "additionalProperties": true,
      "properties": {
        "crossDomainUncertaintySynthesis": {
          "type": "boolean"
        },
        "decisionRecommendation": {
          "type": "boolean"
        },
        "pbpkQualificationAttached": {
          "type": "boolean"
        },
        "pbpkUncertaintySummaryAttached": {
          "type": "boolean"
        },
        "typedUncertaintySemanticsAttached": {
          "type": "boolean"
        }
      },
      "required": [
        "pbpkQualificationAttached",
        "pbpkUncertaintySummaryAttached",
        "typedUncertaintySemanticsAttached",
        "crossDomainUncertaintySynthesis",
        "decisionRecommendation"
      ],
      "type": "object"
    },
    "uncertaintyRegisterReferenceRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "uncertaintySummaryRef": {
      "type": [
        "string",
        "null"
      ]
    }
  },
  "required": [
    "objectType",
    "objectId",
    "backend",
    "assessmentBoundary",
    "decisionBoundary",
    "decisionOwner",
    "status",
    "supports",
    "requiredExternalInputs",
    "blockingReasons"
  ],
  "title": "uncertaintyHandoff.v1",
  "type": "object"
}
""",
    'uncertaintyRegisterReference.v1': r"""
{
  "$defs": {
    "backend": {
      "enum": [
        "ospsuite",
        "rxode2",
        "external-import"
      ],
      "type": "string"
    },
    "stringArray": {
      "items": {
        "type": "string"
      },
      "type": "array"
    }
  },
  "$id": "https://raw.githubusercontent.com/ToxMCP/pbpk-mcp/main/schemas/uncertaintyRegisterReference.v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "description": "Typed external uncertainty-register reference emitted by PBPK MCP.",
  "properties": {
    "assessmentBoundary": {
      "const": "external-uncertainty-register-reference-only"
    },
    "backend": {
      "$ref": "#/$defs/backend"
    },
    "decisionBoundary": {
      "const": "cross-domain-uncertainty-synthesis-owned-by-external-orchestrator"
    },
    "decisionOwner": {
      "const": "external-orchestrator"
    },
    "objectId": {
      "minLength": 1,
      "type": "string"
    },
    "objectType": {
      "const": "uncertaintyRegisterReference.v1"
    },
    "owner": {
      "type": [
        "string",
        "null"
      ]
    },
    "registerRef": {
      "type": [
        "string",
        "null"
      ]
    },
    "requiredExternalInputs": {
      "$ref": "#/$defs/stringArray"
    },
    "scope": {
      "type": [
        "string",
        "null"
      ]
    },
    "simulationId": {
      "type": [
        "string",
        "null"
      ]
    },
    "source": {
      "type": [
        "string",
        "null"
      ]
    },
    "sourcePlatform": {
      "type": [
        "string",
        "null"
      ]
    },
    "status": {
      "enum": [
        "attached-external-reference",
        "not-attached"
      ],
      "type": "string"
    },
    "summary": {
      "type": [
        "string",
        "null"
      ]
    },
    "supports": {
      "additionalProperties": true,
      "properties": {
        "crossDomainUncertaintySynthesis": {
          "type": "boolean"
        },
        "decisionRecommendation": {
          "type": "boolean"
        },
        "typedReference": {
          "type": "boolean"
        }
      },
      "required": [
        "typedReference",
        "crossDomainUncertaintySynthesis",
        "decisionRecommendation"
      ],
      "type": "object"
    },
    "warnings": {
      "$ref": "#/$defs/stringArray"
    }
  },
  "required": [
    "objectType",
    "objectId",
    "backend",
    "assessmentBoundary",
    "decisionBoundary",
    "decisionOwner",
    "status",
    "supports",
    "requiredExternalInputs",
    "warnings"
  ],
  "title": "uncertaintyRegisterReference.v1",
  "type": "object"
}
""",
    'uncertaintySummary.v1': r"""
{
  "$defs": {
    "backend": {
      "enum": [
        "ospsuite",
        "rxode2",
        "external-import"
      ],
      "type": "string"
    },
    "stringArray": {
      "items": {
        "type": "string"
      },
      "type": "array"
    }
  },
  "$id": "https://raw.githubusercontent.com/ToxMCP/pbpk-mcp/main/schemas/uncertaintySummary.v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "description": "PBPK-side uncertainty summary emitted by PBPK MCP.",
  "properties": {
    "assessmentBoundary": {
      "const": "pbpk-side-uncertainty-summary-only"
    },
    "backend": {
      "$ref": "#/$defs/backend"
    },
    "bundleMetadata": {
      "additionalProperties": true,
      "type": [
        "object",
        "null"
      ]
    },
    "decisionBoundary": {
      "const": "no-ngra-decision-policy"
    },
    "evidenceRowCount": {
      "minimum": 0,
      "type": "integer"
    },
    "evidenceSource": {
      "type": [
        "string",
        "null"
      ]
    },
    "hasResidualUncertainty": {
      "type": "boolean"
    },
    "hasSensitivityAnalysis": {
      "type": "boolean"
    },
    "hasVariabilityApproach": {
      "type": "boolean"
    },
    "hasVariabilityPropagation": {
      "type": "boolean"
    },
    "issueCount": {
      "minimum": 0,
      "type": "integer"
    },
    "objectId": {
      "minLength": 1,
      "type": "string"
    },
    "objectType": {
      "const": "uncertaintySummary.v1"
    },
    "requiredExternalInputs": {
      "$ref": "#/$defs/stringArray"
    },
    "residualUncertaintyStatus": {
      "type": [
        "string",
        "null"
      ]
    },
    "semanticCoverage": {
      "additionalProperties": true,
      "properties": {
        "declaredOnlyComponents": {
          "$ref": "#/$defs/stringArray"
        },
        "declaredOnlyRowCount": {
          "minimum": 0,
          "type": "integer"
        },
        "overallQuantificationStatus": {
          "minLength": 1,
          "type": "string"
        },
        "quantifiedComponents": {
          "$ref": "#/$defs/stringArray"
        },
        "quantifiedRowCount": {
          "minimum": 0,
          "type": "integer"
        },
        "residualUncertaintyQuantificationStatus": {
          "minLength": 1,
          "type": "string"
        },
        "residualUncertaintyType": {
          "minLength": 1,
          "type": "string"
        },
        "sensitivityQuantificationStatus": {
          "minLength": 1,
          "type": "string"
        },
        "sensitivityType": {
          "minLength": 1,
          "type": "string"
        },
        "variabilityQuantificationStatus": {
          "minLength": 1,
          "type": "string"
        },
        "variabilityType": {
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "overallQuantificationStatus",
        "variabilityType",
        "sensitivityType",
        "residualUncertaintyType",
        "variabilityQuantificationStatus",
        "sensitivityQuantificationStatus",
        "residualUncertaintyQuantificationStatus",
        "quantifiedRowCount",
        "declaredOnlyRowCount",
        "quantifiedComponents",
        "declaredOnlyComponents"
      ],
      "type": "object"
    },
    "sensitivityStatus": {
      "type": [
        "string",
        "null"
      ]
    },
    "simulationId": {
      "type": [
        "string",
        "null"
      ]
    },
    "sourcePlatform": {
      "type": [
        "string",
        "null"
      ]
    },
    "sources": {
      "$ref": "#/$defs/stringArray"
    },
    "status": {
      "minLength": 1,
      "type": "string"
    },
    "summary": {
      "type": [
        "string",
        "null"
      ]
    },
    "supports": {
      "additionalProperties": true,
      "properties": {
        "decisionRecommendation": {
          "type": "boolean"
        },
        "typedNgraHandoff": {
          "type": "boolean"
        },
        "typedUncertaintySemantics": {
          "type": "boolean"
        }
      },
      "required": [
        "typedUncertaintySemantics",
        "typedNgraHandoff",
        "decisionRecommendation"
      ],
      "type": "object"
    },
    "totalEvidenceRows": {
      "minimum": 0,
      "type": "integer"
    },
    "variabilityStatus": {
      "type": [
        "string",
        "null"
      ]
    }
  },
  "required": [
    "objectType",
    "objectId",
    "backend",
    "assessmentBoundary",
    "decisionBoundary",
    "status",
    "evidenceRowCount",
    "totalEvidenceRows",
    "semanticCoverage",
    "supports",
    "requiredExternalInputs"
  ],
  "title": "uncertaintySummary.v1",
  "type": "object"
}
""",
}

_SCHEMA_EXAMPLE_JSON = {
    'assessmentContext.v1': r"""
{
  "assessmentBoundary": "pbpk-context-alignment-only",
  "backend": "external-import",
  "contextOfUse": {
    "decisionContext": {
      "declared": null,
      "effective": "BER handoff",
      "requested": "BER handoff"
    },
    "regulatoryUse": {
      "declared": null,
      "effective": "research-only",
      "requested": "research-only"
    },
    "scientificPurpose": {
      "declared": null,
      "effective": "Tier 1 internal exposure screening",
      "requested": "Tier 1 internal exposure screening"
    }
  },
  "decisionBoundary": "no-ngra-decision-policy",
  "domain": {
    "compound": {
      "declared": null,
      "effective": null,
      "requested": null
    },
    "lifeStage": {
      "declared": null,
      "effective": null,
      "requested": null
    },
    "population": {
      "declared": "adult",
      "effective": "adult",
      "requested": "adult"
    },
    "route": {
      "declared": "oral",
      "effective": "oral",
      "requested": "oral"
    },
    "species": {
      "declared": "human",
      "effective": "human",
      "requested": "human"
    }
  },
  "doseScenario": null,
  "objectId": "gastroplus-assessment-context",
  "objectType": "assessmentContext.v1",
  "populationSupport": {
    "extrapolationPolicy": "outside-declared-population-context-requires-human-review",
    "supportedGenotypesOrPhenotypes": [],
    "supportedLifeStages": [],
    "supportedPhysiologyContexts": [],
    "supportedSpecies": [
      "human"
    ],
    "variabilityRepresentation": "not-declared"
  },
  "simulationId": null,
  "sourcePlatform": "GastroPlus",
  "supports": {
    "decisionRecommendation": false,
    "declaredProfileComparison": true,
    "requestContextAlignment": true,
    "typedNgraHandoff": true
  },
  "targetOutput": {
    "declared": [
      "Plasma|Parent|Concentration"
    ],
    "requested": "Plasma|Parent|Concentration"
  },
  "validationDecision": null,
  "workflowRole": {
    "downstreamOutputs": [
      "internal exposure estimates",
      "PBPK qualification and uncertainty handoff objects",
      "BER-ready input bundle when compatible external PoD metadata are attached"
    ],
    "nonGoals": [
      "standalone weight-of-evidence integration",
      "standalone exposure assessment ownership",
      "direct regulatory decision authority",
      "standalone hazard or AOP interpretation"
    ],
    "role": "pbpk-exposure-translation-and-internal-dose-support",
    "upstreamDependencies": [
      "dose scenario or exposure estimate defined outside PBPK MCP",
      "in vitro ADME or IVIVE parameterization evidence defined outside PBPK MCP",
      "bioactivity, point-of-departure, or NAM interpretation defined outside PBPK MCP"
    ],
    "workflow": "exposure-led-ngra"
  }
}
""",
    'berInputBundle.v1': r"""
{
  "assessmentBoundary": "external-ber-calculation-only",
  "backend": "external-import",
  "blockingReasons": [],
  "comparisonMetric": "cmax",
  "decisionBoundary": "ber-calculation-and-decision-owned-by-external-orchestrator",
  "decisionOwner": "external-orchestrator",
  "internalExposureEstimateRef": "gastroplus-internal-exposure-estimate",
  "internalExposureMetric": {
    "metric": "cmax",
    "outputPath": "Plasma|Parent|Concentration",
    "unit": "uM",
    "value": 3.2
  },
  "objectId": "gastroplus-ber-input-bundle",
  "objectType": "berInputBundle.v1",
  "podMetadata": {
    "basis": "true-dose-adjusted",
    "metric": "cmax",
    "ref": "pod-001",
    "source": "httr-benchmark",
    "summary": null,
    "unit": "uM",
    "value": null
  },
  "podRef": "pod-001",
  "pointOfDepartureReferenceRef": "gastroplus-point-of-departure-reference",
  "qualificationSummaryRef": "gastroplus-qualification-summary",
  "requiredExternalInputs": [
    "BER calculation and decision policy outside PBPK MCP"
  ],
  "simulationId": null,
  "sourcePlatform": "GastroPlus",
  "status": "ready-for-external-ber-calculation",
  "supports": {
    "decisionRecommendation": false,
    "externalBerCalculation": true,
    "externalPodReferenceAttached": true,
    "internalExposureMetricAttached": true,
    "trueDoseMetadataAttached": true
  },
  "trueDoseAdjustment": {
    "applied": true,
    "basis": "free-concentration",
    "summary": "Normalized to free concentration"
  },
  "trueDoseAdjustmentApplied": true,
  "uncertaintySummaryRef": "gastroplus-uncertainty-summary",
  "warnings": []
}
""",
    'internalExposureEstimate.v1': r"""
{
  "analyte": null,
  "assessmentBoundary": "pbpk-side-internal-exposure-estimate-only",
  "backend": "external-import",
  "candidateOutputCount": 1,
  "candidateOutputs": [
    {
      "auc0Tlast": 10.5,
      "aucUnitBasis": "uM*h",
      "cmax": 3.2,
      "outputPath": "Plasma|Parent|Concentration",
      "pointCount": 0,
      "tmax": 1.5,
      "unit": "uM"
    }
  ],
  "candidateOutputsTruncated": false,
  "decisionBoundary": "no-ngra-decision-policy",
  "distribution": null,
  "doseScenario": null,
  "objectId": "gastroplus-internal-exposure-estimate",
  "objectType": "internalExposureEstimate.v1",
  "population": "adult",
  "requestedTargetOutput": "Plasma|Parent|Concentration",
  "resultsId": null,
  "route": "oral",
  "selectedOutput": {
    "auc0Tlast": 10.5,
    "aucUnitBasis": "uM*h",
    "cmax": 3.2,
    "outputPath": "Plasma|Parent|Concentration",
    "pointCount": 0,
    "tmax": 1.5,
    "unit": "uM"
  },
  "selectionStatus": "explicit",
  "simulationId": null,
  "source": "external-import",
  "sourcePlatform": "GastroPlus",
  "species": "human",
  "status": "available",
  "supports": {
    "decisionRecommendation": false,
    "deterministicMetricSelection": true,
    "externalBerHandoff": true,
    "populationDistributionSummary": false
  },
  "warnings": []
}
""",
    'pbpkQualificationSummary.v1': r"""
{
  "assessmentBoundary": "external-pbpk-normalization-only",
  "backend": "external-import",
  "cautionSummary": {
    "advisoryCount": 1,
    "blockingCount": 3,
    "blockingRecommended": true,
    "cautions": [
      {
        "cautionType": "summary-transport-risk",
        "code": "detached-summary-overread",
        "currentStatus": "detached-summary-unsafe",
        "handling": "blocking",
        "message": "Thin report cards, screenshots, or forwarded imported summaries can detach the trust-bearing PBPK label from the caveats it needs.",
        "requiresHumanReview": true,
        "scope": "summary-surface",
        "severity": "high",
        "sourceSurface": "exportBlockPolicy"
      },
      {
        "cautionType": "decision-overclaim-risk",
        "code": "direct-regulatory-dose-derivation-blocked",
        "currentStatus": "not-supported",
        "handling": "blocking",
        "message": "Imported PBPK outputs should not be presented as direct regulatory dose derivations or final decision recommendations.",
        "requiresHumanReview": true,
        "scope": "workflow-claim",
        "severity": "high",
        "sourceSurface": "workflowClaimBoundaries"
      },
      {
        "cautionType": "decision-overclaim-risk",
        "code": "risk-assessment-ready-overclaim",
        "currentStatus": "research-use",
        "handling": "blocking",
        "message": "Imported qualification remains bounded, so decision-ready or regulatory-ready framing should stay blocked.",
        "requiresHumanReview": true,
        "scope": "workflow-claim",
        "severity": "high",
        "sourceSurface": "qualificationState"
      },
      {
        "cautionType": "parameter-transfer-uncertainty",
        "code": "parameter-transfer-uncertainty",
        "currentStatus": "in-vitro-adme-and-literature",
        "handling": "advisory",
        "message": "Parameterization depends on transferred, literature-derived, or default assumptions, so parameter-transfer uncertainty should be reviewed before stronger claims.",
        "requiresHumanReview": true,
        "scope": "model",
        "severity": "medium",
        "sourceSurface": "evidenceBasis"
      }
    ],
    "highestSeverity": "high",
    "requiresHumanReview": true,
    "summaryVersion": "pbpk-caution-summary.v1"
  },
  "checklistScore": null,
  "decisionBoundary": "no-ngra-decision-policy",
  "evidenceBasis": {
    "basisType": "external-imported",
    "inVivoSupportStatus": "no-direct-in-vivo-support",
    "iviveLinkageStatus": "external-ivive-linkage-declared",
    "parameterizationBasis": "in-vitro-adme-and-literature",
    "populationVariabilityStatus": "declared-or-characterized"
  },
  "evidenceStatus": "checked",
  "executableVerificationStatus": "checked",
  "exportBlockPolicy": {
    "blockReasons": [
      {
        "appliesTo": [
          "report-card",
          "screenshot",
          "chat-snippet",
          "forwarded-bundle",
          "thin-api-response"
        ],
        "code": "detached-summary-blocked",
        "currentStatus": "high",
        "message": "Block lossy report cards, screenshots, chat snippets, or forwarded bundles when qualification state, review status, evidence basis, claim boundaries, and anti-misread guidance cannot travel with them.",
        "requiredFields": [
          "qualificationState",
          "reviewStatus",
          "evidenceBasis",
          "claimBoundaries",
          "misreadRiskSummary.plainLanguageSummary",
          "summaryTransportRisk.plainLanguageSummary"
        ],
        "severity": "high"
      },
      {
        "appliesTo": [
          "regulatory-dose-claim",
          "regulatory-decision-summary",
          "decision-recommendation"
        ],
        "code": "direct-regulatory-dose-derivation-blocked",
        "currentStatus": "not-supported",
        "message": "Block downstream presentations that frame this PBPK output as a direct regulatory dose derivation or final decision recommendation.",
        "severity": "high"
      }
    ],
    "blockedViewModes": [
      "report-card",
      "screenshot",
      "chat-snippet",
      "forwarded-bundle",
      "thin-api-response"
    ],
    "contextualizedRenderOnly": true,
    "defaultAction": "block-lossy-or-decision-leaning-exports",
    "notes": [
      "This policy is descriptive and machine-readable so analyst-facing clients can refuse unsafe thin views.",
      "Imported or operator-reviewed state does not create regulatory decision authority inside PBPK MCP."
    ],
    "policyVersion": "pbpk-export-block-policy.v1",
    "requiredFields": [
      "qualificationState",
      "reviewStatus",
      "evidenceBasis",
      "claimBoundaries",
      "misreadRiskSummary.plainLanguageSummary",
      "summaryTransportRisk.plainLanguageSummary"
    ],
    "workflow": "exposure-led-ngra"
  },
  "label": "Research Use",
  "limitations": [
    "Imported performance evidence is limited to runtime or internal supporting evidence."
  ],
  "missingEvidenceCount": 0,
  "objectId": "gastroplus-qualification-summary",
  "objectType": "pbpkQualificationSummary.v1",
  "oecdReadiness": "external-imported",
  "performanceEvidenceBoundary": "runtime-or-internal-evidence-only",
  "platformClass": "commercial",
  "profileSource": "external-import",
  "qualificationLevel": "L2",
  "requiredExternalInputs": [
    "higher-level NGRA decision policy or orchestrator outside PBPK MCP",
    "observed-vs-predicted, predictive-dataset, or external qualification evidence"
  ],
  "reviewStatus": {
    "declaredStatus": "unreported",
    "focusTopics": [],
    "priorUseCount": 0,
    "requiresReviewerAttention": true,
    "resolvedDissentCount": 0,
    "reviewRecordCount": 0,
    "revisionEntryCount": 0,
    "revisionStatus": null,
    "status": "not-declared",
    "summary": "No peer-review, reviewer stance, or prior-use workflow metadata are declared.",
    "unresolvedDissentCount": 0
  },
  "riskAssessmentReady": false,
  "scientificProfile": true,
  "simulationId": null,
  "sourcePlatform": "GastroPlus",
  "state": "research-use",
  "summary": "External PBPK qualification metadata were normalized without executing the upstream platform.",
  "supports": {
    "executableVerification": false,
    "externalBerHandoff": true,
    "externalImportNormalization": true,
    "manifestValidation": false,
    "nativeExecution": false,
    "oecdDossierExport": true,
    "preflightValidation": false,
    "regulatoryDecision": false,
    "typedNgraHandoff": true
  },
  "validationDecision": null,
  "validationReferences": [],
  "withinDeclaredContext": null,
  "workflowClaimBoundaries": {
    "directRegulatoryDoseDerivation": "not-supported",
    "exposureLedPrioritization": "supported-only-as-pbpk-substrate-with-external-orchestrator",
    "forwardDosimetry": "external-imported-not-executed-by-pbpk-mcp",
    "reverseDosimetry": "not-performed-directly-external-workflow-required"
  }
}
""",
    'pointOfDepartureReference.v1': r"""
{
  "assessmentBoundary": "external-pod-reference-only",
  "backend": "external-import",
  "basis": "true-dose-adjusted",
  "decisionBoundary": "pod-interpretation-and-ber-policy-owned-by-external-orchestrator",
  "decisionOwner": "external-orchestrator",
  "metric": "cmax",
  "objectId": "gastroplus-point-of-departure-reference",
  "objectType": "pointOfDepartureReference.v1",
  "podRef": "pod-001",
  "requiredExternalInputs": [
    "PoD interpretation and suitability assessment outside PBPK MCP",
    "BER calculation and decision policy outside PBPK MCP"
  ],
  "simulationId": null,
  "source": "httr-benchmark",
  "sourcePlatform": "GastroPlus",
  "status": "attached-external-reference",
  "summary": null,
  "supports": {
    "decisionRecommendation": false,
    "externalBerCalculation": false,
    "metricMetadataAttached": true,
    "trueDoseMetadataAttached": true,
    "typedReference": true
  },
  "trueDoseAdjustment": {
    "applied": true,
    "basis": "free-concentration",
    "summary": "Normalized to free concentration"
  },
  "trueDoseAdjustmentApplied": true,
  "unit": "uM",
  "value": null,
  "warnings": []
}
""",
    'uncertaintyHandoff.v1': r"""
{
  "assessmentBoundary": "pbpk-to-cross-domain-uncertainty-handoff-only",
  "backend": "external-import",
  "blockingReasons": [],
  "decisionBoundary": "cross-domain-uncertainty-synthesis-owned-by-external-orchestrator",
  "decisionOwner": "external-orchestrator",
  "internalExposureEstimateRef": "gastroplus-internal-exposure-estimate",
  "objectId": "gastroplus-uncertainty-handoff",
  "objectType": "uncertaintyHandoff.v1",
  "pbpkQualificationSummaryRef": "gastroplus-qualification-summary",
  "pointOfDepartureReferenceRef": "gastroplus-point-of-departure-reference",
  "requiredExternalInputs": [
    "cross-domain uncertainty synthesis outside PBPK MCP",
    "exposure-scenario uncertainty outside PBPK MCP",
    "PoD or NAM uncertainty outside PBPK MCP"
  ],
  "simulationId": null,
  "sourcePlatform": "GastroPlus",
  "status": "ready-for-cross-domain-uncertainty-synthesis",
  "supports": {
    "classifiedResidualUncertaintySummaryAttached": true,
    "classifiedVariabilitySummaryAttached": true,
    "crossDomainUncertaintySynthesis": false,
    "decisionRecommendation": false,
    "internalExposureContextAttached": true,
    "pbpkQualificationAttached": true,
    "pbpkUncertaintySummaryAttached": true,
    "pointOfDepartureReferenceAttached": true,
    "quantifiedPbpkResidualUncertainty": false,
    "quantifiedPbpkSensitivity": false,
    "quantifiedPbpkVariability": true,
    "residualUncertaintyTracked": true,
    "typedUncertaintySemanticsAttached": true,
    "uncertaintyRegisterReferenceAttached": true
  },
  "uncertaintyRegisterReferenceRef": "gastroplus-uncertainty-register-reference",
  "uncertaintySummaryRef": "gastroplus-uncertainty-summary"
}
""",
    'uncertaintyRegisterReference.v1': r"""
{
  "assessmentBoundary": "external-uncertainty-register-reference-only",
  "backend": "external-import",
  "decisionBoundary": "cross-domain-uncertainty-synthesis-owned-by-external-orchestrator",
  "decisionOwner": "external-orchestrator",
  "objectId": "gastroplus-uncertainty-register-reference",
  "objectType": "uncertaintyRegisterReference.v1",
  "owner": null,
  "registerRef": "unc-reg-001",
  "requiredExternalInputs": [
    "cross-domain uncertainty synthesis outside PBPK MCP"
  ],
  "scope": "tier-1-systemic",
  "simulationId": null,
  "source": "assessment-workbench",
  "sourcePlatform": "GastroPlus",
  "status": "attached-external-reference",
  "summary": null,
  "supports": {
    "crossDomainUncertaintySynthesis": false,
    "decisionRecommendation": false,
    "typedReference": true
  },
  "warnings": []
}
""",
    'uncertaintySummary.v1': r"""
{
  "assessmentBoundary": "pbpk-side-uncertainty-summary-only",
  "backend": "external-import",
  "bundleMetadata": null,
  "decisionBoundary": "no-ngra-decision-policy",
  "evidenceRowCount": 2,
  "evidenceSource": "external-import",
  "hasResidualUncertainty": true,
  "hasSensitivityAnalysis": false,
  "hasVariabilityApproach": false,
  "hasVariabilityPropagation": true,
  "issueCount": 0,
  "objectId": "gastroplus-uncertainty-summary",
  "objectType": "uncertaintySummary.v1",
  "requiredExternalInputs": [
    "cross-domain uncertainty synthesis outside PBPK MCP"
  ],
  "residualUncertaintyStatus": "declared",
  "semanticCoverage": {
    "declaredOnlyComponents": [
      "residual-uncertainty"
    ],
    "declaredOnlyRowCount": 1,
    "overallQuantificationStatus": "partially-quantified",
    "quantifiedComponents": [
      "variability"
    ],
    "quantifiedRowCount": 1,
    "residualUncertaintyQuantificationStatus": "declared-only",
    "residualUncertaintyType": "declared-residual-uncertainty",
    "sensitivityQuantificationStatus": "unreported",
    "sensitivityType": "unreported",
    "variabilityQuantificationStatus": "quantified",
    "variabilityType": "aleatoric-or-population-variability"
  },
  "sensitivityStatus": "not-bundled",
  "simulationId": null,
  "sourcePlatform": "GastroPlus",
  "sources": [],
  "status": "declared",
  "summary": "Imported uncertainty summary",
  "supports": {
    "classifiedResidualUncertainty": true,
    "classifiedVariability": true,
    "crossDomainUncertaintyRegister": false,
    "decisionRecommendation": false,
    "qualitativeSummary": true,
    "quantifiedResidualUncertainty": false,
    "quantifiedSensitivity": false,
    "quantifiedVariability": true,
    "quantitativePropagation": true,
    "residualUncertaintyTracking": true,
    "sensitivityAnalysis": false,
    "typedNgraHandoff": true,
    "typedUncertaintySemantics": true,
    "variabilityCharacterization": false
  },
  "totalEvidenceRows": 2,
  "variabilityStatus": "propagated"
}
""",
}

def capability_matrix_document() -> dict[str, object]:
    return json.loads(_CAPABILITY_MATRIX_JSON)

def contract_manifest_document() -> dict[str, object]:
    return json.loads(_CONTRACT_MANIFEST_JSON)

def release_bundle_manifest_document() -> dict[str, object]:
    return json.loads(_RELEASE_BUNDLE_MANIFEST_JSON)

def schema_documents() -> dict[str, dict]:
    return {key: json.loads(value) for key, value in _SCHEMA_JSON.items()}

def schema_examples() -> dict[str, dict]:
    return {key: json.loads(value) for key, value in _SCHEMA_EXAMPLE_JSON.items()}
