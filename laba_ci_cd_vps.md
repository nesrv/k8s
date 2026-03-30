# Методическое указание

## Лабораторная: CI/CD и деплой на VPS

## 1. Цель работы

Научиться собирать и публиковать Docker-образ через CI, затем автоматически выкатывать приложение на VPS через CD.

---

## 2. Что получите в итоге

- после `git push` запускается CI-пайплайн;
- проходят проверки и собирается образ;
- образ публикуется в registry;
- на VPS выполняется деплой новой версии;
- при проблеме можно сделать rollback.

---

## 3. Архитектура (учебный минимум)

- GitHub-репозиторий;
- GitHub Actions (CI/CD);
- Docker Hub (или GHCR) как registry;
- VPS (Ubuntu) + Docker + Docker Compose;
- приложение FastAPI в контейнере.

---

## 4. Подготовка репозитория

Минимальная структура:

```text
project/
  app/
    main.py
  requirements.txt
  Dockerfile
  docker-compose.yml
  .github/
    workflows/
      ci-cd.yml
```

---

## 5. Подготовка VPS

На VPS (Ubuntu):

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

Создайте рабочий каталог, например `/opt/lab-app`.

---

## 6. docker-compose.yml на VPS

Пример:

```yaml
services:
  web:
    image: DOCKERHUB_USERNAME/lab1-api:latest
    container_name: lab1-api
    restart: unless-stopped
    ports:
      - "80:8000"
```

Пояснение:

- `restart: unless-stopped` поднимет контейнер после перезапуска VPS;
- тег `latest` удобен для учебного CD, но в проде лучше фиксированные версии (`v1.2.3`).

---

## 7. Секреты в GitHub

В репозитории добавьте Secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`

Опционально:

- `VPS_PORT` (если SSH не на 22)

---

## 8. CI/CD workflow (GitHub Actions)

Файл: `.github/workflows/ci-cd.yml`

```yaml
name: CI-CD

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Smoke import
        run: python -c "import fastapi; import uvicorn; print('ok')"

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKERHUB_USERNAME }}/lab1-api:latest
            ${{ secrets.DOCKERHUB_USERNAME }}/lab1-api:${{ github.sha }}

  cd:
    needs: ci
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/lab-app
            docker compose pull
            docker compose up -d
            docker image prune -f
```

---

## 9. Первый ручной запуск на VPS

Перед автоматическим CD подготовьте VPS один раз:

```bash
mkdir -p /opt/lab-app
cd /opt/lab-app
# вставьте docker-compose.yml
docker compose pull
docker compose up -d
docker ps
```

Проверьте в браузере: `http://<VPS_IP>/docs`.

---

## 10. Демонстрация CI/CD на занятии

1. Измените строку в `main.py` (например, версию ответа).
2. Сделайте commit и push в `main`.
3. Покажите Actions:
   - job `ci` прошел,
   - job `cd` прошел.
4. На VPS:

```bash
docker ps
docker logs lab1-api --tail 50
```

5. Откройте `http://<VPS_IP>/` и покажите новую версию.

---

## 11. Rollback (обязательно знать)

Если последняя версия сломана:

1. Найдите предыдущий рабочий тег (например, SHA).
2. На VPS в `docker-compose.yml` временно поставьте этот тег:

```yaml
image: DOCKERHUB_USERNAME/lab1-api:<OLD_SHA>
```

3. Примените:

```bash
docker compose pull
docker compose up -d
```

---

## 12. Типичные ошибки

| Симптом | Причина | Что делать |
|---|---|---|
| `denied: requested access to the resource is denied` | неверный логин/токен Docker Hub | проверить `DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN` |
| CD не запускается | push не в `main` или упал CI | проверить branch и статус `ci` |
| На VPS старая версия | используется старый тег/кеш | `docker compose pull` и фиксировать новый тег |
| SSH ошибка в CD | ключ/хост/пользователь неверны | проверить `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` |
| Приложение недоступно снаружи | порт/фаервол | открыть `80/tcp` в firewall и cloud security group |

---

## 13. Минимальные требования безопасности

- не хранить пароли и токены в репозитории;
- только SSH key auth, без пароля;
- ограничить порты (`22`, `80`, `443`);
- регулярно обновлять систему VPS;
- использовать отдельного deploy-пользователя (не `root`).

---

## 14. Чеклист сдачи

- [ ] CI запускается на push.
- [ ] Образ публикуется в registry.
- [ ] CD обновляет сервис на VPS.
- [ ] Приложение доступно по `http://<VPS_IP>/docs`.
- [ ] Продемонстрирован rollback.
- [ ] В отчете объяснена разница CI и CD своими словами.

---

Готово: эта методичка закрывает полный путь от `git push` до обновления приложения на VPS.
