# Thông Tin Triển Khai

## Public URL

```text
https://agent-production-b973.up.railway.app
```

## Nền tảng

Railway

## Trạng thái triển khai

- Service chính: `agent`.
- Database/cache: Railway Redis service.
- Public URL hoạt động.
- `/health` trả `200`.
- `/ready` trả `200`.
- `/ask` yêu cầu API key.
- Rate limit hoạt động với giới hạn `10` request/phút/user.

## Lệnh kiểm tra Railway

### Health Check

```bash
curl https://agent-production-b973.up.railway.app/health
# Kỳ vọng: 200, body có "status":"ok"
```

PowerShell:

```powershell
Invoke-WebRequest -Uri "https://agent-production-b973.up.railway.app/health" -UseBasicParsing
```

Kết quả đã xác minh:

```text
StatusCode: 200
Content: {"status":"ok", ...}
```

### Ready Check

```bash
curl https://agent-production-b973.up.railway.app/ready
# Kỳ vọng: 200, body có "status":"ready"
```

PowerShell:

```powershell
Invoke-WebRequest -Uri "https://agent-production-b973.up.railway.app/ready" -UseBasicParsing
```

Kết quả đã xác minh:

```text
StatusCode: 200
Content: {"status":"ready"}
```

### Kiểm tra API không xác thực

```bash
curl -X POST https://agent-production-b973.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","question":"hello"}'
# Kỳ vọng: 401
```

Kết quả đã xác minh:

```text
StatusCode: 401
```

### Kiểm tra API có xác thực

```bash
curl -X POST https://agent-production-b973.up.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","question":"hello"}'
# Kỳ vọng: 200
```

PowerShell:

```powershell
Invoke-WebRequest -Uri "https://agent-production-b973.up.railway.app/ask" `
  -Method Post `
  -Headers @{"X-API-Key"="YOUR_KEY"} `
  -ContentType "application/json" `
  -Body '{"user_id":"demo","question":"hello"}' `
  -UseBasicParsing
```

Kết quả đã xác minh:

```text
StatusCode: 200
Content: {"user_id":"...","question":"hello","answer":"...","model":"gpt-4o-mini", ...}
```

### Kiểm tra Rate Limit

```bash
for i in {1..20}; do
  curl -X POST https://agent-production-b973.up.railway.app/ask \
    -H "X-API-Key: YOUR_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"rate-user-cloud\",\"question\":\"q$i\"}"
done
# Kỳ vọng: sau 10 request/phút sẽ nhận 429
```

Kết quả đã xác minh:

```text
200,200,200,200,200,200,200,200,200,200,429,429
```

## Biến môi trường đã cấu hình trên Railway

- `ENVIRONMENT=production`
- `AGENT_API_KEY`
- `JWT_SECRET`
- `REDIS_URL` từ Railway Redis service
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10`
- `LOG_LEVEL=INFO`

Không ghi giá trị secret thật vào file nộp bài.

## Kiểm tra local bằng Docker

### Part 2 Docker images

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
```

Kết quả:

```text
my-agent:develop    1.66GB
my-agent:advanced   236MB
```

### Part 2 Docker Compose

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\02-docker\production
docker compose up -d
Invoke-RestMethod -Uri "http://localhost/health"
Invoke-RestMethod -Uri "http://localhost/ask" -Method Post -ContentType "application/json" -Body '{"question":"Explain microservices"}'
docker compose ps
```

Kết quả:

- `agent`: healthy.
- `redis`: healthy.
- `qdrant`: healthy.
- `nginx`: running.
- `GET /health`: `200`.
- `POST /ask`: `200`.

### Part 5 Scaling

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\05-scaling-reliability\production
docker compose -p day12-scaling up -d --scale agent=3
Invoke-RestMethod -Uri "http://localhost:8080/health"
$env:PYTHONIOENCODING='utf-8'
python test_stateless.py
```

Kết quả:

- 3 agent instances chạy healthy.
- Redis healthy.
- Nginx expose port `8080`.
- Requests được phân tán qua nhiều instance.
- Session history vẫn giữ nguyên trong Redis.

### Final Project

```powershell
cd D:\Vin\assignments\day12_ha-tang-cloud_va_deployment\06-lab-complete
docker compose up -d
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/ready"
python check_production_ready.py
```

Kết quả:

```text
Result: 25/25 checks passed (100%)
Status: PRODUCTION READY
```

## Ảnh chụp màn hình

- [Bảng điều khiển deployment](screenshots/dashboard.png)
- [Service đang chạy](screenshots/running.png)
- [Kết quả kiểm tra health và ready](screenshots/test1.png)
- [Kết quả kiểm tra API ask](screenshots/test2.png)

Lưu ý: nếu ảnh test có hiển thị API key, hãy che hoặc crop phần key trước khi nộp.

## Ghi chú bảo mật

- Không commit `.env`, `.env.local`, `.env.production`.
- File `.gitignore` đã ignore các file env local.
- Trong tài liệu nộp bài chỉ dùng placeholder `YOUR_KEY`, không ghi API key thật.
