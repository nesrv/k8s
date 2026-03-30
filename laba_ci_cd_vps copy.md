# Практическое занятие

## Деплой и CI/CD на VPS (Kubernetes / k3s)

---

## Публикация образов в Docker Hub и GitHub Container Registry (GHCR)

Образ должен лежать в **публичном или приватном registry**, иначе k3s на VPS не сможет выполнить `pull` с Docker Hub — только локальная сборка на вашем ПК недостаточна.

В **CI** образ собирается и **пушится** в registry. В манифестах Kubernetes указывается полное имя:

`<registry>/<пользователь или org>/<репозиторий>:<тег>`

Ниже в примерах workflow используется **Docker Hub**. **GHCR** — равноценная альтернатива для репозитория на GitHub.

---

### Docker Hub

#### Подготовка аккаунта и токена

1. Зарегистрируйтесь на [hub.docker.com](https://hub.docker.com/). Запомните **логин** (Docker ID) — он участвует в имени образа.

2. Создайте **Access Token** (для входа из CLI и для GitHub Actions):
  *Account Settings → Security → New Access Token* — права **Read & Write** (или аналог для загрузки образов).
   **Пароль при `docker login` вводить не нужно** — вместо пароля вставляют этот токен.

3. Имя образа на Docker Hub всегда в виде `**ВАШ_LOGIN/имя_репозитория:тег`** (например `ivanov/lab1-api:latest`).
  Репозиторий на сайте можно создать заранее (*Repositories → Create*), но чаще он **появляется автоматически** после первого успешного `docker push` с таким именем.
  
  
4. Для CI в GitHub Secrets сохраните:
  - `DOCKERHUB_USERNAME` — ваш логин на Docker Hub;
  - `DOCKERHUB_TOKEN` — созданный токен.

---

#### Способ 1: залить образ вручную с вашего компьютера

**Цель:** собрать образ локально и отправить на Docker Hub командой `**docker push*`*.

Это и есть «заливка». Один только `**docker build**` на Hub ничего не загружает.

**Предусловия:** установлен и запущен **Docker Desktop** (Windows/macOS) или Docker Engine (Linux).

---

**Шаг 1.** Откройте терминал в каталоге проекта, где лежит **Dockerfile** (контекст сборки — эта папка).

PowerShell (Windows), пример:

```powershell
cd C:\path\to\your\project
```

---

**Шаг 2.** Войдите в Docker Hub (вместо пароля — **Access Token**):

```text
docker login -u ВАШ_LOGIN
```

Система запросит `Password:` — вставьте токен (ввод может не отображаться).

---

**Шаг 3.** Соберите образ, указав **полное имя** под ваш логин и выбранный тег:

```text
docker build -t ВАШ_LOGIN/lab1-api:v1 .
```

Точка в конце — «контекст = текущая папка».

---

**Шаг 4.** Отправьте образ в registry:

```text
docker push ВАШ_LOGIN/lab1-api:v1
```

Дождитесь окончания загрузки слоёв без ошибки `denied` / `unauthorized`.

---

**Шаг 5.** Проверка: на [hub.docker.com](https://hub.docker.com/) откройте **Repositories** → ваш репозиторий → вкладка **Tags** — должен быть тег `v1`.

---

**Типичные ошибки**


| Сообщение                                            | Что сделать                                                           |
| ---------------------------------------------------- | --------------------------------------------------------------------- |
| `denied: requested access to the resource is denied` | Проверить логин, токен и что имя образа начинается с `**ВАШ_LOGIN/`** |
| `unauthorized: authentication required`              | Выполнить `docker login` заново                                       |
| Образа нет на Hub после `build`                      | Выполнить именно `**docker push**`, не только `docker build`          |


---

#### Способ 2: залить через GitHub Actions (основной для лабы)

После настройки секретов `DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN` push в ветку `main` запускает workflow.

Job **Build and push** сам выполняет эквивалент `docker login` + `docker build` + `docker push` на раннере GitHub.

Вручную на своём ПК шаги способа 1 **не обязательны**.

---

### GitHub Container Registry (GHCR)

1. Образы хранятся под именем `**ghcr.io/<owner>/<image>:<тег>`**, где `<owner>` — пользователь или организация GitHub.
2. В GitHub для организации/репозитория при необходимости включите поддержку GitHub Packages и права на публикацию.
3. В workflow для входа в GHCR обычно используют встроенный `**GITHUB_TOKEN**` (scope `write:packages`) или отдельный PAT с правами `write:packages`.

---

Пример шага логина и тегов (замените `OWNER` и `IMAGE`):

```yaml
- name: Login to GHCR
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}

- name: Build and push
  uses: docker/build-push-action@v6
  with:
    context: .
    push: true
    tags: |
      ghcr.io/OWNER/IMAGE:latest
      ghcr.io/OWNER/IMAGE:${{ github.sha }}
```

---

В `deployment.yaml` на VPS укажите тот же образ, например `ghcr.io/OWNER/IMAGE:latest`.

При **приватном** пакете настройте на k3s [imagePullSecret](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/). В учебной работе проще начать с **публичного** образа.

---

### Кратко для отчёта

- **Docker Hub** — универсальный публичный registry, проще всего для первого прохода.
- **GHCR** — удобно, если код уже на GitHub и не хочется заводить отдельный аккаунт в Docker Hub.
- Секреты (`USERNAME`/`TOKEN` или `GITHUB_TOKEN`) хранятся только в GitHub Secrets, не в репозитории.

---

## 1. Цель работы

Научиться собирать и публиковать Docker-образ через CI, затем автоматически выкатывать приложение на VPS в кластер **Kubernetes (k3s)** через CD.

---

## 2. Что получите в итоге

- после `git push` запускается CI-пайплайн;
- проходят проверки и собирается образ;
- образ публикуется в registry;
- на VPS в k3s выполняется обновление Deployment (новый образ в кластере);
- при проблеме можно сделать rollback (`kubectl rollout undo`).

---

## 3. Архитектура (учебный минимум)

- GitHub-репозиторий;
- GitHub Actions (CI/CD);
- Docker Hub (или GHCR) как registry;
- VPS (Ubuntu) с SSH-доступом;
- **[k3s](https://k3s.io/)** — один узел, достаточно для учебы;
- приложение FastAPI в контейнере; деплой через манифесты `k8s/`.

**CI:** сборка и push образа.

**CD в этой методичке:** SSH на VPS и команды `kubectl`.

---

## 4. Подготовка репозитория

Минимальная структура:

```text
project/
  app/
    main.py
  requirements.txt
  Dockerfile
  k8s/
    deployment.yaml
    service.yaml
  .github/
    workflows/
      ci-cd.yml
```

---

В `deployment.yaml` укажите образ из registry, например:

`image: DOCKERHUB_USERNAME/lab1-api:latest`

При необходимости задайте `imagePullPolicy: Always`, чтобы при теге `latest` на узле подтягивалась свежая сборка.

---

## 5. Kubernetes (k3s) на VPS

### 5.1. Установка k3s (один узел, для учебы)

На чистом VPS (Ubuntu):

```bash
curl -sfL https://get.k3s.io | sh -
sudo systemctl status k3s
```

---

Kubeconfig по умолчанию: `/etc/rancher/k3s/k3s.yaml`.

Для пользователя `ubuntu` (не root) скопируйте и поправьте сервер:

```bash
sudo mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
# замените в сгенерированном файле 127.0.0.1 на публичный IP VPS, если kubectl вызываете с вашего ПК
```

---

Проверка на VPS:

```bash
kubectl get nodes
```

k3s подтянет образ с Docker Hub по полю `image:` в Deployment, если с VPS есть выход в интернет.

---

### 5.2. Минимальные манифесты в репозитории (`k8s/`)

Полную структуру `Deployment` и метки `app: lab1-api` можно взять из лабы по Kubernetes (например, `laba_k8s_docker_desktop.md`), заменив `image` на свой из Docker Hub и при необходимости тип `Service` на `NodePort`.

---

`deployment.yaml` (фрагмент):

```yaml
spec:
  template:
    spec:
      containers:
        - name: lab1-api
          image: DOCKERHUB_USERNAME/lab1-api:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 8000
```

---

`service.yaml` — для доступа снаружи удобен `NodePort`, например порт `30080` на хосте:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: lab1-api
spec:
  type: NodePort
  selector:
    app: lab1-api
  ports:
    - port: 80
      targetPort: 8000
      nodePort: 30080
```

---

Первый раз на VPS (вручную, из склонированного репо или вставив файлы):

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl get pods,svc
```

Проверка: `http://<VPS_IP>:30080/docs` (откройте порт `30080` в firewall облака и `ufw`, если используется).

---

### 5.3. Что делает CD

После успешного CI на VPS по SSH обновляют образ в кластере, например:

```bash
export IMG="DOCKERHUB_USERNAME/lab1-api:latest"
kubectl set image deployment/lab1-api lab1-api=$IMG
kubectl rollout status deployment/lab1-api
```

Имя контейнера `lab1-api` должно совпадать с `containers[].name` в `deployment.yaml`.

---

Или при изменении только манифестов:

```bash
kubectl apply -f /opt/lab-app/k8s/deployment.yaml
kubectl rollout status deployment/lab1-api
```

На VPS должен лежать актуальный `k8s/` (например, обновляется отдельным `git pull` в CD).

---

## 6. Секреты в GitHub

В репозитории добавьте Secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`

Опционально:

- `VPS_PORT` (если SSH не на 22)

---

## 7. CI/CD workflow (GitHub Actions)

Файл: `.github/workflows/ci-cd.yml`

### 7.1. Job `ci`

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
```

---

### 7.2. Job `cd` (k3s / kubectl по SSH)

Добавьте после `ci`:

```yaml
  cd:
    needs: ci
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH (kubectl / k3s)
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            export IMG="${{ secrets.DOCKERHUB_USERNAME }}/lab1-api:latest"
            kubectl set image deployment/lab1-api lab1-api=$IMG
            kubectl rollout status deployment/lab1-api --timeout=120s
```

---

Убедитесь, что пользователь `VPS_USER` на сервере может вызывать `kubectl` (kubeconfig настроен, см. п. 5.1).

---

## 8. Первый ручной запуск на VPS

Один раз выполните установку k3s (п. 5.1), затем:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl get pods,svc
```

Проверка: `http://<VPS_IP>:30080/docs` (или ваш `nodePort`).

---

## 9. Демонстрация CI/CD на занятии

1. Измените строку в `main.py` (например, версию ответа).
2. Сделайте commit и push в `main`.
3. Покажите Actions:
  - job `ci` прошёл;
  - job `cd` прошёл.
4. На VPS:

```bash
kubectl get pods
kubectl rollout history deployment/lab1-api
```

1. Откройте приложение в браузере и покажите новую версию.

---

## 10. Rollback (обязательно знать)

```bash
kubectl rollout undo deployment/lab1-api
kubectl rollout status deployment/lab1-api
```

---

Либо откат на конкретную ревизию:

```bash
kubectl rollout history deployment/lab1-api
kubectl rollout undo deployment/lab1-api --to-revision=<N>
```

---

## 11. Типичные ошибки


| Симптом                                              | Причина                                      | Что делать                                                            |
| ---------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------- |
| `denied: requested access to the resource is denied` | неверный логин/токен Docker Hub              | проверить `DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN`                    |
| CD не запускается                                    | push не в `main` или упал CI                 | проверить branch и статус `ci`                                        |
| На кластере старый pod                               | `latest` уже закеширован                     | `imagePullPolicy: Always` или деплой с уникальным тегом `:sha`        |
| `kubectl: command not found` на VPS                  | пользователь без k3s/kubeconfig              | настроить `~/.kube/config` для `VPS_USER`                             |
| `ErrImagePull` / `ImagePullBackOff`                  | нет доступа к registry / неверное имя образа | проверить `image:` и сеть с VPS                                       |
| SSH ошибка в CD                                      | ключ/хост/пользователь неверны               | проверить `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`                       |
| Приложение недоступно снаружи                        | порт/фаервол                                 | открыть `30080` (или ваш NodePort) и `22` в firewall и security group |


---

## 12. Минимальные требования безопасности

- не хранить пароли и токены в репозитории;
- только SSH key auth, без пароля;
- ограничить порты (`22`, при необходимости `80`/`443`, ваш `nodePort` для сервиса);
- регулярно обновлять систему VPS;
- использовать отдельного deploy-пользователя (не `root`).

---

## 13. Чеклист сдачи

- CI запускается на push.
- Образ публикуется в registry.
- k3s на VPS запущен, `kubectl get nodes` показывает Ready.
- CD по SSH обновляет Deployment (`kubectl set image` или `apply`).
- Приложение доступно по `http://<VPS_IP>:<nodePort>/docs` (или выбранному способу публикации).
- Продемонстрирован rollback.
- В отчёте объяснена разница CI и CD своими словами.

---

Методичка описывает путь от `git push` до обновления приложения на VPS в кластере **Kubernetes (k3s)**.