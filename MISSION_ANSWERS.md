# Câu trả lời Lab Day 12

## Trạng thái kiểm tra thực tế

- Đã chạy và test Part 1 basic trên Windows PowerShell.
- Đã sửa và kiểm tra Docker Desktop; Docker Engine hiện chạy được.
- Đã build và chạy Docker image Part 2:
  - `my-agent:develop`: `1.66GB`.
  - `my-agent:advanced`: `236MB`.
  - Image advanced nhỏ hơn khoảng `85.8%` và đạt yêu cầu nhỏ hơn `500MB`.
- Đã chạy Docker Compose Part 2 với `agent`, `redis`, `qdrant`, `nginx`; test qua Nginx thành công.
- Đã chạy Part 5 scaling với `3` agent instances, Redis và Nginx; `test_stateless.py` pass khi đặt `PYTHONIOENCODING=utf-8`.
- Đã chạy `python 06-lab-complete/check_production_ready.py`: pass `25/25`.
- Đã tạo Redis service trên Railway, set `REDIS_URL` cho service `agent`, redeploy và kiểm tra Railway public URL:
  - `GET /health` trả `200`.
  - `GET /ready` trả `200`.
  - `POST /ask` không có API key trả `401`.
  - `POST /ask` có API key hợp lệ trả `200`.
  - Rate limit trả `429` sau khi vượt `10` request/phút cho cùng `user_id`.
- Đã có screenshot thật trong `screenshots/`: `dashboard.png`, `running.png`, `test1.png`, `test2.png`.

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

Đã đọc `01-localhost-vs-production/develop/app.py` và tìm thấy các vấn đề:

1. API key bị hardcode trực tiếp trong source code: `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`.
2. Database URL bị hardcode: `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
3. Không có config management; các giá trị như `DEBUG` và `MAX_TOKENS` nằm trực tiếp trong code.
4. App bind vào `host="localhost"`, chỉ phù hợp local, không phù hợp container/cloud.
5. Port bị cố định là `8000`, không đọc từ biến môi trường `PORT`.
6. `reload=True` đang bật, đây là chế độ development, không nên dùng production.
7. Không có `/health` hoặc `/ready`, nên cloud platform không biết app còn sống hay sẵn sàng nhận traffic.
8. Không xử lý graceful shutdown qua `SIGTERM`.
9. Logging dùng `print()` thay vì structured logging.
10. Code còn in secret ra log: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.

### Exercise 1.2: Chạy basic version

Lệnh đã chạy trên Windows PowerShell:

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\01-localhost-vs-production\develop
pip install -r requirements.txt
python app.py
```

Test endpoint:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask?question=Hello" -Method Post
```

Kết quả thực tế:

- App khởi động thành công tại `http://localhost:8000`.
- Trình duyệt mở `/` trả JSON: `{"message":"Hello! Agent is running on my machine :)"}`.
- Endpoint `/ask?question=Hello` trả `200 OK`.
- Server log có ghi:
  - `[DEBUG] Got question: Hello`
  - `[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this`
  - `POST /ask?question=Hello HTTP/1.1" 200 OK`

Kết luận: app chạy được ở local, nhưng chưa production-ready vì vẫn hardcode secret, không có health check, không có graceful shutdown và log chưa an toàn.

### Exercise 1.3: So sánh basic và advanced

| Feature | Basic | Advanced | Tại sao quan trọng? |
|---------|-------|----------|---------------------|
| Config | Hardcode trong code | Đọc từ env vars qua `config.py` và `.env` | Cùng code có thể chạy ở local, staging, production |
| Secrets | Nằm trong source code và bị log ra ngoài | Đọc từ environment, không log secret | Tránh lộ API key/database URL |
| Host | `localhost` | `0.0.0.0` | Container/cloud cần nhận request từ bên ngoài process |
| Port | Cố định `8000` | Đọc từ `PORT` env var | Railway/Render thường inject port |
| Debug/reload | `reload=True` | Chỉ bật khi `DEBUG=true` | Tránh behavior dev trong production |
| Health check | Không có | Có `/health` | Platform có thể kiểm tra app còn sống |
| Readiness check | Không có | Có `/ready` | Load balancer biết khi nào app sẵn sàng nhận traffic |
| Logging | `print()` plain text | JSON structured logging | Dễ search, parse và giám sát |
| Shutdown | Không xử lý `SIGTERM` | Có signal handler/lifespan cleanup | Giảm rủi ro mất request khi container dừng |

