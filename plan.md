# Kế hoạch khởi tạo Backend Python (FastAPI + Keycloak + PostgreSQL/SQLAlchemy + Milvus)

Ngày cập nhật: 2025-09-05

## 0) Mục tiêu và tiêu chí chung

- Mục tiêu: Dựng bộ khung backend chuẩn 3 lớp (Presentation / Application / Data) bằng FastAPI; xác thực/ủy quyền chuẩn OAuth2/OIDC qua Keycloak (chạy Docker); dữ liệu quan hệ trên PostgreSQL (ORM bằng SQLAlchemy 2.0, async với asyncpg); tích hợp Vector DB Milvus; bảo mật CORS và logging đầy đủ.
- Worker criteria (áp dụng xuyên suốt khi code):
  - Luôn luôn suy nghĩ kỹ, triển khai step-by-step (ghi chú rõ ràng trong PR/commit).
  - Kiểm tra lại chất lượng code một lần trước khi hoàn thành (self-review + lint/test).
  - Mọi function bắt buộc có docstring (mô tả input/output, exceptions, side-effects).

## 1) Kiến trúc & cấu trúc thư mục

- Mô hình 3 lớp:
  - Presentation (API): định nghĩa routers, request/response models, dependency injection, CORS, middleware, auth guards.
  - Application (Services/Use cases): nghiệp vụ, orchestrate repo + clients (Keycloak/JWKS, Milvus), kiểm soát phân quyền (RBAC/ABAC), kiểm tra IDOR.
  - Data (Persistence): ORM models, repositories (SQLAlchemy), migration (Alembic), client Milvus (PyMilvus), mapping entity <-> schema.
- Cấu trúc thư mục dự kiến:
  - `src/`
    - `api/` (presentation): `routers/`, `deps/`, `schemas/`
    - `application/` (services): `services/`, `auth/`, `use_cases/`
    - `data/` (persistence): `models/`, `repositories/`, `migrations/`
    - `integrations/`: `keycloak/` (OIDC/JWKS), `milvus/` (PyMilvus client)
    - `core/`: `config.py`, `logging.py`, `security.py`, `cors.py`, `errors.py`
    - `main.py`: khởi tạo FastAPI, mount routers, middleware
  - `docker/`: `keycloak/` (realm file), `postgres/` (init scripts), `milvus/` (yml tham khảo)
  - `scripts/`: tiện ích PowerShell/Bash (`dev-up`, `dev-down`, `migrate`, `seed`)
  - `tests/`: unit/integration tests (pytest + httpx)
  - `.env.example`, `docker-compose.yml`, `README.md`, `Makefile` hoặc `Taskfile.yml` (tuỳ chọn), `requirements.txt`/`pyproject.toml`

## 2) Công nghệ & phiên bản khuyến nghị (2025)

- FastAPI (phiên bản ổn định mới nhất 2025), Uvicorn cho dev, có thể Gunicorn/UvicornWorker cho prod.
- SQLAlchemy 2.x (async) + `asyncpg`, Alembic cho migration.
- PostgreSQL 14/15/16 (Docker image official).
- Keycloak (>=24.x/25.x) chạy Docker, import realm bằng `--import-realm` và đặt file vào `/opt/keycloak/data/import` theo quy ước `<realm>-realm.json` (theo docs Keycloak Import/Export 2025).
- Milvus Standalone v2.5.x (Docker Compose), kèm MinIO + etcd (theo docs Milvus 2.5.x Windows/Linux).
- PyMilvus client để thao tác Milvus.
- httpx (async) để lấy JWKS (caching), python-jose hoặc authlib để verify JWT (RS256) từ Keycloak.
- Pydantic v2 cho schema/validation.
- Logging: chuẩn JSON; có correlation ID middleware.
- Lint/format: ruff + black; pre-commit hooks (khuyến nghị).

Tham khảo:

- Keycloak Import/Export: https://www.keycloak.org/server/importExport
- Milvus Standalone Docker Compose: https://milvus.io/docs/v2.5.x/install_standalone-docker-compose.md và Windows: https://milvus.io/docs/install_standalone-windows.md
- FastAPI CORS: https://fastapi.tiangolo.com/tutorial/cors/
- SQLAlchemy 2.x asyncio: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

