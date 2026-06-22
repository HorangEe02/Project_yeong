# Mac, VS Code, Lemon-Aid Project Environment Summary

Date: 2026-05-19
Workspace root: `/Users/yeong/99_me/00_github/03_lemon_healthcare`
Project root: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid`

## 1. 작성 기준

이 문서는 현재 Mac에서 실제 명령으로 확인한 개발 환경, VS Code 설정, Lemon-Aid 프로젝트가 정의한 기술 스택과 실행 환경을 정리한다.

보안 원칙:

- `.env`와 `backend/.env`는 존재만 확인하고 내용은 읽지 않았다.
- API key, JWT secret, OCR vendor secret, database password 같은 비밀값은 문서에 기록하지 않는다.
- 환경값은 `.env.example`, `pyproject.toml`, `requirements*.txt`, `pubspec.yaml`, `Dockerfile`, `PROJECT_GUIDE.md`, `implementation-readiness.settings.json` 기준으로 정리했다.

## 2. 현재 Mac 기본 환경

| 항목 | 현재 확인값 |
| --- | --- |
| OS | macOS 26.5 |
| Build | 25F71 |
| CPU architecture | arm64 |
| Shell | zsh |
| Homebrew | 5.1.11 |
| Python CLI | `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` |
| Python version | 3.13.7 |
| Node.js CLI | `/usr/local/bin/node` |
| Node.js version | v22.17.0 |
| npm version | 10.9.2 |
| Docker CLI | `/usr/local/bin/docker` |
| Docker version | 29.4.3 |
| PostgreSQL CLI | `psql` not found |
| Ollama CLI | `/opt/homebrew/bin/ollama` |
| Ollama client | 0.18.2 |
| ngrok | `/opt/homebrew/bin/ngrok`, version 3.37.3 |

Ollama 상태:

- `ollama --version`은 client version `0.18.2`를 반환했다.
- 확인 시점에는 실행 중인 Ollama server에 연결되지 않았다.
- 프로젝트 기본값은 `OLLAMA_BASE_URL=http://127.0.0.1:11434`이므로, 실제 LLM 기능 검증 전 `ollama serve` 또는 원격 A100 tunnel 확인이 필요하다.

Docker 상태:

- Docker CLI는 설치되어 있다.
- 이 문서 작성 중 Docker daemon live 상태는 별도 확인하지 않았다.

PostgreSQL CLI 상태:

- `psql` 명령은 현재 PATH에서 발견되지 않았다.
- 프로젝트 런타임은 Python `asyncpg`와 SQLAlchemy async 엔진을 사용하므로, DB 접속 자체와 `psql` CLI 설치 여부는 별도 문제다.

## 3. zsh PATH 및 개발 도구 경로

확인 파일:

- `/Users/yeong/.zshenv`
- `/Users/yeong/.zprofile`
- `/Users/yeong/.zshrc`

주요 설정:

```bash
export ANDROID_HOME="/opt/homebrew/share/android-commandlinetools"
export PATH="$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
```

추가 PATH 계열:

- `/usr/local/RemoteDevelopmentToolkit/bin`
- `/Library/Frameworks/Python.framework/Versions/3.13/bin`
- `/Users/yeong/.npm-global/bin`
- `/opt/anaconda3/bin`
- `/usr/local/mysql/bin`
- `/Users/yeong/.lmstudio/bin`
- `/Users/yeong/.opencode/bin`
- `/Users/yeong/.antigravity/antigravity/bin`

주의:

- `.zshenv`에 Android SDK command-line tools 경로가 들어가 있어 VS Code terminal과 Flutter CLI에서 emulator, adb, cmdline-tools를 찾을 수 있다.
- `.zshrc`에는 여러 AI/DB/Node 관련 CLI path가 추가되어 있다.

## 4. Flutter, Android, iOS 개발 환경

### 4.1 Flutter

