# docs_catalog_initial — documentation checklist

- [x] `job-submission` · feature · docs/features/job-submission.md
      title: Job Submission (POST /v1/jobs)
      entry: route: POST /v1/jobs in src/scenewise/service/http/routes.py post_job -> src/scenewise/service/http/push.py push, read_body, _admitted, _rejected ; usecases: src/scenewise/app/delivery.py handle_delivery (Finished, Rejected, TryLater) ; contract: src/scenewise/app/contract/envelope.py parse, src/scenewise/app/contract/requests.py JobRequestV1, src/scenewise/app/contract/mapping.py rejection_json ; ports: BlobStore (deps.store) ; service state: src/scenewise/service/http/state.py ServiceState (limiter, watchdog, policy) ; stored_data: job record {state_prefix}/{job_id}/status.json, artifacts {prefix}/a{attempt}/
- [x] `job-status` · feature · docs/features/job-status.md
      title: Job Status (GET /v1/jobs/{job})
      entry: route: GET /v1/jobs/{job} in src/scenewise/service/http/routes.py get_job ; usecases: src/scenewise/app/delivery.py job_status, record_uri ; contract: src/scenewise/app/contract/mapping.py status_json, record_from_json, src/scenewise/app/contract/results.py JobStatusV1 ; domain: src/scenewise/domain/jobs.py wire_status, job_id ; ports: BlobStore read ; stored_data: job record {state_prefix}/{job_id}/status.json
- [x] `audio-stage` · feature · docs/features/audio-stage.md
      title: Audio Stage
      entry: usecases: src/scenewise/app/audio.py acquire_audio, src/scenewise/app/stages.py audio, src/scenewise/app/runner.py _audio_stage, _dispatch ; domain: src/scenewise/domain/inputs.py AudioFile, AudioSegments, AudioManifest, NoAudio ; ports: BlobStore materialise (deps.inputs), MediaTool probe, audio_track ; adapters: src/scenewise/adapters/media/ffmpeg.py FfmpegMediaTool ; contract: src/scenewise/app/contract/requests.py AudioFileV1, NoAudioV1, src/scenewise/app/contract/results.py AudioStageV1 ; stored_data: audio.wav under {prefix}/a{attempt}/
- [x] `job-results-and-artifacts` · feature · docs/features/job-results-and-artifacts.md
      title: Job Results and Artifacts
      entry: usecases: src/scenewise/app/publish.py publish, attempt_prefix, src/scenewise/app/delivery.py artifacts_prefix, job_prefix ; contract: src/scenewise/app/contract/mapping.py result_json, src/scenewise/app/contract/results.py JobResultV1, StageResultsV1, ProbedMediaV1, src/scenewise/app/contract/requests.py DeliveryV1, ArtifactSinkV1 ; ports: BlobStore write (deps.store) ; config: ServiceSettings.artifact_roots, state_prefix ; stored_data: result.json and audio.wav under {prefix}/a{attempt}/, result_uri in the job record
- [x] `cli-analyse` · feature · docs/features/cli-analyse.md
      title: CLI analyse Command
      entry: cli: scenewise analyse FILE --out DIR [--stage ...] and --version in src/scenewise/service/cli.py main, analyse, _parser, _with_local_root ; entry point: src/scenewise/__main__.py, pyproject.toml [project.scripts] ; usecases: src/scenewise/app/runner.py run_job ; composition: src/scenewise/service/bootstrap.py build_dependencies ; contract: src/scenewise/app/contract/mapping.py result_json ; stored_data: audio.wav written to --out, result document on stdout, no job record
- [x] `health-probes` · feature · docs/features/health-probes.md
      title: Health Probes (/healthz, /readyz)
      entry: routes: GET /healthz and GET /readyz in src/scenewise/service/http/routes.py healthz, readyz ; watchdog: src/scenewise/service/http/health.py Watchdog (watch, overdue) ; lifespan: src/scenewise/service/http/app.py create_app ; config: ServiceSettings.attempt_budget_s, watchdog_grace_s, probe_period_s, probe_failure_threshold ; deps: src/scenewise/app/deps.py Dependencies.enabled_stages
- [x] `layering-and-ports` · concept · docs/concepts/layering-and-ports.md
      title: Layering, Ports and the Composition Root
      entry: layers: domain, app, adapters, service, package (ARCHITECTURE.md §2-§4, pyproject.toml [tool.importlinter]) ; ports: src/scenewise/ports.py ; bundle: src/scenewise/app/deps.py Dependencies, Speech, enabled_stages ; composition root: src/scenewise/service/bootstrap.py build_dependencies, _stores ; adapters: src/scenewise/adapters/storage/local.py, src/scenewise/adapters/media/ffmpeg.py, src/scenewise/adapters/media/images.py
