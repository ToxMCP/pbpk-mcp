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
    "supporting": 9
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
    "schemaCatalog": "/mcp/resources/schemas"
  },
  "schemas": [
    {
      "classification": "normative",
      "exampleRelativePath": "schemas/examples/assessmentContext.v1.example.json",
      "exampleSha256": "316fe3e7b69b1f27ade102c10444540e50fca61725c95b369c4bd48dd52b4fa6",
      "relativePath": "schemas/assessmentContext.v1.json",
      "schemaId": "assessmentContext.v1",
      "sha256": "e8b4ba287879f7fddc7139c666e057256efa0190e7263721e8685c9331bb5940"
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
      "exampleSha256": "2305d9887725aac70de57e2893599aa4446ea0e81013da1f80ecf344a50c04da",
      "relativePath": "schemas/pbpkQualificationSummary.v1.json",
      "schemaId": "pbpkQualificationSummary.v1",
      "sha256": "515b371dad39d241a97384a4627eca529636ea5e6378da1f01be8688d08da08d"
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
      "relativePath": "docs/architecture/capability_matrix.md",
      "role": "human-readable capability guide",
      "sha256": "668e616af45a6a1ff89cbda523264ffbc087a79dadfb64c7e3d0e2e56c72f14c"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/architecture/mcp_payload_conventions.md",
      "role": "payload contract reference",
      "sha256": "051b8800193809b7a012a0ec57fd4f5a310c52758c671b377895b12f96d00f8e"
    },
    {
      "classification": "supporting",
      "relativePath": "docs/github_publication_checklist.md",
      "role": "publication checklist",
      "sha256": "b00bf8aea5469aeb0dc9cc3ccc4e26bbcfe3c3019eb539fbb836bd6f0d8690b6"
    },
    {
      "classification": "supporting",
      "relativePath": "schemas/README.md",
      "role": "schema usage guide",
      "sha256": "0eb43956df6b769bbf3028e0b8b1f2997db397e7618eb1be0d98b7a48847c80a"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/check_distribution_artifacts.py",
      "role": "distribution artifact validation script",
      "sha256": "f71f779112302dc1b0bc6d0aa83fed81bf9ca11fefdfba5782eabc736198e6da"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/check_release_metadata.py",
      "role": "release metadata consistency check",
      "sha256": "a5c81528c34952d7a51fb32970ac18bc6bc2703a40b4e16db9f669e9b92eecac"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/check_installed_package_contract.py",
      "role": "installed package contract validation script",
      "sha256": "e961342d40a42ea074f5735671da5f030066db4bd28b4763d6661f6c371a365a"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/check_runtime_contract_env.py",
      "role": "contract dependency preflight script",
      "sha256": "82cbd13b4c7c4fef29b06cac4d9552f7db236985c1e7c348391e7f929b35d9a0"
    },
    {
      "classification": "supporting",
      "relativePath": "scripts/generate_contract_artifacts.py",
      "role": "contract artifact generator",
      "sha256": "02429aee7d348e7b63a99ad1f707ebc1d43fbcd2511283ab5f97e97737d95123"
    }
  ]
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
    "checklistScore": {
      "type": [
        "number",
        "null"
      ]
    },
    "decisionBoundary": {
      "const": "no-ngra-decision-policy"
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
  "validationDecision": null
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
  "checklistScore": null,
  "decisionBoundary": "no-ngra-decision-policy",
  "evidenceStatus": "checked",
  "executableVerificationStatus": "checked",
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
  "withinDeclaredContext": null
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

def schema_documents() -> dict[str, dict]:
    return {key: json.loads(value) for key, value in _SCHEMA_JSON.items()}

def schema_examples() -> dict[str, dict]:
    return {key: json.loads(value) for key, value in _SCHEMA_EXAMPLE_JSON.items()}