| 항목 | 현재 확인값 |
| --- | --- |
| Flutter CLI | `/opt/homebrew/bin/flutter` |
| Flutter version | 3.41.9 |
| Channel | stable |
| Flutter SDK path | `/opt/homebrew/share/flutter` |
| Dart version | 3.11.5 |
| DevTools | 2.54.2 |

`flutter doctor -v` 결과:

- Flutter: ready
- Android toolchain: ready
- Xcode: ready
- Chrome: ready
- Connected devices: macOS, Chrome
- Network resources: ready
- Final result: `No issues found!`

### 4.2 Android

| 항목 | 현재 확인값 |
| --- | --- |
| Android SDK | `/opt/homebrew/share/android-commandlinetools` |
| Android SDK version | 36.0.0 |
| Build tools | 36.0.0 |
| Platform | android-36 |
| ADB CLI | `/opt/homebrew/bin/adb` |
| ADB version | 37.0.0-14910828 |
| Flutter configured JDK | `/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home` |
| Flutter configured Java | OpenJDK 17.0.19 |

`flutter config --list` 기준:

```text
jdk-dir: /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
android-sdk: /opt/homebrew/share/android-commandlinetools
```

주의:

- 일반 `java -version`은 Temurin OpenJDK 25.0.2를 반환했다.
- Flutter Android build는 global Java가 아니라 Flutter config의 OpenJDK 17을 사용한다.
- `emulator -version` 직접 호출은 Qt/Crashpad 관련 오류와 `Incompatible processor ... neon` 메시지로 실패했다.
- 그러나 `flutter doctor -v`는 Android emulator version `36.5.11.0`과 Android toolchain ready 상태를 확인했다.

### 4.3 iOS/macOS

| 항목 | 현재 확인값 |
| --- | --- |
| Active Xcode path | `/Applications/Xcode.app/Contents/Developer` |
| Xcode version | 26.3 |
| Xcode build | 17C528 |
| CocoaPods | 1.16.2 |

현재 connected devices:

- macOS desktop
- Chrome web

주의:

- 확인 시점에는 무선 iPhone 연결이 실패했다.
- Flutter 메시지는 iPhone unlock, same LAN/cable, Developer Mode 확인을 요구했다.
- Android emulator는 `flutter devices` 기준 현재 실행 중인 device로 잡히지 않았다.

## 5. VS Code 설치 및 설정

### 5.1 VS Code CLI

| 항목 | 현재 확인값 |
| --- | --- |
| Code CLI | `/usr/local/bin/code` |
| VS Code version | 1.120.0 |
| Commit | `0958016b2af9f09bb4257e0df4a95e2f90590f9f` |
| Architecture | arm64 |

주의:

- `code --version` 실행 시 macOS codesign 관련 `task_name_for_pid` 오류 로그가 출력되었지만 version 값은 정상 반환됐다.
- `code --list-extensions` 실행 시 `Code/logs/...` 생성에 대한 `EPERM` 로그가 출력되었지만 extension 목록은 반환됐다.

### 5.2 User settings

설정 파일:

```text
/Users/yeong/Library/Application Support/Code/User/settings.json
```

주요 설정:

| 설정 | 값/의미 |
| --- | --- |
| `workbench.iconTheme` | `material-icon-theme` |
| `workbench.colorTheme` | `GitHub Dark Colorblind (Beta)` |
| `terminal.integrated.inheritEnv` | `false` |
| `typescript.preferences.importModuleSpecifier` | `non-relative` |
| `chat.useAgentSkills` | `true` |
| `git.openRepositoryInParentFolders` | `always` |
| `security.workspace.trust.untrustedFiles` | `open` |
| `http.systemCertificatesNode` | `true` |
| `notebook.output.textLineLimit` | `500` |
| `chat.mcp.gallery.enabled` | `true` |
| `claudeCode.preferredLocation` | `panel` |
| `liveServer.settings.donotShowInfoMsg` | `true` |

중요 해석:

- `terminal.integrated.inheritEnv=false`이므로 VS Code 통합 terminal이 macOS login shell 환경을 그대로 상속하지 않을 수 있다.
- Android/Flutter PATH가 동작하지 않을 때는 VS Code terminal에서 `ANDROID_HOME`, `PATH`, `flutter config --list`를 직접 확인해야 한다.