---

## Part 2: Docker Containerization

### Exercise 2.1: Dockerfile cơ bản

Đã đọc `02-docker/develop/Dockerfile`.

1. Base image: `python:3.11`.
2. Working directory: `/app`.
3. `COPY requirements.txt` trước để tận dụng Docker layer cache; nếu code đổi nhưng dependencies không đổi thì Docker không cần cài lại packages.
4. `CMD` là lệnh mặc định khi container start và có thể bị ghi đè khi `docker run`; `ENTRYPOINT` cố định executable chính hơn, thường dùng khi muốn container luôn chạy một chương trình cụ thể.

### Exercise 2.2: Build và run basic image

Lệnh đã chạy:

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run --rm -d --name day12-test-develop -p 8000:8000 my-agent:develop
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/ask?question=What%20is%20Docker" -Method Post
docker stop day12-test-develop
```

Kết quả:

- `/health` trả `200`, body có `status: ok`, `container: True`.
- `/ask?question=What is Docker` trả `200`.
- Log container ghi `POST /ask?question=What%20is%20Docker HTTP/1.1" 200 OK`.
- Image size: `my-agent:develop = 1.66GB`.

### Exercise 2.3: Multi-stage build

Đã đọc và sửa `02-docker/production/Dockerfile` flow bằng cách bổ sung file còn thiếu `02-docker/production/requirements.txt`.

- Stage 1 `builder`: dùng `python:3.11-slim`, cài build tools như `gcc`, `libpq-dev`, sau đó cài dependencies vào `/root/.local`.
- Stage 2 `runtime`: dùng image sạch hơn, copy dependencies từ builder, copy app code, tạo non-root user `appuser`, thêm healthcheck và chạy bằng `uvicorn`.
- Image nhỏ hơn vì runtime stage không giữ lại build tools và layer không cần thiết từ quá trình build.

Lệnh đã chạy:

```powershell
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker run --rm -d --name day12-test-advanced -p 8000:8000 -e ENVIRONMENT=production my-agent:advanced
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/ready"
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method Post -ContentType "application/json" -Body '{"question":"Explain multi-stage Docker"}'
docker stop day12-test-advanced
docker images my-agent
```

Kết quả:

- `/health` trả `200`.
- `/ready` trả `200`.
- `/ask` trả `200`.
- Image size: `my-agent:advanced = 236MB`.
- So sánh: develop `1.66GB`, advanced `236MB`, giảm khoảng `85.8%`.

### Exercise 2.4: Docker Compose stack

Đã đọc và sửa `02-docker/production/docker-compose.yml`:

- Sửa `build.context` để Dockerfile build từ repo root đúng với các lệnh `COPY`.
- Sửa Qdrant healthcheck vì image `qdrant/qdrant:v1.9.0` không có `curl`; dùng TCP check qua `/bin/bash` thay thế.
- Tạo `.env.local` local bị `.gitignore` bỏ qua để compose chạy được.

Các service chạy:

- `agent`: FastAPI AI agent.
- `redis`: cache/session/rate limiting backend.
- `qdrant`: vector database.
- `nginx`: reverse proxy/load balancer, expose port `80` và `443`.

Luồng kiến trúc:

```text
Client -> Nginx -> Agent -> Redis
                  Agent -> Qdrant
```

Lệnh đã chạy:

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\02-docker\production
docker compose up -d
Invoke-RestMethod -Uri "http://localhost/health"
Invoke-RestMethod -Uri "http://localhost/ask" -Method Post -ContentType "application/json" -Body '{"question":"Explain microservices"}'
docker compose ps
```

Kết quả:

- `production-agent-1`: `healthy`.
- `production-redis-1`: `healthy`.
- `production-qdrant-1`: `healthy`.
- `production-nginx-1`: chạy và expose `80:80`, `443:443`.
- `GET http://localhost/health`: `200`.
- `POST http://localhost/ask`: `200`.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

Public URL:

```text
https://agent-production-b973.up.railway.app
```

Kết quả kiểm tra thực tế:

- `/health`: `200`, body có `{"status":"ok", ...}`.
- `/ready`: `200`, body có `{"status":"ready"}`.
- `/ask` không có API key: `401`.
- `/ask` có API key hợp lệ: `200`.

Đã có screenshot Railway dashboard và kết quả test trong thư mục `screenshots/`.

### Exercise 3.2: Render vs Railway config

Đã đọc `03-cloud-deployment/railway/railway.toml` và `03-cloud-deployment/render/render.yaml`.

