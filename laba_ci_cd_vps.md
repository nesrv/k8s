# Практическое занятие

## Деплой и CI/CD на VPS (Kubernetes / k3s)

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

## Публикация образов в Docker Hub

Образ должен лежать в **публичном или приватном registry**, иначе k3s на VPS не сможет выполнить `pull` с Docker Hub — только локальная сборка на вашем ПК недостаточна.

В **CI** образ собирается и **пушится** в registry. В манифестах Kubernetes указывается полное имя:

`<registry>/<пользователь или org>/<репозиторий>:<тег>`

Ниже в примерах workflow используется **Docker Hub**. **GHCR** — равноценная альтернатива для репозитория на GitHub.

---

### Docker Hub

#### Подготовка аккаунта и токена

1. Зарегистрируйтесь на [hub.docker.com](https://hub.docker.com/). Запомните **логин** (Docker ID) — он участвует в имени образа.
2. Создайте **Access Token** (для входа из CLI и для GitHub Actions): *Account Settings → Security → New Access Token* — права **Read & Write** (или аналог для загрузки образов). **Пароль при `docker login` вводить не нужно** — вместо пароля вставляют этот токен.
3. Имя образа на Docker Hub всегда в виде `**ВАШ_LOGIN/имя_репозитория:тег`** (например `ivanov/lab1-api:latest`). Репозиторий на сайте можно создать заранее (*Repositories → Create*), но чаще он **появляется автоматически** после первого успешного `docker push` с таким именем.

---

#### Заливка образ вручную

**1.** Откройте терминал в каталоге проекта, где лежит **Dockerfile** (контекст сборки — эта папка).

PowerShell (Windows), пример:

```powershell
cd C:\path\to\your\project
```

---

**2.** Войдите в Docker Hub (вместо пароля — **Access Token**):

```text
docker login -u ВАШ_LOGIN
```

Система запросит `Password:` — вставьте токен (ввод может не отображаться).

---

**3.** Соберите образ, указав **полное имя** под ваш логин и выбранный тег:

```text
docker build -t ВАШ_LOGIN/lab1-api:v1 .
```

Точка в конце — «контекст = текущая папка».

---

**4.** Отправьте образ в registry:

```text
docker push ВАШ_LOGIN/lab1-api:v1
```

Дождитесь окончания загрузки слоёв без ошибки `denied` / `unauthorized`.

---

**5.** Проверка: на [hub.docker.com](https://hub.docker.com/) откройте **Repositories** → ваш репозиторий → вкладка **Tags** — должен быть тег `v1`.

**6.** В `deployment.yaml` укажите образ из registry, например:

```yaml
image: DOCKERHUB_USERNAME/lab1-api:latest
```

При необходимости задайте `imagePullPolicy: Always`, чтобы при теге `latest` на узле подтягивалась свежая сборка.

---

### Ручной деплой

#### Подключение по SSH (с вашего ПК)

```bash
ssh alekseeva@81.90.182.174
```

**Имя хоста (DNS):** `alekseeva.h1n.ru` — при настроенной A-записи:

```bash
ssh alekseeva@alekseeva.h1n.ru
```

Дальнейшие шаги выполняются **на VPS** в SSH-сессии. Подставьте вместо `DOCKERHUB_USERNAME` свой логин Docker Hub; при другом сервере — свой пользователь, IP и домен.

---

#### 1. Установите k3s

Один узел, Ubuntu. Если k3s уже установлен — шаг пропустите.

```bash
curl -sfL https://get.k3s.io | sh -
sudo systemctl status k3s
```

Дождитесь активного состояния сервиса `k3s`.

---

#### 2. Настройте `kubectl` для вашего пользователя (не root)

Файл `/etc/rancher/k3s/k3s.yaml` создаётся k3s и обычно **читается только root**; от обычного пользователя его не открывают — иначе `permission denied` и предупреждение про `--write-kubeconfig-mode`. 

Скопируйте конфиг в домашний каталог:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown "$USER:$USER" ~/.kube/config
chmod 600 ~/.kube/config
```

**Важно:** после установки k3s команда `kubectl` часто является **ссылкой на `k3s`** (`/usr/local/bin/kubectl` → `k3s`), а не отдельным бинарником. 

Такой `kubectl` **не подхватывает** `~/.kube/config`, если переменная `**KUBECONFIG` не задана**, и снова пытается читать `/etc/rancher/k3s/k3s.yaml`. Задайте явно:

```bash
export KUBECONFIG="$HOME/.kube/config"
```

Чтобы не вводить при каждом входе по SSH, добавьте эту строку в `~/.bashrc` (или `~/.profile`). Проверка: `echo "$KUBECONFIG"` должен показывать путь к вашему `config`.

**Альтернатива без `export`:** каждый раз указывать файл:

```bash
k3s kubectl --kubeconfig "$HOME/.kube/config" get nodes
```

(или `kubectl --kubeconfig "$HOME/.kube/config" …`, если `kubectl` — это k3s.)

Если `kubectl` вызываете **с другого компьютера**, в копии `~/.kube/config` замените адрес API `127.0.0.1` на **публичный IP VPS** (например `81.90.182.174`). Если работаете только на самом VPS, менять не обязательно.

---

#### 3. Проверьте, что кластер отвечает

```bash
kubectl get nodes
```

У узла в колонке `STATUS` должно быть `Ready`.

---

#### 4. Получите на VPS каталог `k8s/` с манифестами

Склонируйте **свой** репозиторий (URL из GitHub, кнопка **Code**):

```bash
cd ~
git clone https://github.com/ВАШ_АККАУНТ/ИМЯ_РЕПО.git
cd ИМЯ_РЕПО/k8s
ls -la
```

Должны быть `deployment.yaml` и `service.yaml`.

- **Публичный** репозиторий — достаточно HTTPS, как выше.
- **Приватный** — удобнее SSH: `git clone git@github.com:ВАШ_АККАУНТ/ИМЯ_РЕПО.git` (ключ на VPS добавлен в GitHub), либо HTTPS с [Personal Access Token](https://github.com/settings/tokens) вместо пароля.

Проверьте в `deployment.yaml` поле `**image:`** — образ в Docker Hub, например `DOCKERHUB_USERNAME/lab1-api:latest` (`nano deployment.yaml` при необходимости).

Для доступа из браузера в `service.yaml` нужны тип **NodePort** и `**nodePort`** (например `30080`). Если в репозитории `ClusterIP`, замените `spec` сервиса на пример из варианта B.

**Вариант B — без Git**

```bash
mkdir -p ~/lab-app/k8s
cd ~/lab-app/k8s
nano deployment.yaml
```

`deployment.yaml` (замените `DOCKERHUB_USERNAME`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lab1-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lab1-api
  template:
    metadata:
      labels:
        app: lab1-api
    spec:
      containers:
        - name: lab1-api
          image: DOCKERHUB_USERNAME/lab1-api:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 8000
```

```bash
nano service.yaml
```

`service.yaml`:

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

Образ должен быть в Docker Hub: на ПК `docker build`, `docker login`, `docker push`. С VPS нужен выход в интернет для `pull` слоёв.

---

#### 5. Примените манифесты

Рабочий каталог — `k8s/`: после клона это `~/ИМЯ_РЕПО/k8s`, при варианте B — `~/lab-app/k8s`.

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

---

#### 6. Проверьте поды и сервисы

```bash
kubectl get pods,svc
```

Поды в `STATUS` должны стать `Running`. Для `Service` типа `NodePort` запомните порт узла — в примере **30080** (в `PORT(S)` вид `80:30080/TCP`).

---

#### 7. Разрешите вход с интернета

В панели провайдера откройте inbound **TCP 30080** и **TCP 22** (SSH). На машине при включённом `ufw`:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 30080/tcp
sudo ufw status
```

---

#### 8. Откройте приложение в браузере (Swagger)

- `http://81.90.182.174:30080/docs`
- или `http://alekseeva.h1n.ru:30080/docs`

Порт должен совпадать с `nodePort` в `service.yaml`.

---

#### 9. Обновите образ после новой сборки

После `docker build` и `docker push`:

```bash
export IMG="DOCKERHUB_USERNAME/lab1-api:latest"
kubectl set image deployment/lab1-api lab1-api=$IMG
kubectl rollout status deployment/lab1-api
```

Имена `deployment/lab1-api` и контейнера `lab1-api` должны совпадать с `metadata.name` в `deployment.yaml` и `containers[].name`.

---

#### 10. Откат при неудачном выкате

```bash
kubectl rollout undo deployment/lab1-api
kubectl rollout status deployment/lab1-api
```

История ревизий:

```bash
kubectl rollout history deployment/lab1-api
```

---