### 5.3 VS Code MCP 설정

설정 파일:

```text
/Users/yeong/Library/Application Support/Code/User/mcp.json
```

등록된 MCP 서버:

- `microsoft/markitdown`
- `io.github.github/github-mcp-server`
- `makenotion/notion-mcp-server`
- `com.figma.mcp/mcp`
- `chroma-core/chroma-mcp`

주의:

- Chroma MCP는 prompt input 형태로 API key/custom auth를 받을 수 있게 되어 있다.
- 이 문서에는 secret input 값이 없고, 실제 secret도 기록하지 않는다.

### 5.4 주요 VS Code 확장

Flutter/Dart:

- `dart-code.dart-code`
- `dart-code.flutter`
- `alexisvt.flutter-snippets`

Python:

- `ms-python.python`
- `ms-python.vscode-pylance`
- `ms-python.debugpy`
- `ms-python.black-formatter`
- `ms-python.vscode-python-envs`
- `donjayamanne.python-environment-manager`
- `kevinrose.vsc-python-indent`
- `njpwerner.autodocstring`

Jupyter/Data:

- `ms-toolsai.jupyter`
- `ms-toolsai.datawrangler`
- `percy.vscode-pydata-viewer`

Containers/Remote:

- `ms-vscode-remote.remote-ssh`
- `ms-vscode-remote.remote-ssh-edit`
- `ms-vscode-remote.remote-containers`
- `ms-vscode.remote-explorer`
- `ms-azuretools.vscode-containers`
- `ms-azuretools.vscode-docker`
- `docker.docker`

Database:

- `alexcvzz.vscode-sqlite`
- `qwtel.sqlite-viewer`
- `ckolkman.vscode-postgres`
- `ms-ossdata.vscode-pgsql`
- `mtxr.sqltools`
- `mtxr.sqltools-driver-mysql`
- `ms-mssql.mssql`
- `cweijan.vscode-postgresql-client2`
- `cweijan.vscode-mysql-client2`

Markdown/Docs:

- `davidanson.vscode-markdownlint`
- `bierner.markdown-mermaid`
- `bierner.markdown-preview-github-styles`
- `shd101wyy.markdown-preview-enhanced`

AI/Agent tooling:

- `anthropic.claude-code`
- `github.copilot-chat`
- `google.gemini-cli-vscode-ide-companion`
- `google.geminicodeassist`
- `teamsdevapp.vscode-ai-foundry`
- `ms-azuretools.vscode-azure-mcp-server`
- `supabase.vscode-supabase-extension`

Other development:

- C/C++ extension pack
- Java extension pack
- Gradle, Maven
- OpenCV snippets/intellisense
- Live Server
- PDF viewer

## 6. Lemon-Aid 프로젝트 구조

주요 디렉터리:

| 경로 | 역할 |
| --- | --- |
| `backend/` | FastAPI backend, Alembic, scripts, Dockerfile |
| `backend/Nutrition-backend/src/` | 백엔드 런타임 코드 |
| `backend/Nutrition-backend/tests/` | backend unit/integration tests |
| `mobile/flutter_app/` | Flutter mobile app |
| `firebase-ocr-test/` | Firebase/브라우저 기반 OCR test UI |
| `docs/` | Nutrition/Food/Chat/Integration 문서 |
| `config/` | readiness/settings JSON |
| `data/nutrition_reference/` | KDRI, barcode, nutrition reference data |
| `data/private/` | private annotation/training data 계열 |
| `PaddleOCR-main/` | PaddleOCR source snapshot/integration area |
| `sglang-main/` | SGLang source snapshot/integration area |
| `outputs/todo-list/` | 날짜별 팀 공유/작업 산출물 |

현재 Git 상태:

- 작업 트리에 이미 많은 수정 파일과 untracked 파일이 존재한다.
- 이 문서는 기존 변경을 되돌리지 않고, 새 산출물만 추가한다.