- `railway.toml` ngắn gọn, tập trung vào start command, healthcheck path và restart policy.
- `render.yaml` khai báo hạ tầng đầy đủ hơn theo Blueprint: web service, region, plan, build command, start command, env vars và Redis service.
- Railway phù hợp deploy nhanh bằng CLI.
- Render phù hợp quản lý service theo file YAML gắn với GitHub.

Trạng thái: chưa deploy Render vì yêu cầu lab chỉ cần deploy thành công ít nhất một platform; platform đã dùng là Railway.

### Exercise 3.3: GCP Cloud Run

Đã đọc ý nghĩa cấu hình ở `03-cloud-deployment/production-cloud-run/cloudbuild.yaml` và `service.yaml`.

- `cloudbuild.yaml`: mô tả pipeline build/deploy tự động.
- `service.yaml`: mô tả Cloud Run service, container, port và cấu hình runtime.

Trạng thái: optional, chưa deploy GCP Cloud Run.

---

## Part 4: API Security

### Exercise 4.1: API Key authentication

Đã đọc `04-api-gateway/develop/app.py`.

- API key được đọc từ `AGENT_API_KEY`, fallback là `demo-key-change-in-production`.
- Header được kiểm tra bằng `APIKeyHeader(name="X-API-Key", auto_error=False)`.
- Logic check nằm trong function `verify_api_key`.
- Nếu thiếu key: trả `401`.
- Nếu sai key: trả `403`.
- Muốn rotate key: đổi biến môi trường `AGENT_API_KEY` rồi restart/redeploy app.

### Exercise 4.2: JWT authentication

Đã đọc `04-api-gateway/production/auth.py` và `app.py`.

JWT flow:

1. User gửi username/password tới `POST /auth/token`.
2. Server gọi `authenticate_user`.
3. Nếu đúng credential, server tạo JWT bằng `create_token`.
4. Client gửi token ở header `Authorization: Bearer <token>`.
5. Server gọi `verify_token`, kiểm tra signature/expiry rồi lấy `username` và `role`.

Demo users trong code:

- `student / demo123`: role `user`.
- `teacher / teach456`: role `admin`.

Lưu ý: trong `CODE_LAB.md` có chỗ ghi `/token`, nhưng code thực tế dùng `/auth/token`.

### Exercise 4.3: Rate limiting

Đã đọc `04-api-gateway/production/rate_limiter.py`.

- Algorithm: Sliding Window Counter bằng `deque` trong memory.
- User thường: `10 requests / 60 giây`.
- Admin: `100 requests / 60 giây`.
- Admin không bypass hoàn toàn, nhưng dùng limiter rộng hơn: `rate_limiter_admin`.
- Khi vượt limit, app trả `429 Too Many Requests`.

Kết quả cloud thực tế sau khi cấu hình Redis trên Railway:

```text
200,200,200,200,200,200,200,200,200,200,429,429
```

Kết luận: rate limiting trên cloud đã được xác minh; vượt quá 10 request/phút thì trả `429`.

### Exercise 4.4: Cost guard

Đã đọc `04-api-gateway/production/cost_guard.py`.

- Demo trong Part 4 dùng in-memory `CostGuard`, không phải Redis.
- Theo dõi usage theo ngày bằng `UsageRecord`.
- Tính chi phí từ input/output tokens.
- Per-user budget mặc định: `$1/day`.
- Global budget mặc định: `$10/day`.
- Nếu user vượt budget: trả `402`.
- Nếu global budget vượt: trả `503`.

Bản final ở `06-lab-complete/app/cost_guard.py` dùng Redis hoặc fallback memory với key dạng `budget:{user_id}:{YYYY-MM}` và giới hạn `$10/month` theo yêu cầu Part 6.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks

Đã đọc `05-scaling-reliability/develop/app.py`.

- `/health`: liveness probe, trả status, uptime, version, environment, timestamp và memory check nếu có `psutil`.
- `/ready`: readiness probe, trả `503` nếu app chưa ready; trả ready khi startup xong.

### Exercise 5.2: Graceful shutdown

Trong `05-scaling-reliability/develop/app.py`:

- App dùng lifespan startup/shutdown.
- Biến `_is_ready` chuyển về `False` khi shutdown.
- Biến `_in_flight_requests` đếm request đang xử lý.
- Signal handler xử lý `SIGTERM` và `SIGINT`.
- `uvicorn.run(..., timeout_graceful_shutdown=30)` cho phép chờ request đang chạy hoàn tất.