## 3) OAuth2/OIDC với Keycloak (Docker)

- Mục tiêu: Bảo mật bắt buộc bằng OAuth2 (Bearer JWT). Tất cả endpoints (trừ health/metrics/docs nếu cần) yêu cầu token hợp lệ phát hành bởi Keycloak realm cấu hình.
- Key điểm triển khai:
  1. Docker Keycloak:
     - Sử dụng image `quay.io/keycloak/keycloak:<version>`.
     - Chạy `start-dev` (dev) hoặc `start` (prod) với tham số `--import-realm` khi cần import khởi tạo.
     - Realm export phải đặt tại `/opt/keycloak/data/import/<realm>-realm.json` (đúng quy ước tên file).
     - Thiết lập `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` cho bootstrap.
  2. Realm/Clients:
     - Tạo realm (ví dụ: `hakathon`), client type `confidential` cho backend (audience là API), cấp `client_secret`.
     - Cấu hình roles (e.g., `admin`, `user`), scopes cần thiết (email, profile) nếu dùng.
  3. Xác thực/JWT verify tại backend:
     - Lấy OIDC discovery: `https://<keycloak-host>/realms/<realm>/.well-known/openid-configuration` -> lấy `jwks_uri`.
     - Tải JWKS (cache + background refresh), verify `iss`, `aud`, `exp`, `nbf`, `iat`, `kid`, `alg`.
     - Trích xuất claims (`sub`, roles) -> ánh xạ sang principal nội bộ.
  4. Ủy quyền (Authorization):
     - Ở tầng Application, bổ sung guard theo role/permission và kiểm tra quyền sở hữu tài nguyên (chống IDOR).
  5. Token introspection (tuỳ chọn):
     - Dự phòng khi cần xác thực thời gian thực qua endpoint introspect của Keycloak cho trường hợp đặc biệt.

Lưu ý hostname/proxy:

- Nếu có reverse proxy (Traefik/Nginx), cân nhắc `KC_PROXY_HEADERS=xforwarded`, `KC_HOSTNAME`, `...STRICT=false` phù hợp (xem discussions Keycloak 2025).

## 4) Database PostgreSQL + ORM SQLAlchemy (chống SQLi/IDOR/SSRF)

- Kết nối async: `postgresql+asyncpg://user:pass@host:5432/db`.
- Session lifecycle theo dependency của FastAPI (AsyncSession), `expire_on_commit=False`.
- Migration: Alembic (tự động sinh revision cho models, quản lý version schema).
- Repository pattern: tách rõ CRUD và query phức tạp; tất cả truy vấn đi qua ORM (không dùng string SQL concat) -> giảm rủi ro SQL injection.
- Ràng buộc & chỉ mục: khoá chính, khoá ngoại, unique index, check constraints; soft delete nếu cần.
- Giao dịch/đồng bộ hoá: dùng transaction theo use-case; `select_for_update` khi cần nhất quán.
- IDOR: ở tầng Application, mọi truy vấn theo user phải filter theo `owner_id == current_user.sub` (hoặc theo quan hệ) trước khi trả dữ liệu.
- SSRF: không cho phép người dùng nhập URL tùy ý để server gọi ra ngoài; nếu bắt buộc, dùng allow-list domain và timeout, chặn internal IP ranges.

## 5) Vector DB Milvus

- Chạy Milvus Standalone (Docker Compose) kèm etcd + MinIO.
- Client `pymilvus`: quản lý collection, index (HNSW/IVF/FLAT tuỳ yêu cầu), insert và search embeddings.
- Tích hợp dịch vụ embeddings (tuỳ chọn, ngoài scope này) -> service sinh vector rồi upsert vào Milvus; service API cung cấp endpoint search.
- Lưu metadata (id, owner, reference) trong PostgreSQL; vector nằm ở Milvus. Đồng bộ khoá ngoại để enforce quyền truy cập (Application layer kiểm tra IDOR trước khi gọi search/trả kết quả).