## 7. Backend 기술 스택

선언 파일:

- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/.env.example`
- `backend/Dockerfile`
- `PROJECT_GUIDE.md`

### 7.1 런타임

| 영역 | 기술 |
| --- | --- |
| Language | Python >= 3.13 |
| API framework | FastAPI >=0.110,<0.140 |
| ASGI server | Uvicorn standard >=0.27,<0.35 |
| Data validation | Pydantic >=2.6,<3.0 |
| Settings | pydantic-settings >=2.2,<3.0 |
| Auth | PyJWT[crypto] >=2.10,<3.0 |
| ORM/DB | SQLAlchemy[asyncio] >=2.0,<3.0 |
| PostgreSQL driver | asyncpg >=0.29 |
| Migration | Alembic >=1.13 |
| Cache/rate-limit foundation | Redis >=5.0 |
| HTTP client | httpx >=0.27 |
| LLM client | ollama >=0.6.0 |
| OCR external option | google-cloud-vision >=3.7, google-auth >=2.29 |
| Image processing | Pillow >=10.2 |
| Multipart upload | python-multipart >=0.0.9 |

### 7.2 개발/품질 도구

| 영역 | 기술 |
| --- | --- |
| Formatting | Black >=24.4 |
| Linting | Ruff >=0.4 |
| Type checking | mypy >=1.10, strict mode |
| Tests | pytest >=8.0 |
| Async tests | pytest-asyncio >=0.23 |
| Coverage | pytest-cov >=4.1, fail-under 80 |
| Mocking | pytest-mock >=3.12 |
| Security audit | pip-audit >=2.10,<3.0 |

`pyproject.toml` 주요 정책:

- Python target: 3.13
- Black/Ruff line length: 100
- Ruff lint convention: Google style docstring
- mypy: strict mode
- pytest addopts: coverage report + `--cov-fail-under=80`

### 7.3 Optional backend features

`backend/pyproject.toml` optional dependencies:

| Extra | 포함 기술 | 목적 |
| --- | --- | --- |
| `vision` | torch, ultralytics | YOLO/vision classifier gate |
| `learning` | boto3, pgvector, sentence-transformers | image learning/vector pipeline gate |
| `ocr-local` | paddleocr | local OCR fallback |

이 optional stack은 기본 CI/runtime에 항상 켜는 항목이 아니라, 문서화된 gate 통과 후 활성화하는 구조다.

## 8. Backend 환경변수 정책

기준 파일:

- `backend/.env.example`
- `config/implementation-readiness.settings.json`

주요 runtime defaults:

```env
ENVIRONMENT=development
DEPLOYMENT_EXPOSURE=local
DATABASE_URL=postgresql+asyncpg://lemon:lemon@localhost:5432/lemon
REDIS_URL=redis://localhost:6379/0
AUTH_MODE=disabled
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_TIMEOUT_SEC=60
OLLAMA_TEMPERATURE=0
ALLOW_EXTERNAL_LLM=false
OCR_PRIMARY_PROVIDER=paddleocr
ALLOW_EXTERNAL_OCR=false
ENABLE_LOCAL_OCR=true
LOCAL_OCR_PROVIDER=paddleocr
LOCAL_OCR_LANGUAGE=korean
```

보안/운영 기본값:

- public staging/production은 JWT, explicit hosts/origins, rate limit을 요구한다.
- production에서는 `ALLOW_EXTERNAL_LLM=true`가 차단된다.
- production에서는 Google Vision 사용 시 ADC, project, external OCR consent가 필요하다.
- prescription/lab OCR, medication safety alert, dosage-change recommendation은 feature flag 기본값이 false다.
- 민감 문서 원본 이미지 retention 기본값은 `0`초다.
- image learning, pgvector, multimodal LLM, YOLO ROI preprocessing은 gate sign-off 전 기본 비활성이다.

주의:

- 실제 `.env`와 `backend/.env`는 존재하지만 secret 보호를 위해 내용은 열람하지 않았다.
- 이 문서는 `.env.example` 기준의 선언 환경을 설명한다.

## 9. LLM/OCR/AI 파이프라인

### 9.1 LLM

현재 기본 정책:

- Provider: Ollama
- Base URL: `http://127.0.0.1:11434`
- Model: `qwen3.5:9b`
- Vision model candidate: `gemma4:e4b`
- Temperature: 0
- External LLM: false

