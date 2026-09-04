# EC2 Web Service Runbook

KORStockScan 웹 대시보드를 EC2에서 외부 서비스로 운영할 때의 기준 절차입니다.

## 권장 구조

`Domain -> Elastic IP -> Nginx(80/443) -> Gunicorn(127.0.0.1:5000) -> Flask`

핵심 원칙:

- Flask 개발 서버는 외부 공개용으로 쓰지 않습니다.
- 외부 공개 포트는 `80`, `443`만 사용합니다.
- Gunicorn은 `127.0.0.1:5000`에서만 수신합니다.
- TLS는 `certbot --nginx`로 관리합니다.

## 사전 준비

- EC2에 `Elastic IP` 연결
- 도메인 또는 DDNS를 Elastic IP로 연결
- 보안그룹 인바운드 허용
  - `80/tcp` from `0.0.0.0/0`
  - `443/tcp` from `0.0.0.0/0`
  - `22/tcp` from 관리자 IP only
- 아웃바운드는 기본 허용 유지

## 패키지 설치

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
/home/ubuntu/KORStockScan/.venv/bin/pip install gunicorn
```

## Gunicorn systemd 서비스

참고 파일:

- `deploy/systemd/korstockscan-gunicorn.service`

서버 반영:

```bash
sudo cp deploy/systemd/korstockscan-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now korstockscan-gunicorn.service
sudo systemctl status korstockscan-gunicorn.service
```

코드 반영 후 재시작:

```bash
sudo systemctl restart korstockscan-gunicorn.service
sudo systemctl status korstockscan-gunicorn.service
```

현재 서비스 파일에는 `ExecReload`가 없으므로 `reload` 대신 `restart`를 기준으로 운영합니다.

직접 실행 확인:

```bash
cd /home/ubuntu/KORStockScan
PYTHONPATH=/home/ubuntu/KORStockScan /home/ubuntu/KORStockScan/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 src.web.app:app
```

포트 충돌이 나면 기존 Flask 서비스가 `5000`을 점유하고 있는지 확인합니다.

```bash
sudo lsof -i :5000
sudo systemctl stop korstockscan-web.service
sudo systemctl disable korstockscan-web.service
```

## Nginx reverse proxy

참고 파일:

- `deploy/nginx/korstockscan.conf`

서버 반영:

```bash
sudo cp deploy/nginx/korstockscan.conf /etc/nginx/sites-available/korstockscan
```

도메인을 실제 값으로 수정한 뒤:

```bash
sudo ln -s /etc/nginx/sites-available/korstockscan /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl status nginx
```

HTTP 확인:

```bash
curl -I http://127.0.0.1
curl -I http://YOUR_DOMAIN_HERE
```

## TLS / HTTPS

인증서 발급:

```bash
sudo certbot --nginx -d YOUR_DOMAIN_HERE
```

권장 선택:

- 이메일 입력
- 약관 동의
- HTTP -> HTTPS redirect 활성화

확인:

```bash
sudo certbot certificates
curl -Ik https://YOUR_DOMAIN_HERE
```

자동 갱신 테스트:

```bash
sudo certbot renew --dry-run
```

## 점검 명령

애플리케이션:

```bash
sudo systemctl status korstockscan-gunicorn.service
sudo journalctl -u korstockscan-gunicorn.service -f
```

리버스프록시:

```bash
sudo systemctl status nginx
sudo journalctl -u nginx -f
```

네트워크:

```bash
sudo ss -tlnp | grep 443
sudo ss -tlnp | grep 5000
```

## 현재 주요 웹 경로

- 일일 리포트: `/` 또는 `/daily-report`
- 진입 게이트 플로우: `/entry-pipeline-flow`
- 실시간 매매 복기: `/trade-review`

## 주요 API

- `/api/daily-report`
- `/api/entry-pipeline-flow`
- `/api/trade-review`
- `/api/strength-momentum`

Flutter나 외부 프론트는 위 API를 그대로 사용하는 것을 기준으로 합니다.

상세 응답 필드 가이드는 [web_api_spec_guide.md](web_api_spec_guide.md)를 참고합니다.

특히 `/api/entry-pipeline-flow`는 최신 버전에서 아래 기준을 따릅니다.

- `recent_stocks`는 재진입 종목도 `최신 시도 세그먼트`만 반환
- 각 row에 `record_id`, `attempt_started_at` 포함
- `pass_flow`와 `confirmed_failure`는 최신 시도 기준으로 계산

## 트러블슈팅

### 1. Gunicorn 시작 실패

확인:

```bash
sudo systemctl status korstockscan-gunicorn.service
sudo journalctl -u korstockscan-gunicorn.service -n 50 --no-pager
```

가장 흔한 원인:

- `127.0.0.1:5000` 이미 사용 중
- `.venv` 패키지 누락
- `PYTHONPATH` 누락

### 2. HTTPS 인증서는 발급됐는데 외부 접속 실패

확인 순서:

```bash
curl -Ik https://127.0.0.1
curl -Ik --resolve YOUR_DOMAIN_HERE:443:127.0.0.1 https://YOUR_DOMAIN_HERE
dig +short YOUR_DOMAIN_HERE A
```

위 두 `curl`이 성공하면 서버 설정은 정상이고, DNS 또는 외부 네트워크 문제일 가능성이 큽니다.

### 3. 보안그룹/NACL 확인

보안그룹:

- `80/tcp` 허용
- `443/tcp` 허용

NACL:

- 기본 허용형이면 보통 문제 없음
- 커스텀 NACL이면 `443`과 응답 포트 대역까지 확인