- [x] `wire-contract` · concept · docs/concepts/wire-contract.md
      title: The Versioned Wire Contract
      entry: contract: src/scenewise/app/contract/requests.py JobRequestV1, src/scenewise/app/contract/results.py JobResultV1, JobStatusV1, ProblemV1, RejectionV1, src/scenewise/app/contract/records.py JobRecordV1, src/scenewise/app/contract/envelope.py parse, request_digest, _external_ref ; mapping: src/scenewise/app/contract/mapping.py to_domain, record_to_json, record_from_json, status_json, result_json, problem ; constants: src/scenewise/app/constants.py SCHEMA_VERSION_V1, JSON_MEDIA_TYPE
- [ ] `error-model` · concept · docs/concepts/error-model.md
      title: Error Model and HTTP Mapping
      entry: domain: src/scenewise/domain/errors.py ScenewiseError and subclasses, ErrorCode aliases ; http: src/scenewise/service/http/problems.py http_status, problem_title, problem_response, src/scenewise/service/http/push.py _rejected ; usecases: src/scenewise/app/runner.py _run_stage, src/scenewise/app/delivery.py _run ; contract: src/scenewise/app/contract/mapping.py problem, rejection_json, _stage_fields ; reference: ARCHITECTURE.md §9
- [ ] `job-lifecycle-and-timing` · concept · docs/concepts/job-lifecycle-and-timing.md
      title: Job Lifecycle, Leases and Timing Invariants
      entry: domain: src/scenewise/domain/jobs.py JobRecord, JobState, AttemptInfo, decide_attempt, Decision variants, wire_status ; usecases: src/scenewise/app/delivery.py handle_delivery, _attempt, _release, _finish, _give_up, src/scenewise/app/runner.py remaining ; ports: BlobStore write if_generation, WriteConflictError, ABSENT_GENERATION ; config: src/scenewise/service/config.py ServiceSettings._timing, lease_s, max_attempts ; stored_data: job record {state_prefix}/{job_id}/status.json ; reference: ARCHITECTURE.md §7-§8
- [x] `stages-and-outcomes` · concept · docs/concepts/stages-and-outcomes.md
      title: Stages, Planning and Outcomes
      entry: domain: src/scenewise/domain/jobs.py StageName, SkipReason, src/scenewise/domain/plan.py ordered, unavailable, PREREQUISITES, src/scenewise/domain/results.py Outcome variants, StageOutcome, Analysis, job_state ; usecases: src/scenewise/app/runner.py run_job, _run_stage, src/scenewise/app/deps.py enabled_stages ; config: ServiceSettings.required_stages ; reference: ARCHITECTURE.md §6
- [x] `storage-and-uri-policy` · concept · docs/concepts/storage-and-uri-policy.md
      title: Storage and URI Policy
      entry: ports: src/scenewise/ports.py BlobStore, Blob, WriteConflictError ; adapters: src/scenewise/adapters/storage/local.py LocalBlobStore ; composition: src/scenewise/service/bootstrap.py _stores ; usecases: src/scenewise/app/delivery.py record_uri, job_prefix, artifacts_prefix, src/scenewise/app/publish.py attempt_prefix ; config: ServiceSettings.state_prefix, artifact_roots, InputSettings.local_roots ; stored_data: {state_prefix}/{job_id}/status.json, {prefix}/a{attempt}/, sidecar .name.meta.json and .name.lock files
- [x] `media-processing` · concept · docs/concepts/media-processing.md
      title: Media Processing with ffmpeg
      entry: ports: src/scenewise/ports.py MediaTool, ImageReader, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS ; adapters: src/scenewise/adapters/media/ffmpeg.py FfmpegMediaTool, find_binaries, scaled_size, src/scenewise/adapters/media/images.py PillowImageReader ; domain: src/scenewise/domain/media.py MediaInfo, Frame, Tile, Rect ; config: MediaSettings ffmpeg, ffprobe, min_major ; reference: ARCHITECTURE.md §11
- [x] `configuration` · concept · docs/concepts/configuration.md
      title: Configuration and Settings
      entry: settings: src/scenewise/service/config.py Settings, MediaSettings, InputSettings, ServiceSettings, LogSettings ; env: SCENEWISE_ prefix with __ nesting ; consumers: src/scenewise/service/bootstrap.py build_dependencies, src/scenewise/service/http/app.py create_app, src/scenewise/service/cli.py main ; reference: ARCHITECTURE.md §10, README.md Requirements
- [x] `logging` · concept · docs/concepts/logging.md
      title: Logging
      entry: setup: src/scenewise/service/logs.py configure, LogSettings level and format ; context: structlog bound_contextvars in src/scenewise/app/runner.py, src/scenewise/app/delivery.py, src/scenewise/service/http/push.py _log_context (Cloud Tasks headers) ; redaction: src/scenewise/app/contract/mapping.py _validation_summary, src/scenewise/domain/errors.py module docstring ; reference: ARCHITECTURE.md §10
- [ ] `index` · concept · docs/INDEX.md
      title: scenewise Docs Index
      entry: read this checklist and every doc under docs/features/ and docs/concepts/ ; produce a grouped, linked map (features by area, concepts by area) ; fold in sdlc-harness/docs_catalog/needs_review.md as a Flagged for human review section ; parity is off, so no parity gaps section