### Exercise 5.3: Stateless design

Đã đọc `05-scaling-reliability/production/app.py`.

- State conversation được lưu bằng session storage.
- Nếu Redis khả dụng, session lưu vào Redis với key `session:{session_id}`.
- Nếu Redis không khả dụng, app fallback sang `_memory_store`, nhưng code có cảnh báo đây không scalable.
- Endpoint chính là `POST /chat`.

### Exercise 5.4: Load balancing

Đã bổ sung file còn thiếu để chạy được stack Part 5:

- `05-scaling-reliability/production/Dockerfile`.
- `05-scaling-reliability/production/requirements.txt`.
- `.env.local` local, bị `.gitignore` bỏ qua.
- Sửa `docker-compose.yml` trỏ đúng Dockerfile.

Lệnh đã chạy:

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\05-scaling-reliability\production
docker compose -p day12-scaling up -d --scale agent=3
Invoke-RestMethod -Uri "http://localhost:8080/health"
docker compose -p day12-scaling ps
```

Kết quả:

- `day12-scaling-agent-1`: `healthy`.
- `day12-scaling-agent-2`: `healthy`.
- `day12-scaling-agent-3`: `healthy`.
- `day12-scaling-redis-1`: `healthy`.
- `day12-scaling-nginx-1`: expose `8080:80`.
- `/health` trả `200`, storage là `redis`, `redis_connected: True`.

Test 10 requests cho thấy request được phân tán qua nhiều instance:

```text
instance-15ea9e redis
instance-15ea9e redis
instance-886ae1 redis
instance-886ae1 redis
instance-076b2b redis
instance-886ae1 redis
instance-15ea9e redis
instance-076b2b redis
instance-886ae1 redis
instance-15ea9e redis
```

### Exercise 5.5: Test stateless

Lệnh đã chạy:

```powershell
$env:PYTHONIOENCODING='utf-8'
python test_stateless.py
```

Kết quả:

- Script tạo session mới thành công.
- 5 requests được serve bởi 3 instances khác nhau:
  - `instance-076b2b`
  - `instance-886ae1`
  - `instance-15ea9e`
- Conversation history có `10` messages.
- Script kết luận: `Session history preserved across all instances via Redis`.

Ghi chú: chạy script không có `PYTHONIOENCODING=utf-8` trên Windows có thể gặp `UnicodeEncodeError` khi in tiếng Việt; đây là lỗi console encoding, không phải lỗi service.

---

## Part 6: Final Project

Hoàn thành trong `06-lab-complete`:

- Có `Dockerfile` multi-stage.
- Có `docker-compose.yml`.
- Có `.dockerignore`.
- Có `.env.example`.
- Có `app/main.py`, `app/config.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`.
- Có health endpoint `/health`.
- Có readiness endpoint `/ready`.
- Có API key authentication.
- Có rate limiting.
- Có cost guard.
- Có structured JSON logging.
- Có graceful shutdown qua `SIGTERM`.
- Có Railway/Render config.
- Có Redis-backed stateless conversation history.

Kết quả kiểm tra local Docker final:

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\06-lab-complete
docker compose up -d
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/ready"
```

Kết quả:

- `/health`: `200`.
- `/ready`: `200`.
- Không có API key: `401`.
- Có API key hợp lệ: `200`.
- Rate limit local: `200` x10, sau đó `429`, `429`.
- Image `06-lab-complete-agent`: `255MB`.

Kết quả checker:

```powershell
python check_production_ready.py
```

```text
Result: 25/25 checks passed (100%)
Status: PRODUCTION READY
```

Kiểm tra Railway thật:

- `GET /health`: `200`.
- `GET /ready`: `200`.
- `POST /ask` không API key: `401`.
- `POST /ask` có API key: `200`.
- Rate limit: request 11 và 12 với cùng `user_id` trả `429`.

---

## Việc cần tự kiểm tra trước khi nộp

1. Kiểm tra lại ảnh `screenshots/test2.png`; nếu ảnh có hiển thị API key thì crop hoặc che phần key trước khi nộp.
2. Đảm bảo GitHub repository public hoặc instructor có quyền truy cập.
3. Đảm bảo không commit file `.env`, `.env.local`, `.env.production`; `.gitignore` hiện đã ignore các file này.
4. Nếu API key từng bị đẩy lên GitHub hoặc chia sẻ ra ngoài, nên rotate key trước khi nộp.
