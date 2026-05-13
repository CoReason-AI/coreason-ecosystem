# Changelog

## [0.11.1](https://github.com/CoReason-AI/coreason-ecosystem/compare/v0.11.0...v0.11.1) (2026-05-13)


### Features

* add CI workflow to automate documentation deployment and packag… ([64991ee](https://github.com/CoReason-AI/coreason-ecosystem/commit/64991ee19eebf468097c2318b24aaceae04477dc))
* add CI workflow to automate documentation deployment and package publishing ([4490a95](https://github.com/CoReason-AI/coreason-ecosystem/commit/4490a95d36085e55b2d779854df6159dacdfb42e))
* formalize Neurosymbolic Caging Protocol and Epistemic Quarantine directives across agent configuration rules ([603912c](https://github.com/CoReason-AI/coreason-ecosystem/commit/603912c7ed49b20b1b18a535948af9d4fe50a602))
* **governance:** provision thermodynamic boundaries for chaos mesh via RBAC and deployment scripts ([90053a2](https://github.com/CoReason-AI/coreason-ecosystem/commit/90053a2a280fa487d1a23f01b94208605ec4d315))
* implement fleet scaling infrastructure including Skypilot actuator, expansion loop, and mesh injector with aiohttp support. ([26618a1](https://github.com/CoReason-AI/coreason-ecosystem/commit/26618a12e5b0084bfbb10def0a07191c7ef356da))
* implement master MCP gateway and establish comprehensive test suite ([26a5f58](https://github.com/CoReason-AI/coreason-ecosystem/commit/26a5f58714b7ae98e690945167542b2bc5d5d360))
* implement master MCP gateway for federated actuator discovery and execution with comprehensive test suite ([30562be](https://github.com/CoReason-AI/coreason-ecosystem/commit/30562be9b54c5acb39a9374ff8807168d1fa69d5))
* implement MCP gateway module and semantic router with arrow support ([60a39a4](https://github.com/CoReason-AI/coreason-ecosystem/commit/60a39a4a6b0792e4f9b223a231d05bd0dd12e29c))
* implement SemanticRouter and add ML-related dependencies to support intent-based routing ([2fda4ba](https://github.com/CoReason-AI/coreason-ecosystem/commit/2fda4ba4fa5aa9e202024ea14f2d93b8927744ec))
* implement Von Neumann expansion loop, Sovereign MCP registry, and master MCP orchestration modules. ([0632087](https://github.com/CoReason-AI/coreason-ecosystem/commit/063208783eb4b227dda8c4534fbf123d5a5639fd))
* remove deprecated proprietary chaos components ([#133](https://github.com/CoReason-AI/coreason-ecosystem/issues/133)) ([64d4b4e](https://github.com/CoReason-AI/coreason-ecosystem/commit/64d4b4ebc34b71857c8ae50dca4c803e76970eca))
* remove deprecated proprietary chaos components ([#133](https://github.com/CoReason-AI/coreason-ecosystem/issues/133)) ([2f5f2f9](https://github.com/CoReason-AI/coreason-ecosystem/commit/2f5f2f90f68545d5d75cc011ab2beaf016ed40b5))


### Bug Fixes

* add mypy type annotations and fix ruff lint in coverage tests ([36ae316](https://github.com/CoReason-AI/coreason-ecosystem/commit/36ae3166db8b431fe75a035a535944885094865b))
* **ci:** formatting fixes for remaining test files ([b71e876](https://github.com/CoReason-AI/coreason-ecosystem/commit/b71e87629b696a1acb13512e71b7e17e6f5b2063))
* **ci:** resolve deptry and mypy failures in lint-and-audit pipeline ([1da3d25](https://github.com/CoReason-AI/coreason-ecosystem/commit/1da3d25637df3614fbb37b721cc8fb02d73269db))
* **ci:** ruff format to resolve pre-commit failure ([350a9d0](https://github.com/CoReason-AI/coreason-ecosystem/commit/350a9d0a41878cd8af64ef5736ab8c257acec088))
* **ci:** sync release-please manifest version to v0.11.0 ([f76efc9](https://github.com/CoReason-AI/coreason-ecosystem/commit/f76efc95da5c9ed564570224e429f10d8b8ef9a1))
* **ci:** sync release-please manifest version to v0.11.0 ([b5e4e4c](https://github.com/CoReason-AI/coreason-ecosystem/commit/b5e4e4cbb15e1f7e72c64cf30ca6a2c25767cbea))
* **deps:** remove unused prometheus-client and networkx from pyproject ([67795df](https://github.com/CoReason-AI/coreason-ecosystem/commit/67795df40e96296c09140d53ddbadf316909e5c2))
* **fleet:** resolve formatting, whitespace, and Bandit B110 security issue in SkyPilotActuator ([ecf4df0](https://github.com/CoReason-AI/coreason-ecosystem/commit/ecf4df09dbdcb31c703628a7476776a3371dd7e8))
* resolve linting, typing, and security errors in ecosystem ([6337321](https://github.com/CoReason-AI/coreason-ecosystem/commit/63373217851d94ec71db2a60c98c14871f192050))
* Resolve missing mock unused variables ([a1a41cb](https://github.com/CoReason-AI/coreason-ecosystem/commit/a1a41cb3fc2a96bf2bebf85c8b7bf86225830f37))
* Resolve mypy typing issues in tests and master_mcp.py ([f61cc6a](https://github.com/CoReason-AI/coreason-ecosystem/commit/f61cc6a6591d664700ddeae33fa0cb799583f159))
* Resolve pre-commit (whitespace and ruff-format) failures in ecosystem. ([9eb02eb](https://github.com/CoReason-AI/coreason-ecosystem/commit/9eb02eb4eec907a7f21679749bc838f23ecaa7d0))
* **security:** ignore B501 on intentional internal mTLS without verify ([9049e0b](https://github.com/CoReason-AI/coreason-ecosystem/commit/9049e0b1fc25409332d6415668d5901e62d387dc))


### Refactoring

* Finalize Proxy-First amputation by hollowing gateway filtering and substrate resolution. ([b872df1](https://github.com/CoReason-AI/coreason-ecosystem/commit/b872df17c4f1380e02333854e5318a74eebe2275))
* fully delegate OpenShell mTLS and security bounds to sidecar proxy in master_mcp.py ([ddf9e70](https://github.com/CoReason-AI/coreason-ecosystem/commit/ddf9e70919680c51df55775ae37a303e661e2253))
* Just-in-Time Cognition via NemoClaw ([#120](https://github.com/CoReason-AI/coreason-ecosystem/issues/120)) ([99fc088](https://github.com/CoReason-AI/coreason-ecosystem/commit/99fc0883d0f2e932a8d887eef576ba9c0bc6ea37))
* simplify identity logic and remove custom RBAC layer ([#118](https://github.com/CoReason-AI/coreason-ecosystem/issues/118)) ([#119](https://github.com/CoReason-AI/coreason-ecosystem/issues/119)) ([b11a900](https://github.com/CoReason-AI/coreason-ecosystem/commit/b11a90024d03969f4c6f4c48f84b7fc6af8bbc19))


### Tests

* add comprehensive test suite for orchestration, gateway, fleet, and utility modules ([73d12a3](https://github.com/CoReason-AI/coreason-ecosystem/commit/73d12a37a69c52c6e243ea75f7f75c9d8898e904))
* add comprehensive unit and integration test suite for CLI, fleet daemon, and expansion logic ([25aa4b9](https://github.com/CoReason-AI/coreason-ecosystem/commit/25aa4b94cd823e5ee6e7f01f67776fad0d79d49e))
* add comprehensive unit tests and scratch scripts for gateway master MCP integration ([e3f6c15](https://github.com/CoReason-AI/coreason-ecosystem/commit/e3f6c157deec623df94e109afabb8083b1611114))
* add unit and fleet coverage for semantic router error handling and daemon reconciliation logic ([f545271](https://github.com/CoReason-AI/coreason-ecosystem/commit/f545271f51aebd42c7519496c661615ee66ce415))
* **ecosystem:** fix mypy errors in SkyPilotActuator tests ([2f7bcf2](https://github.com/CoReason-AI/coreason-ecosystem/commit/2f7bcf2b31a8775120c4e7e728e79f7e6e9f4280))
* expand coverage for semantic router to 98% ([1d31c43](https://github.com/CoReason-AI/coreason-ecosystem/commit/1d31c43b03ee3335485c2c071c26a486fec75623))
* **fleet:** add unit tests for SkyPilotActuator to ensure 100% coverage ([67f3acf](https://github.com/CoReason-AI/coreason-ecosystem/commit/67f3acf0f330dffa603c7324860187f2e25f9441))