핵심 구현 방식:

- Ollama Chat API payload에 Pydantic JSON Schema를 `format`으로 전달한다.
- 응답의 `message.content`는 다시 Pydantic `model_validate_json()`으로 검증한다.
- LLM은 `nutrient_code`, diagnosis, treatment, dose-change guidance를 확정하지 않는다.
- raw OCR text와 raw model response를 저장하지 않는다.

### 9.2 OCR

기본 OCR:

- Primary provider: PaddleOCR local
- Language: Korean
- Confidence threshold: 0.85 primary OCR, 0.75 local OCR fallback

옵션 OCR:

- Google Vision: explicit live-smoke/comparison opt-in
- CLOVA OCR: explicit fallback opt-in
- Ollama vision assist: multimodal gate #1 전 기본 disabled

안전 정책:

- OCR/LLM 결과는 preview이며 사용자 확인 전 최종 데이터가 아니다.
- raw image와 raw OCR text는 product API에서 직접 노출하지 않는다.
- regulated OCR은 별도 intake-only flow와 명시적 확인을 요구한다.

## 10. Database, Cache, Migration

| 영역 | 현재 프로젝트 정의 |
| --- | --- |
| Main DB | PostgreSQL via `postgresql+asyncpg` |
| ORM | SQLAlchemy async |
| Migration | Alembic |
| Cache/rate-limit foundation | Redis |
| Local CLI caveat | 현재 Mac PATH에서 `psql` 없음 |

현재 개발 DB 기본 URL은 `.env.example` 기준:

```env
DATABASE_URL=postgresql+asyncpg://lemon:lemon@localhost:5432/lemon
REDIS_URL=redis://localhost:6379/0
```

## 11. Mobile Flutter 앱

기준 파일:

- `mobile/flutter_app/pubspec.yaml`
- `mobile/flutter_app/analysis_options.yaml`
- `mobile/flutter_app/android/key.properties.example`
- `mobile/flutter_app/lib/app.dart`
- `mobile/flutter_app/lib/app_controller.dart`
- `mobile/flutter_app/lib/main.dart`

선언된 Flutter 앱:

| 항목 | 값 |
| --- | --- |
| package name | `lemon_aid_mobile` |
| description | Minimal Lemon Aid mobile demo connected to Nutrition backend |
| version | `1.0.0+1` |
| Dart SDK constraint | `^3.11.5` |
| publish | `none` |

dependencies:

- `flutter`
- `cupertino_icons ^1.0.8`
- `http ^1.6.0`
- `image_picker ^1.2.2`

dev dependencies:

- `flutter_test`
- `flutter_lints ^6.0.0`

Release guardrail:

- Android signing scaffold는 `android/key.properties.example`로 존재한다.
- 실제 release signing material은 별도 제공 전까지 문서화된 scaffold일 뿐이다.
- 현재 connected device는 macOS/Chrome이며, Android emulator와 iPhone은 실행/연결 상태가 아니었다.

## 12. Docker/배포 환경

기준 파일:

- `backend/Dockerfile`

Dockerfile 요약:

- Base image: `python:3.13-slim`
- Workdir: `/app`
- `requirements.txt` 설치
- `INSTALL_PADDLEOCR=true`일 때 PaddlePaddle CPU package와 `paddleocr[all]>=3.0` 추가 설치
- `Nutrition-backend`, `alembic`, `alembic.ini` 복사
- Expose: `8080`
- Entrypoint: `python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}`

확인 범위:

