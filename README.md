# Day 12 - Cloud Infrastructure and Deployment

Repository bài lab Day 12 về triển khai AI agent lên môi trường production.

Bài này tập trung vào các kỹ năng deployment/backend infrastructure:

- Phân biệt môi trường localhost và production.
- Dockerize ứng dụng bằng Docker và Docker Compose.
- Deploy service lên cloud bằng Railway.
- Bảo vệ API bằng API key authentication.
- Rate limiting để giới hạn request.
- Cost guard để tránh vượt ngân sách.
- Health check, readiness check và graceful shutdown.
- Stateless design với Redis.
- Load balancing bằng Nginx.

Lưu ý: toàn bộ lab đang dùng mock LLM, không gọi OpenAI/Anthropic thật. Điều này đúng với yêu cầu của `CODE_LAB.md`, vì lab không yêu cầu OpenAI API key.

---

## Trạng Thái Hoàn Thành

- Part 1: đã chạy local basic app và phân tích anti-patterns.
- Part 2: đã build Docker image develop và advanced.
- Part 2: đã chạy Docker Compose stack gồm agent, Redis, Qdrant và Nginx.
- Part 3: đã deploy lên Railway.
- Part 4: đã kiểm tra authentication, rate limiting và cost guard.
- Part 5: đã chạy scaling demo với 3 agent instances, Redis và Nginx.
- Part 6: final production agent trong `06-lab-complete` đã pass readiness checker `25/25`.

Public URL:

```text
https://agent-production-b973.up.railway.app
```

Kết quả kiểm tra chính:

```text
GET  /health  -> 200
GET  /ready   -> 200
POST /ask     -> 401 nếu thiếu API key
POST /ask     -> 200 nếu có API key hợp lệ
Rate limit    -> 429 sau khi vượt 10 request/phút/user
```

---

## Cấu Trúc Project

```text
day12_ha-tang-cloud_va_deployment/
├── 01-localhost-vs-production/
│   ├── develop/                 # App local cơ bản, có nhiều anti-pattern
│   └── production/              # Bản advanced theo 12-factor app
├── 02-docker/
│   ├── develop/                 # Dockerfile single-stage
│   └── production/              # Multi-stage Dockerfile + Compose stack
├── 03-cloud-deployment/
│   ├── railway/                 # Cấu hình Railway
│   ├── render/                  # Cấu hình Render
│   └── production-cloud-run/    # Ví dụ Cloud Run
├── 04-api-gateway/
│   ├── develop/                 # API key authentication
│   └── production/              # JWT, rate limit, cost guard
├── 05-scaling-reliability/
│   ├── develop/                 # Health check và graceful shutdown
│   └── production/              # Stateless Redis + Nginx load balancer
├── 06-lab-complete/             # Final production-ready agent
├── screenshots/                 # Ảnh chụp kết quả deploy/test
├── CODE_LAB.md                  # Hướng dẫn lab
├── DAY12_DELIVERY_CHECKLIST.md  # Checklist nộp bài
├── MISSION_ANSWERS.md           # Câu trả lời các bài tập
└── DEPLOYMENT.md                # Thông tin deploy public service
```

---

## Tài Liệu Quan Trọng

- `CODE_LAB.md`: hướng dẫn làm từng phần của lab.
- `DAY12_DELIVERY_CHECKLIST.md`: tiêu chí nộp bài.
- `MISSION_ANSWERS.md`: câu trả lời và kết quả kiểm tra từng exercise.
- `DEPLOYMENT.md`: public URL, test commands, environment variables và screenshots.
- `06-lab-complete/README.md`: hướng dẫn riêng cho final production agent.

---

## Yêu Cầu Môi Trường

- Python 3.11 trở lên.
- Docker Desktop.
- Docker Compose.
- Git.
- PowerShell hoặc terminal tương đương.
- Railway CLI nếu muốn deploy lại.

Không cần OpenAI API key thật vì lab dùng mock LLM.

---

## Chạy Nhanh Final Project

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\06-lab-complete
docker compose up -d
```

Kiểm tra health và readiness:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/ready"
```

