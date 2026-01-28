# 🚀 Деплой PBgroup CRM на VPS

## Предварительные требования

- VPS с Ubuntu 22.04+
- Минимум 2GB RAM, 1 vCPU
- Доменное имя (опционально)

## Быстрый старт (Docker)

### 1. Установка Docker на VPS

```bash
# Подключаемся к VPS
ssh root@your-vps-ip

# Устанавливаем Docker
curl -fsSL https://get.docker.com | sh

# Устанавливаем Docker Compose
apt install docker-compose-plugin -y
```

### 2. Клонируем репозиторий

```bash
cd /var/www
git clone https://github.com/Alfirs/pbgroup-mini-crm.git pbgroup-crm
cd pbgroup-crm
```

### 3. Настраиваем окружение

```bash
# Копируем пример окружения
cp .env.example .env

# Редактируем переменные
nano .env
```

**Важные переменные:**
```env
DATABASE_URL=postgresql://postgres:YOUR_SECURE_PASSWORD@db:5432/pbgroup_crm?schema=public
NEXTAUTH_SECRET=GENERATE_RANDOM_SECRET_HERE
NEXTAUTH_URL=https://your-domain.com
```

Сгенерировать секрет:
```bash
openssl rand -base64 32
```

### 4. Запускаем

```bash
docker compose up -d --build

# Применить миграции
docker compose exec app npx prisma migrate deploy

# Создать админа
docker compose exec app npx prisma db seed
```

### 5. Настраиваем Nginx (SSL)

```bash
apt install nginx certbot python3-certbot-nginx -y

# Создаем конфиг
nano /etc/nginx/sites-available/pbgroup-crm
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
# Активируем сайт
ln -s /etc/nginx/sites-available/pbgroup-crm /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Получаем SSL
certbot --nginx -d your-domain.com
```

---

## Автоматический деплой (GitHub Actions)

### Настройка секретов в GitHub

Перейдите в репозиторий → Settings → Secrets → Actions и добавьте:

| Secret | Значение |
|--------|----------|
| `VPS_HOST` | IP адрес VPS |
| `VPS_USER` | `root` или ваш пользователь |
| `VPS_SSH_KEY` | Приватный SSH ключ |
| `VPS_PORT` | `22` (или ваш порт) |

### Генерация SSH ключа

```bash
# На локальной машине
ssh-keygen -t ed25519 -C "github-deploy"

# Копируем публичный ключ на VPS
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@your-vps-ip

# Приватный ключ добавляем в GitHub Secrets
cat ~/.ssh/id_ed25519
```

---

## Откат версии

```bash
cd /var/www/pbgroup-crm

# Посмотреть историю
git log --oneline -10

# Откатиться к коммиту
git checkout abc123

# Пересобрать
docker compose up -d --build
```

---

## Полезные команды

```bash
# Логи приложения
docker compose logs -f app

# Перезапуск
docker compose restart app

# Остановить всё
docker compose down

# Бэкап базы
docker compose exec db pg_dump -U postgres pbgroup_crm > backup.sql

# Восстановление базы
cat backup.sql | docker compose exec -T db psql -U postgres pbgroup_crm
```