- 이 문서 작성 중 `docker-compose*.yml`은 프로젝트 maxdepth 3 검색에서 발견되지 않았다.
- 배포 실행은 Dockerfile 기반 backend container를 우선 기준으로 본다.

## 13. Frontend/Firebase test surface

확인된 별도 surface:

- `firebase-ocr-test/firebase.json`
- `firebase-ocr-test/.firebaserc`
- `firebase-ocr-test/public/`

역할:

- 모바일/브라우저 OCR 테스트용 frontend surface다.
- ngrok gateway와 함께 로컬 backend OCR 테스트에 사용된 이력이 있다.

주의:

- `frontend/` 디렉터리는 존재하지만 maxdepth 3 기준 `package.json`은 발견되지 않았다.
- 현재 주요 모바일 surface는 Flutter app으로 정리하는 것이 맞다.

## 14. 현재 확인된 운영상 주의점

1. Worktree가 매우 dirty하다.
   - 이 문서 외에도 다수의 수정/미추적 파일이 존재한다.
   - publish/commit 시에는 의도한 파일만 좁게 staging해야 한다.

2. `.env` 파일은 존재하지만 읽지 않았다.
   - 실제 local secret/config 상태는 이 문서에 포함하지 않았다.
   - 재현 가능한 팀 문서는 `.env.example` 기준으로 관리해야 한다.

3. VS Code terminal 환경과 shell 환경이 다를 수 있다.
   - `terminal.integrated.inheritEnv=false` 때문이다.
   - Flutter/Android 문제가 나면 VS Code terminal 안에서 `flutter doctor -v`, `flutter config --list`, `echo $ANDROID_HOME`를 다시 확인해야 한다.

4. Ollama server는 확인 시점에 실행 중이 아니었다.
   - local Ollama 테스트 전 `ollama serve`가 필요하다.
   - A100 원격 Ollama를 쓸 경우 SSH/VS Code port forwarding과 별도 remote-private LLM 정책이 필요하다.

5. Android emulator 직접 version command는 실패했다.
   - Flutter doctor는 Android toolchain ready를 확인했지만, emulator 직접 실행/버전 확인은 Qt/processor 관련 오류를 냈다.
   - 실제 device test 전 `flutter emulators`, `adb devices`, emulator boot 상태 확인이 필요하다.

6. `psql` CLI가 없다.
   - Alembic/SQLAlchemy/asyncpg 기반 backend 실행과는 별개로, DB 수동 점검용 CLI가 필요하면 PostgreSQL client 설치가 필요하다.

## 15. 공식 문서 참조

환경/스택 판단에 필요한 공식 문서:

- VS Code Remote SSH / port forwarding: https://code.visualstudio.com/docs/remote/ssh
- Flutter macOS Android setup: https://docs.flutter.dev/get-started/install/macos/mobile-android
- Flutter CLI / doctor guide: https://docs.flutter.dev/reference/flutter-cli
- FastAPI documentation: https://fastapi.tiangolo.com/
- Pydantic BaseModel API: https://docs.pydantic.dev/latest/api/base_model/
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
- Redis Python client: https://redis.io/docs/latest/develop/clients/redis-py/
- Dockerfile reference: https://docs.docker.com/reference/builder
- Ollama API introduction: https://docs.ollama.com/api/introduction
- Ollama Chat API: https://docs.ollama.com/api/chat
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs

## 16. 다음 액션

권장 후속 작업:

1. `.env.example`와 실제 `.env` 차이를 secret-safe 방식으로 점검하는 스크립트를 추가한다.
2. VS Code workspace-local `.vscode/settings.json`이 필요하면 프로젝트 전용으로 Python path, Flutter SDK, formatter, test command만 최소 설정한다.
3. Ollama local/A100 remote runtime을 실제로 쓸 경우 `probe_ollama_runtime.py`를 추가해 `/api/tags`, structured output, latency, model presence를 비식별 smoke test로 확인한다.
4. Android emulator direct command 실패 원인을 별도 추적한다. Flutter doctor는 통과하므로 우선순위는 실제 device run이 필요할 때 올린다.
