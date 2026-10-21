# Changelog

All notable changes to this project will be documented in this file.

## [0.10.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.9.0...v0.10.0) (2026-10-21)


### Features

* diagnose names the likely cause of a failed setup or test run, compared with what CI sets up ([#104](https://github.com/anandkaranubc/git-into-gsoc/issues/104)) ([9fe3257](https://github.com/anandkaranubc/git-into-gsoc/commit/9fe3257681e7f82f97fbfda65db6fb90d7eacd0d))
* **draft:** check a message you wrote against the rules for its kind before you post it ([#98](https://github.com/anandkaranubc/git-into-gsoc/issues/98)) ([07b2a8c](https://github.com/anandkaranubc/git-into-gsoc/commit/07b2a8cfb6e0db3de2a0ddd44ae13e98eae612cd))
* pr-check applies the repository's own rules to your pull request before review ([#96](https://github.com/anandkaranubc/git-into-gsoc/issues/96)) ([a52d6fa](https://github.com/anandkaranubc/git-into-gsoc/commit/a52d6fad3c0ec8031f10ff64ea0b8cfdd35b3729))
* **progress:** show progress as a readable checklist instead of raw JSON ([#109](https://github.com/anandkaranubc/git-into-gsoc/issues/109)) ([7846b16](https://github.com/anandkaranubc/git-into-gsoc/commit/7846b1678a28258714bf0069f8106c8b9b4eaf39))
* **repo:** count closed outside pull requests that a maintainer committed another way ([#87](https://github.com/anandkaranubc/git-into-gsoc/issues/87)) ([f93a6d4](https://github.com/anandkaranubc/git-into-gsoc/commit/f93a6d400419f0d93daa63023d8f3aa753cbebe4))


### Bug Fixes

* **cache:** delete old entries and cap the HTTP cache size ([#93](https://github.com/anandkaranubc/git-into-gsoc/issues/93)) ([82a85e4](https://github.com/anandkaranubc/git-into-gsoc/commit/82a85e4ba08bc0b07dd76c0f3fcbf5abfe9d4c6b))
* **cli:** survive legacy Windows encodings in output and in draft files ([#97](https://github.com/anandkaranubc/git-into-gsoc/issues/97)) ([e2e7b9d](https://github.com/anandkaranubc/git-into-gsoc/commit/e2e7b9d91a5e7543ee9e457a823e649254abaafe))
* **config:** a .env in the current folder cannot redirect requests or data ([#103](https://github.com/anandkaranubc/git-into-gsoc/issues/103)) ([a01df72](https://github.com/anandkaranubc/git-into-gsoc/commit/a01df72892c89fcc898a3ea8a2889f735ee80601))
* **draft:** read --check messages saved as UTF-16, cp1252, or with a byte-order mark ([#106](https://github.com/anandkaranubc/git-into-gsoc/issues/106)) ([ec71814](https://github.com/anandkaranubc/git-into-gsoc/commit/ec718145c11869377d9aa18bf20db0d8965545e7))
* **http:** never fetch local or private network addresses ([#89](https://github.com/anandkaranubc/git-into-gsoc/issues/89)) ([941aca3](https://github.com/anandkaranubc/git-into-gsoc/commit/941aca30985c591fb848bff2e5d4107a3d41c019))
* **http:** stop reading a response past 64 MB, counted after decompression ([#108](https://github.com/anandkaranubc/git-into-gsoc/issues/108)) ([cef96f8](https://github.com/anandkaranubc/git-into-gsoc/commit/cef96f80bcabd65a05902a6714d81cc5d0cbb35c))
* **install:** use PyPI only for a release this repository published ([#101](https://github.com/anandkaranubc/git-into-gsoc/issues/101)) ([c0209d7](https://github.com/anandkaranubc/git-into-gsoc/commit/c0209d7af4b1a6670307b8af504a914177eb435e))
* **mcp:** exact write hints, guarded weekly note, validated progress input ([#88](https://github.com/anandkaranubc/git-into-gsoc/issues/88)) ([95a2ddc](https://github.com/anandkaranubc/git-into-gsoc/commit/95a2ddcc05e330d6df068b1e50ff0f4aecabef47))
* never run gh or an assistant's command from the current folder ([#105](https://github.com/anandkaranubc/git-into-gsoc/issues/105)) ([d6f154a](https://github.com/anandkaranubc/git-into-gsoc/commit/d6f154a667d56ca12384cfe3071491f3c1e7a5fe))
* **progress:** wait out Windows sharing violations and never reset an unreadable file ([#107](https://github.com/anandkaranubc/git-into-gsoc/issues/107)) ([2f37ab7](https://github.com/anandkaranubc/git-into-gsoc/commit/2f37ab7a07d818b5810e0d20208c3f9f4f197d77))
* **repos:** find repositories for umbrellas that list no GitHub organization ([#99](https://github.com/anandkaranubc/git-into-gsoc/issues/99)) ([538ea53](https://github.com/anandkaranubc/git-into-gsoc/commit/538ea53437370e7f9e551f8c114d5f3492cffb2c))
* **setup:** read configs with a byte-order mark, explain ones with comments, write atomically ([#95](https://github.com/anandkaranubc/git-into-gsoc/issues/95)) ([a7c8657](https://github.com/anandkaranubc/git-into-gsoc/commit/a7c865703035b97b2364a74940fa2a21c96125bf))
* **snapshot:** make an unchanged refresh byte-identical ([#111](https://github.com/anandkaranubc/git-into-gsoc/issues/111)) ([2031f31](https://github.com/anandkaranubc/git-into-gsoc/commit/2031f31b5a76d355f29f2be4d013c4c77ac4a21b))
* strip hidden and terminal-control characters from all output ([#92](https://github.com/anandkaranubc/git-into-gsoc/issues/92)) ([43ea10c](https://github.com/anandkaranubc/git-into-gsoc/commit/43ea10ce8e90309d8884bc4b344247c588bc6a21))


### Performance Improvements

* **archive:** fetch archive years side by side and cache them for a week ([#100](https://github.com/anandkaranubc/git-into-gsoc/issues/100)) ([e24f299](https://github.com/anandkaranubc/git-into-gsoc/commit/e24f2996a292c6a734f4c34f06f2dfbfd3736dcb))


### Documentation

* a final beginner pass over every user-facing file ([#94](https://github.com/anandkaranubc/git-into-gsoc/issues/94)) ([1364d71](https://github.com/anandkaranubc/git-into-gsoc/commit/1364d712e1b6aeb77e14f93c173be0137235f857))
* **research:** full-README scan of the low-signal census repositories and two more rejected ideas ([#91](https://github.com/anandkaranubc/git-into-gsoc/issues/91)) ([47d6c59](https://github.com/anandkaranubc/git-into-gsoc/commit/47d6c59a0fc7d5e9b2bfc5524bcfca432cb7037d))

## [0.9.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.8.0...v0.9.0) (2026-10-21)


### Features

* **next:** show which open pull requests need you and which are waiting ([#82](https://github.com/anandkaranubc/git-into-gsoc/issues/82)) ([9fc46cf](https://github.com/anandkaranubc/git-into-gsoc/commit/9fc46cf60d9e444281f328f774e187b18f66c279))
* say how long a linked pull request has been idle, and report when a repository expects a changelog entry ([#83](https://github.com/anandkaranubc/git-into-gsoc/issues/83)) ([06b196a](https://github.com/anandkaranubc/git-into-gsoc/commit/06b196ab68a1818d508fbc99c947cf84b40ad813))


### Bug Fixes

* **mcp:** keep HTTP request lines out of the assistant's MCP log ([#84](https://github.com/anandkaranubc/git-into-gsoc/issues/84)) ([fc11860](https://github.com/anandkaranubc/git-into-gsoc/commit/fc118609ddcb36980a9ab306d33a10b7e2f4188b))
* **progress:** atomic, locked saves and recovery from a damaged progress file ([#86](https://github.com/anandkaranubc/git-into-gsoc/issues/86)) ([2cfca8a](https://github.com/anandkaranubc/git-into-gsoc/commit/2cfca8a9b276fbc32b5ea05c2eb7739135f6d71e))
* robustness from offline and odd-input probes ([#81](https://github.com/anandkaranubc/git-into-gsoc/issues/81)) ([9b995ca](https://github.com/anandkaranubc/git-into-gsoc/commit/9b995ca24342eb5b1f74e1ed41b365cfbc0a358b))

## [0.8.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.7.0...v0.8.0) (2026-10-21)


### Features

* **orient:** show the runtime versions, services and systems CI sets up ([#78](https://github.com/anandkaranubc/git-into-gsoc/issues/78)) ([3381f04](https://github.com/anandkaranubc/git-into-gsoc/commit/3381f04c0a3722e9763091bd2aa5234b20c145a6))


### Bug Fixes

* **cli:** render untrusted text literally and let contributions use the saved profile ([#79](https://github.com/anandkaranubc/git-into-gsoc/issues/79)) ([f889c90](https://github.com/anandkaranubc/git-into-gsoc/commit/f889c9031274ff287ab49e29d29b905c8aa90830))

## [0.7.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.6.1...v0.7.0) (2026-10-21)


### Features

* **issues:** point to an earlier closed pull request as a guide, and let stricter organization rules govern; code-search census ([#76](https://github.com/anandkaranubc/git-into-gsoc/issues/76)) ([218c692](https://github.com/anandkaranubc/git-into-gsoc/commit/218c692345520f5756317a07c09ab472a38dcd4e))
* **orient:** list the gates GitHub enforces but CONTRIBUTING leaves out, from branch rules and gate workflows ([#71](https://github.com/anandkaranubc/git-into-gsoc/issues/71)) ([9cd9809](https://github.com/anandkaranubc/git-into-gsoc/commit/9cd9809d074fafb5da22ec45dc67ccc623cbcb9f))


### Bug Fixes

* **site:** show all ten journey phases and the real issue output ([#75](https://github.com/anandkaranubc/git-into-gsoc/issues/75)) ([3f288c5](https://github.com/anandkaranubc/git-into-gsoc/commit/3f288c5b3911e870b2960b34401933027ecd7ad6))


### Documentation

* keep research working notes and the audit record out of the public docs ([#70](https://github.com/anandkaranubc/git-into-gsoc/issues/70)) ([b353e9d](https://github.com/anandkaranubc/git-into-gsoc/commit/b353e9dd21d3af4ce63a1d213a60a3fb42521766))
* list ideas and mentors in the command table and count ten phases everywhere ([#77](https://github.com/anandkaranubc/git-into-gsoc/issues/77)) ([f0f16e2](https://github.com/anandkaranubc/git-into-gsoc/commit/f0f16e274252f54967bec433b1033935e9b0821e))

## [0.6.1](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.6.0...v0.6.1) (2026-10-21)


### Documentation

* **research:** open all 292 census repositories, resolve every link in the notes, and fix the one stale link ([#67](https://github.com/anandkaranubc/git-into-gsoc/issues/67)) ([e27b292](https://github.com/anandkaranubc/git-into-gsoc/commit/e27b29218422c51e3aa886d69d659e332ae77d54))

## [0.6.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.5.1...v0.6.0) (2026-10-21)


### Features

* **setup:** add --remove to delete skill copies and MCP registrations ([#64](https://github.com/anandkaranubc/git-into-gsoc/issues/64)) ([d3012fa](https://github.com/anandkaranubc/git-into-gsoc/commit/d3012fa33011a3fe0e00a0ab4478b1a4b418ed9c))


### Bug Fixes

* **issues:** count reservation words inside labels and fall back to any beginner spelling; first-hand label census and verified sources ([#63](https://github.com/anandkaranubc/git-into-gsoc/issues/63)) ([5709bb1](https://github.com/anandkaranubc/git-into-gsoc/commit/5709bb129ed14db4812058f8bc87590c1fe22ab1))


### Documentation

* **research:** census appendix with a verdict for all 292 repositories and a verification-status header on every note ([#66](https://github.com/anandkaranubc/git-into-gsoc/issues/66)) ([3bddc6b](https://github.com/anandkaranubc/git-into-gsoc/commit/3bddc6b663c7138368da4710a65a0818a5a14afa))

## [0.5.1](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.5.0...v0.5.1) (2026-10-21)


### Bug Fixes

* **ideas:** read pages without a closed head, underlined and styled-div headings, and labels outside the vocabulary; census of all 183 ideas pages ([#60](https://github.com/anandkaranubc/git-into-gsoc/issues/60)) ([0c1a02a](https://github.com/anandkaranubc/git-into-gsoc/commit/0c1a02a4f3ce753f739abe3db68eabf03d8126e0))
* keep org profiles working offline, widen the reply window, and close the consistency sweep ([#61](https://github.com/anandkaranubc/git-into-gsoc/issues/61)) ([3f14439](https://github.com/anandkaranubc/git-into-gsoc/commit/3f14439fa0ff5dc1308b5e606fd49180636e1b4c))


### Documentation

* add the consistency-sweep findings to the audit record ([#62](https://github.com/anandkaranubc/git-into-gsoc/issues/62)) ([840b937](https://github.com/anandkaranubc/git-into-gsoc/commit/840b937e5fc6fb294da3996c0e88b19ec1d112d4))
* record the October 2026 audit findings and their resolutions ([#58](https://github.com/anandkaranubc/git-into-gsoc/issues/58)) ([1e4a75d](https://github.com/anandkaranubc/git-into-gsoc/commit/1e4a75da31a8bb5cfd442586133b5694ad4cce30))

## [0.5.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.4.0...v0.5.0) (2026-10-21)


### Features

* **github:** measure first human reply on the REST path from recent repository comments ([#56](https://github.com/anandkaranubc/git-into-gsoc/issues/56)) ([f804536](https://github.com/anandkaranubc/git-into-gsoc/commit/f804536db4191a2fe07e5092b870847d13a602b5))
* **github:** read the insider set from the public assignees endpoint without a token ([#54](https://github.com/anandkaranubc/git-into-gsoc/issues/54)) ([6fa7694](https://github.com/anandkaranubc/git-into-gsoc/commit/6fa7694ed8236a2c9c0f0ad3eae99732a49d160a))
* time budget, umbrella projects in repos, maintainer and reserved-label issue signals, PR setup commands, and elicitation ([#57](https://github.com/anandkaranubc/git-into-gsoc/issues/57)) ([d76225f](https://github.com/anandkaranubc/git-into-gsoc/commit/d76225f4b1a90c35ef5b4c1a19cb2bce1f6666fe))

## [0.4.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.3.1...v0.4.0) (2026-10-21)


### Features

* **ideas:** follow link-only umbrella pages, ignore links when reading AI policy, and link year-sorted proposal archives ([#50](https://github.com/anandkaranubc/git-into-gsoc/issues/50)) ([b19947d](https://github.com/anandkaranubc/git-into-gsoc/commit/b19947d899093d6b7e2a5c338e061c0d9947f5e4))


### Documentation

* **guide:** list the plugin, extension, and registry ways to connect an assistant ([#51](https://github.com/anandkaranubc/git-into-gsoc/issues/51)) ([b24c844](https://github.com/anandkaranubc/git-into-gsoc/commit/b24c8441cf94b0cb73d064133f783eb0412efe80))

## [0.3.1](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.3.0...v0.3.1) (2026-10-21)


### Bug Fixes

* **ci:** never replace a published MCPB bundle and build it reproducibly ([#47](https://github.com/anandkaranubc/git-into-gsoc/issues/47)) ([8862b75](https://github.com/anandkaranubc/git-into-gsoc/commit/8862b7567398b1ce25a9e1a0a6929adc1d2699d9))
* **http:** name the GitHub search limit and its remedy when a search is rate limited ([#48](https://github.com/anandkaranubc/git-into-gsoc/issues/48)) ([9f4ba79](https://github.com/anandkaranubc/git-into-gsoc/commit/9f4ba7963330d73db95ed96ab345cf5f61f7961d))

## [0.3.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.2.1...v0.3.0) (2026-10-21)


### Features

* **cli:** group the help by journey step and probe each data source in doctor ([#45](https://github.com/anandkaranubc/git-into-gsoc/issues/45)) ([b8178f0](https://github.com/anandkaranubc/git-into-gsoc/commit/b8178f05f80a69b861742497f4c8598abdf69e44))

## [0.2.1](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.2.0...v0.2.1) (2026-10-21)


### Bug Fixes

* **ci:** registry description under 100 characters and bundle built from the tagged source ([#40](https://github.com/anandkaranubc/git-into-gsoc/issues/40)) ([a78ce62](https://github.com/anandkaranubc/git-into-gsoc/commit/a78ce6250a245549b61a6a12d96a048c1e01c2a4))
* honour the configured target year everywhere and keep local data private ([#43](https://github.com/anandkaranubc/git-into-gsoc/issues/43)) ([0c3ad09](https://github.com/anandkaranubc/git-into-gsoc/commit/0c3ad091631b576725759444f12eb7bf313a8156))


### Documentation

* **research:** replace comma-for-dash artifacts with readable punctuation ([#39](https://github.com/anandkaranubc/git-into-gsoc/issues/39)) ([78cbbed](https://github.com/anandkaranubc/git-into-gsoc/commit/78cbbed7187848368290fa3d42749441966c7aff))
* walk beginners through the journey coach and evidence commands ([#41](https://github.com/anandkaranubc/git-into-gsoc/issues/41)) ([4f3ee45](https://github.com/anandkaranubc/git-into-gsoc/commit/4f3ee456de2bc7d87765d0fe944a133fb9a8e0e6))

## [0.2.0](https://github.com/anandkaranubc/git-into-gsoc/compare/v0.1.0...v0.2.0) (2026-10-21)


### Features

* a visual identity for git-into-gsoc (logo, typeface, site, brand kit) ([#20](https://github.com/anandkaranubc/git-into-gsoc/issues/20)) ([4febb5b](https://github.com/anandkaranubc/git-into-gsoc/commit/4febb5bf33b0ce0142fc7a1da064fcb164fe8295))
* add GSoC and GitHub intelligence core library ([8011eb5](https://github.com/anandkaranubc/git-into-gsoc/commit/8011eb597775b6e19644a4206517130603ed90db))
* add orient and iterate phases to the contributor journey ([#34](https://github.com/anandkaranubc/git-into-gsoc/issues/34)) ([d7013f6](https://github.com/anandkaranubc/git-into-gsoc/commit/d7013f695f072b8e1f1cd33bba1720d517a58cfc))
* add portable Agent Skill and one-shot installer ([3c20558](https://github.com/anandkaranubc/git-into-gsoc/commit/3c20558937359698925d56758c6392e97b9a987f))
* add Typer CLI and MCP server ([e9ce08c](https://github.com/anandkaranubc/git-into-gsoc/commit/e9ce08c2a0bac42d9cf1b9df14d69d6d8b9594ad))
* check draft proposals against what organizations reject on ([#21](https://github.com/anandkaranubc/git-into-gsoc/issues/21)) ([530dab5](https://github.com/anandkaranubc/git-into-gsoc/commit/530dab55213d0867c1ac13b9d9a879acd4de4381))
* CodeTour export, repository-specific beginner labels, past-proposal links, and the full research notes ([#37](https://github.com/anandkaranubc/git-into-gsoc/issues/37)) ([55eb68f](https://github.com/anandkaranubc/git-into-gsoc/commit/55eb68f428a6406cc5a89c47e86ea21eeea73c02))
* count newcomers who landed commits using token-free ecosyste.ms data ([#33](https://github.com/anandkaranubc/git-into-gsoc/issues/33)) ([9d3b38d](https://github.com/anandkaranubc/git-into-gsoc/commit/9d3b38d7c97d6a64691900e03523ce80ee88b03e))
* ecosystem intelligence: profile, next, log, contributions, ideas, orient, pointers, draft, and MCP prompts ([#27](https://github.com/anandkaranubc/git-into-gsoc/issues/27)) ([66b758e](https://github.com/anandkaranubc/git-into-gsoc/commit/66b758e3f3b114bfbb1d7200f584d0f3e55218ad))
* evidence-based issue availability scoped to GSoC orgs ([#10](https://github.com/anandkaranubc/git-into-gsoc/issues/10)) ([3991eda](https://github.com/anandkaranubc/git-into-gsoc/commit/3991eda4b7337762b8b00c235efc27e4bb2556f1))
* harden HTTP layer, token discovery, and input validation ([#7](https://github.com/anandkaranubc/git-into-gsoc/issues/7)) ([f667a84](https://github.com/anandkaranubc/git-into-gsoc/commit/f667a84c27ab36dbfbe9ac0e500b28a00494553b))
* live official GSoC timelines with phase-aware guidance ([#8](https://github.com/anandkaranubc/git-into-gsoc/issues/8)) ([a6206f9](https://github.com/anandkaranubc/git-into-gsoc/commit/a6206f937a5928964246501bb6536c52ac9fc127))
* **mcp:** title every tool and report expected failures as tool errors ([#26](https://github.com/anandkaranubc/git-into-gsoc/issues/26)) ([ddfd96f](https://github.com/anandkaranubc/git-into-gsoc/commit/ddfd96f016115491b4970e4610980fd349efed68))
* measure first human reply and real insiders over GraphQL when a token exists ([#29](https://github.com/anandkaranubc/git-into-gsoc/issues/29)) ([f5f2bbd](https://github.com/anandkaranubc/git-into-gsoc/commit/f5f2bbd604fad3363d90c5d57886afc33014e85f))
* mentors from the official archive, claim-bot aware availability, advanced-search-safe queries, and plugin manifests ([#31](https://github.com/anandkaranubc/git-into-gsoc/issues/31)) ([525e6bd](https://github.com/anandkaranubc/git-into-gsoc/commit/525e6bdbf595d920928d8f104cda7bd9eff77d76))
* official org intelligence with precise matching and past projects ([#9](https://github.com/anandkaranubc/git-into-gsoc/issues/9)) ([ec1ac3a](https://github.com/anandkaranubc/git-into-gsoc/commit/ec1ac3aed85ec47df393f023685c536be48b02e8))
* one-command install with a cross-platform setup that wires every assistant ([#14](https://github.com/anandkaranubc/git-into-gsoc/issues/14)) ([0c9ceac](https://github.com/anandkaranubc/git-into-gsoc/commit/0c9ceac61ceb559c7eea92ee651ea76e07f4ffac))
* rank an org's repos and grade them on newcomer merge evidence ([#11](https://github.com/anandkaranubc/git-into-gsoc/issues/11)) ([3aa188e](https://github.com/anandkaranubc/git-into-gsoc/commit/3aa188e21460c707fb35c2be733a9f70f50b085a))
* run the plugin's MCP server from the repository today, and record checked research findings ([#35](https://github.com/anandkaranubc/git-into-gsoc/issues/35)) ([e0b5b49](https://github.com/anandkaranubc/git-into-gsoc/commit/e0b5b4903edcf1ef85be6c8f12bc3966dd2a49c4))


### Bug Fixes

* **cli:** print the setup paths as plain lines and blank the path of skipped rows ([#28](https://github.com/anandkaranubc/git-into-gsoc/issues/28)) ([a0b8cf4](https://github.com/anandkaranubc/git-into-gsoc/commit/a0b8cf4737e56922e0f5150064cc834bc7882e55))
* reject empty progress values and unknown phases with a hint ([#16](https://github.com/anandkaranubc/git-into-gsoc/issues/16)) ([d9bf526](https://github.com/anandkaranubc/git-into-gsoc/commit/d9bf526a62232f483068c6deee066a4566338257))
* report unknown availability on timeline failures and correct doc claims ([#19](https://github.com/anandkaranubc/git-into-gsoc/issues/19)) ([02a1159](https://github.com/anandkaranubc/git-into-gsoc/commit/02a1159064bd9c4d669506ea2b765c60f975f270))
* score repo health on outside authors merged and put community before claiming issues ([#22](https://github.com/anandkaranubc/git-into-gsoc/issues/22)) ([195e31b](https://github.com/anandkaranubc/git-into-gsoc/commit/195e31bfe9f0f0ef872bb69ef521e4c7d5509bc5))


### Performance Improvements

* rank organizations from an embedded snapshot instead of the 15 MB archive ([#18](https://github.com/anandkaranubc/git-into-gsoc/issues/18)) ([7e4da97](https://github.com/anandkaranubc/git-into-gsoc/commit/7e4da97787dbbd98fccd5d95d8d204615731e3dd))


### Documentation

* add governance guide and no-attribution commit hooks ([b6e9d3c](https://github.com/anandkaranubc/git-into-gsoc/commit/b6e9d3ca965b122e66343515aaa47c350b4cdeb1))
* add README, architecture guides, and examples ([0811a4e](https://github.com/anandkaranubc/git-into-gsoc/commit/0811a4eb6d13dc0fee264eeda6b892541f363218))
* **cli:** say the journey, proposal, and rules in plain language ([#23](https://github.com/anandkaranubc/git-into-gsoc/issues/23)) ([938e671](https://github.com/anandkaranubc/git-into-gsoc/commit/938e6715dfadaf6768ebcfd0dbeb5f578e686e05))
* explain uvx on first use and say AND in plain words ([#32](https://github.com/anandkaranubc/git-into-gsoc/issues/32)) ([f105f58](https://github.com/anandkaranubc/git-into-gsoc/commit/f105f586ef5bfa8dea38c83037f26a38a1c2e268))
* rebuild the beginner guide and references around live program, org, repo, and issue evidence ([#12](https://github.com/anandkaranubc/git-into-gsoc/issues/12)) ([3d9ca3c](https://github.com/anandkaranubc/git-into-gsoc/commit/3d9ca3c430ea363b2c0d198b3b222ebfbecdb784))
* rewrite the agent skill, MCP reference, and examples for beginners ([#13](https://github.com/anandkaranubc/git-into-gsoc/issues/13)) ([1abc3a4](https://github.com/anandkaranubc/git-into-gsoc/commit/1abc3a4fddae85301bdbc7c18fb7489a653505fa))
* **skill:** document the proposal check, tracking flags, and new phase order ([#24](https://github.com/anandkaranubc/git-into-gsoc/issues/24)) ([c7a83c0](https://github.com/anandkaranubc/git-into-gsoc/commit/c7a83c0ce91894c4bdcae64e057955200cac2d3c))

## [Unreleased]

## [0.1.0] (2026-10-20)

### Added

* Portable Agent Skill (`skills/git-into-gsoc`) for Cursor, Claude Code, Codex, Gemini CLI
* Python package with Typer CLI (`git-into-gsoc` / `gsoc`)
* MCP server (`git-into-gsoc mcp`) with org search, repo health, issue availability, recommendations, proposal checklist, and progress tracking
* GSoC Organizations archive client + 2026/2027 timeline helpers (estimates clearly labeled)
* GitHub intelligence: repo health scoring, beginner-issue search, availability checks, contribution guide extraction
* One-shot `install.sh`
* Docs, examples, CI, and contribution infrastructure
* Anti-spam / anti-fabrication principles encoded in skill + guidance module