## 6) CORS & bảo mật ứng dụng

- CORS: dùng `CORSMiddleware` của FastAPI, `allow_origins` cấu hình từ ENV (dev có thể `http://localhost:<port>`), cấu hình `allow_methods`, `allow_headers`, `max_age` hợp lý.
- Headers bảo mật: thêm `X-Content-Type-Options`, `X-Frame-Options` (nếu cần), `Referrer-Policy`, `Strict-Transport-Security` khi chạy HTTPS.
- Rate limiting/throttling (tuỳ chọn) bằng proxy hoặc middleware.
- Input validation: tất cả payload qua Pydantic schema; size limits và mime-type check với upload.

## 7) Logging & quan sát

- Structured logging (JSON) qua `logging`/`structlog`, output STDOUT (phù hợp container). Gắn correlation/request ID vào mỗi log.
- Log sự kiện quan trọng: auth success/failure, permission denied, thay đổi dữ liệu quan trọng, gọi external services, lỗi DB/timeout.
- Phân cấp logger: `uvicorn.access`, `uvicorn.error`, app logger; cấu hình level qua ENV.
- Không log secrets/token; mask PII khi cần.

## 8) Cấu hình & biến môi trường

- `.env` (không commit):
  - `APP_ENV`, `APP_DEBUG`
  - `DATABASE_URL`
  - `KEYCLOAK_BASE_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_AUDIENCE`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` (nếu cần introspection), `JWKS_CACHE_TTL`
  - `CORS_ORIGINS`
  - `MILVUS_HOST`, `MILVUS_PORT`
- `config.py` (Pydantic Settings) load từ ENV + validation.

## 9) Docker Compose (good-to-have)

- `docker-compose.yml` gồm:
  - `app`: build từ `Dockerfile`, mount code dev (tuỳ), expose 8000.
  - `postgres`: official image, volume data, init scripts (user/db/tables), healthcheck.
  - `keycloak`: quay.io/keycloak/keycloak, `start-dev --import-realm`, volume realm file vào `/opt/keycloak/data/import`, expose 8080 (hoặc 8070 nếu tránh xung đột), cấu hình DB riêng (khuyến nghị prod) hoặc dev mode.
  - `milvus-standalone`, `milvus-minio`, `milvus-etcd`: theo template Milvus 2.5.x.
  - `networks`: internal network; ports map rõ ràng (Windows).
- Script PS1/Bash:
  - `scripts/dev-up.(ps1|sh)`: `docker compose up -d` theo profile.
  - `scripts/dev-down.(ps1|sh)`: `docker compose down -v` (cẩn thận -v).
  - `scripts/migrate.(ps1|sh)`: alembic upgrade head.
  - `scripts/seed.(ps1|sh)`: dữ liệu demo (không chứa secrets).

## 10) Quy ước code & chất lượng

- Docstring bắt buộc cho mọi hàm/phương thức (Google/Numpy style); type hints đầy đủ.
- Lint/format: ruff + black; mypy (tuỳ chọn) để type-checking.
- Kiểm tra tự động: pytest + coverage; test cho:
  - Auth: verify JWT, role guard, từ chối IDOR.
  - Repos: CRUD chuẩn, SQL injection tests (fuzz payload), transaction.
  - Milvus: insert/search happy-path, lỗi kết nối.
  - API: CORS headers, logging có correlation ID, error handling chuẩn JSON.
- Trước khi merge: self-review theo checklist (nội dung ở cuối file này).

## 11) Lộ trình triển khai (step-by-step)

1. Bootstrap dự án + cấu trúc thư mục + thiết lập pyproject/requirements, ruff/black, pre-commit.
2. Config core: settings (.env), logging (JSON + correlation ID), CORS middleware, error handlers.
3. Dựng Docker Compose: postgres, keycloak, milvus (kèm scripts dev-up/down). Chuẩn bị realm file `<realm>-realm.json`.
4. Data layer: models SQLAlchemy 2.x, Alembic, repositories, seed tối thiểu.
5. Auth/OIDC: fetch JWKS, verify JWT, dependency cho routes, role-based guard; tích hợp claims -> principal.
6. Application services: ví dụ `UserService`, `ItemService` kèm kiểm tra quyền sở hữu (IDOR guard).
7. Milvus integration: client, collection schema, index, service insert/search, mapping metadata với Postgres.
8. API routers: các endpoints CRUD + search; tài liệu OpenAPI; tắt/giới hạn docs ngoài dev nếu cần.
9. Viết tests (unit + integration) cho các phần chính; thiết lập CI cơ bản (tuỳ chọn).
10. Rà soát bảo mật: SQLi/SSRF/IDOR, CORS, secret handling; kiểm tra logging không lộ secrets.

## 12) Rủi ro & phương án

- Keycloak realm import: phải đúng đường dẫn `/opt/keycloak/data/import` và tên file `<realm>-realm.json`; nếu dùng DB riêng, cấu hình `KC_DB=postgres` và biến kết nối.
- Windows & Docker Desktop: có thể xung đột port; chọn port khác (VD: 8070 cho Keycloak, 5432/55432 cho Postgres, 19530 cho Milvus).
- JWKS cache: hết hạn/rotate key -> cần refresh an toàn (background task + TTL). Xử lý network timeout với httpx.
- Milvus resource: RAM/CPU khi index lớn; chọn index phù hợp (HNSW/IVF) & nprobe/nlist theo nhu cầu.
- SSRF: nếu có tính năng gọi URL ngoài, áp dụng allow-list và chặn private ranges (10/8, 172.16/12, 192.168/16, 169.254/16, 127/8, ::1, fc00::/7…).

## 13) Deliverables (đầu ra mong muốn của giai đoạn khởi tạo)

- Mã nguồn khung chuẩn 3 lớp theo cấu trúc trên.
- `docker-compose.yml` chạy được: app + postgres + keycloak + milvus.
- File realm Keycloak mẫu cho dev.
- `.env.example` đầy đủ biến cấu hình.
- Bộ test tối thiểu chạy pass; lint/format pass.
- `README.md` hướng dẫn chạy nhanh (Windows/PowerShell và \*nix).

## 14) Checklist self-review trước khi hoàn thành task/PR

- [ ] Tất cả functions có docstring mô tả rõ input/output/errors.
- [ ] Không có truy vấn SQL thủ công ghép chuỗi; mọi thứ qua ORM/repository.
- [ ] Các endpoint nhạy cảm có kiểm tra quyền (role) và quyền sở hữu (IDOR).
- [ ] CORS cấu hình đúng origin (ENV), không mở rộng quá mức trên prod.
- [ ] Logging dạng JSON, không lộ secrets, có correlation ID.
- [ ] Tests tối thiểu viết đủ (auth, repo, API), đều pass cục bộ.
- [ ] Migrations đồng bộ với models; seed chạy được.
- [ ] Docker Compose up/down ổn định trên Windows.

---

Phụ lục A: Sơ đồ luồng xác thực (tóm tắt)

1. Client gọi Keycloak để lấy Access Token (OIDC) theo flow phù hợp.
2. Client gọi API Backend kèm `Authorization: Bearer <token>`.
3. Backend lấy JWKS của Keycloak (cache) -> verify JWT (sig + claims).
4. Backend ánh xạ claims -> principal -> kiểm tra quyền/IDOR ở Application layer.
5. Nếu hợp lệ: truy cập Postgres/Milvus; trả kết quả JSON.

Phụ lục B: Gợi ý đặt tên & chuẩn hoá

- Tên module/thư mục dạng snake_case; class PascalCase; biến/hàm snake_case.
- Đơn vị đo/tiền tệ/locale: chuẩn hoá sớm; timezone UTC nội bộ.

Phụ lục C: Kế hoạch mở rộng

- Thêm API rate limiting, metrics (Prometheus), tracing (OpenTelemetry), secrets manager.
- Multi-tenant realm/keycloak hoặc clients tách cho từng ứng dụng.