Kiểm tra API không có key, kỳ vọng `401`:

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/ask" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"user_id":"demo","question":"hello"}' `
  -UseBasicParsing
```

Kiểm tra API có key:

```powershell
$key = (Get-Content .env | Where-Object { $_ -match '^AGENT_API_KEY=' } | Select-Object -First 1) -replace '^AGENT_API_KEY=', ''

Invoke-RestMethod -Uri "http://localhost:8000/ask" `
  -Method Post `
  -Headers @{"X-API-Key"=$key} `
  -ContentType "application/json" `
  -Body '{"user_id":"demo","question":"hello"}'
```

Dừng stack:

```powershell
docker compose down
```

---

## Kiểm Tra Production Readiness

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\06-lab-complete
python check_production_ready.py
```

Kết quả đã kiểm tra:

```text
Result: 25/25 checks passed (100%)
Status: PRODUCTION READY
```

---

## Docker Image Size

Lệnh build:

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
```

Kết quả đã kiểm tra:

```text
my-agent:develop    1.66GB
my-agent:advanced   236MB
```

Image advanced dùng multi-stage build và nhỏ hơn khoảng `85.8%`.

---

## Docker Compose Part 2

Chạy stack Docker production demo:

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\02-docker\production
docker compose up -d
docker compose ps
```

Test qua Nginx:

```powershell
Invoke-RestMethod -Uri "http://localhost/health"

Invoke-RestMethod -Uri "http://localhost/ask" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"question":"Explain microservices"}'
```

Các service đã kiểm tra:

- `agent`: healthy.
- `redis`: healthy.
- `qdrant`: healthy.
- `nginx`: running.

Dừng stack:

```powershell
docker compose down
```

---

## Scaling Demo Part 5

Chạy 3 agent instances sau Nginx load balancer:

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\05-scaling-reliability\production
docker compose -p day12-scaling up -d --scale agent=3
docker compose -p day12-scaling ps
```

Test stateless session với Redis:

```powershell
$env:PYTHONIOENCODING='utf-8'
python test_stateless.py
```

Kết quả đã kiểm tra:

- Requests được phục vụ bởi nhiều instance khác nhau.
- Conversation history vẫn được giữ trong Redis.
- Stateless design hoạt động đúng khi scale nhiều instance.

Dừng stack:

```powershell
docker compose -p day12-scaling down
```

---

## Railway Deployment

Thông tin chi tiết nằm trong `DEPLOYMENT.md`.

Public URL:

```text
https://agent-production-b973.up.railway.app
```

Các biến môi trường đã cấu hình trên Railway:

- `ENVIRONMENT=production`
- `AGENT_API_KEY`
- `JWT_SECRET`
- `REDIS_URL`
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10`
- `LOG_LEVEL=INFO`

Redis được cấu hình bằng Railway managed Redis service.

---

## Screenshots

Các ảnh bằng chứng nằm trong thư mục `screenshots/`:

- `screenshots/dashboard.png`: Railway dashboard.
- `screenshots/running.png`: service đang chạy.
- `screenshots/test1.png`: kết quả `/health` và `/ready`.
- `screenshots/test2.png`: kết quả gọi `/ask`.

Nếu ảnh test có hiển thị API key thật, cần crop hoặc che key trước khi nộp.

---

## Bảo Mật

Không commit các file sau:

```text
.env
.env.local
.env.production
```

Repo đã cấu hình `.gitignore` để bỏ qua các file env local.

Trong tài liệu nộp bài chỉ dùng placeholder như `YOUR_KEY`, không ghi API key thật.

---

## Nộp Bài

Theo `DAY12_DELIVERY_CHECKLIST.md`, repository cần có:

- `MISSION_ANSWERS.md`
- `DEPLOYMENT.md`
- Source code final trong `06-lab-complete/`
- Screenshot trong `screenshots/`
- `.env.example`, không commit `.env`
- Public URL hoạt động
- README hướng dẫn rõ ràng

Trước khi nộp, kiểm tra lại:

```powershell
git status --short
git check-ignore -v 06-lab-complete/.env
```

Đảm bảo repository public hoặc giảng viên có quyền truy cập.
