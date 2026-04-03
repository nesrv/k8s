# Практическое занятие

## Kubernetes внутри Docker Desktop (в Windows)

## 1. Цель

Научиться запускать локальный кластер Kubernetes в Docker Desktop и развернуть в нем свое контейнерное приложение через `kubectl`.

---

## 2. Что должно быть установлено

- Docker Desktop (запускается без ошибок).
- `kubectl` (рекомендуется `v1.35.x`).
- Любой терминал PowerShell.

Проверка:

```powershell
docker version
# Проверяет, что Docker Engine запущен и доступен из CLI
kubectl version --client
# Проверяет, что kubectl установлен и команда работает
```

---

## 3. Включение Kubernetes в Docker Desktop

1. Откройте Docker Desktop.
2. В разделе Kubernetes нажмите `Create cluster` (или `Enable Kubernetes`, в зависимости от версии интерфейса).
3. Дождитесь статуса, что кластер запущен.

После запуска Docker Desktop обычно автоматически создает/обновляет контекст `docker-desktop` в kubeconfig.

Проверьте:

```powershell
kubectl config get-contexts
# Показывает список контекстов kubeconfig и текущий активный контекст
kubectl config use-context docker-desktop
# Переключает kubectl на встроенный кластер Docker Desktop
kubectl cluster-info
# Проверяет доступность API-сервера и системных сервисов
kubectl get nodes
# Показывает узлы кластера и их статус (должно быть Ready)
```

Ожидается: узел в статусе `Ready`.

Пример успешной проверки:

- текущий контекст: `docker-desktop` ✅
- `kubectl cluster-info` отвечает ✅
- нода `desktop-control-plane` в статусе `Ready` ✅
- версия кластера: `v1.35.1` ✅

---

## 4. Мини-приложение (пример)

Структура:

```text
k8s-docker-desktop-lab/
  main.py
  requirements.txt
  Dockerfile
  k8s/
    deployment.yaml
    service.yaml
```

`main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Docker Desktop K8s Lab")

@app.get("/")
def root():
    return {"msg": "hello from docker-desktop k8s"}

@app.get("/health")
def health():
    return {"status": "ok"}
```

`requirements.txt`:

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
```

`Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 5. Сборка образа

Важно: при работе с Kubernetes в Docker Desktop образ обычно доступен кластеру сразу, если вы собрали его в том же Docker Desktop.

```powershell
docker build -t lab1-api:1.0 .
# Собирает образ из Dockerfile в текущей папке и присваивает тег lab1-api:1.0
docker images
# Показывает локальные образы и позволяет убедиться, что lab1-api:1.0 создан
```

Пример вывода после успешной сборки:

```text
docker images
docker/desktop-cloud-provider-kind:v0.5.0
docker/desktop-containerd-registry-mirror:v0.0.3
envoyproxy/envoy:v1.36.4
kindest/node:v1.35.1
lab1-api:1.0     93e1c34dc52b        243MB         58.4MB
```

Что это означает:

- `lab1-api:1.0` — ваш пользовательский образ, который будет использоваться в `deployment.yaml`.
- `kindest/node:v1.35.1` и `docker/desktop-*` — служебные образы Kubernetes Docker Desktop; они нужны для самого локального кластера.
- В новых версиях Docker Desktop вывод `docker images` может быть в "расширенном" табличном формате (колонки вроде `IN USE`, `DISK USAGE`, `CONTENT SIZE`) и иногда визуально "съезжать" в PowerShell — это нормально.
- Для лабы важно, что строка `lab1-api:1.0` присутствует: значит образ собран и доступен локально.

---

## 6. Манифесты Kubernetes

Зачем они нужны:

- чтобы описать приложение в виде декларации ("что должно быть"), а не запускать контейнеры вручную;
- чтобы Kubernetes мог автоматически поддерживать нужное число реплик и восстанавливать pod после сбоев;
- чтобы отделить сетевой доступ (`Service`) от жизненного цикла приложения (`Deployment`);
- чтобы одинаково воспроизводить запуск на любом ПК/в любой среде через `kubectl apply -f ...`.

`k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lab1-api
spec:
  replicas: 2
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
        image: lab1-api:1.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
```

Пояснения к `Deployment`:

- `kind: Deployment` — контроллер, который поддерживает нужное число одинаковых pod-реплик.
- `metadata.name: lab1-api` — имя Deployment в кластере.
- `replicas: 2` — Kubernetes должен держать 2 pod одновременно.
- `selector.matchLabels` и `template.metadata.labels` должны совпадать; так Deployment понимает, какими pod он управляет.
- `image: lab1-api:1.0` — образ контейнера, собранный на шаге `docker build`.
- `imagePullPolicy: IfNotPresent` — сначала использовать локальный образ, а не пытаться всегда тянуть из внешнего registry.
- `containerPort: 8000` — порт приложения внутри контейнера (для FastAPI/uvicorn в этом примере).

`k8s/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: lab1-api
spec:
  selector:
    app: lab1-api
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

Пояснения к `Service`:

- `kind: Service` — стабильная точка доступа к группе pod по меткам.
- `selector.app: lab1-api` — сервис направляет трафик в pod с меткой `app=lab1-api`.
- `port: 80` — порт самого сервиса внутри кластера.
- `targetPort: 8000` — порт контейнера, куда сервис проксирует запросы.
- `type: ClusterIP` — сервис доступен внутри кластера; с хоста используем `kubectl port-forward`.

Итого: `Deployment` отвечает за запуск и самовосстановление pod, а `Service` — за сетевой доступ к этим pod.

---

## 7. Развертывание

```powershell
kubectl apply -f k8s/deployment.yaml
# Создает/обновляет Deployment (поды приложения)
kubectl apply -f k8s/service.yaml
# Создает/обновляет Service для доступа к подам
kubectl get deploy
# Проверяет состояние Deployment и число доступных реплик
kubectl get pods
# Проверяет, что поды перешли в статус Running
kubectl get svc
# Проверяет, что сервис создан и слушает нужный порт
```

Проверка логов:

```powershell
kubectl logs -l app=lab1-api --tail=50
# Показывает последние 50 строк логов всех подов приложения
```

---

## 8. Доступ к приложению

Для `ClusterIP` используйте `port-forward`:

```powershell
kubectl port-forward service/lab1-api 8080:80
# Пробрасывает локальный порт 8080 на порт 80 сервиса в кластере
```

В другом терминале:

```powershell
curl http://127.0.0.1:8080/
# Проверяет основной endpoint приложения
curl http://127.0.0.1:8080/health
# Проверяет health endpoint (ожидается статус ok)
```

---

## 9. Отличия от minikube

- Не нужно `minikube start`.
- Не нужны команды `minikube image load` в типовом случае.
- Контекст обычно `docker-desktop`.
- Версия Kubernetes зависит от версии Docker Desktop и его настроек.
- Ресурсы Kubernetes берутся из лимитов Docker Desktop (CPU/RAM/Disk).

---

## 10. Типичные проблемы и решения

| Симптом                                                                 | Причина                                                                   | Что сделать                                                                                                        |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `Unable to connect to the server`                                            | Kubernetes в Docker Desktop не запущен                                 | Включить Kubernetes в UI, дождаться запуска, проверить контекст `docker-desktop` |
| `ErrImagePull` / `ImagePullBackOff`                                        | Неверный `image`/`tag` или образ не собран           | Проверить `docker images`, имя тега в `deployment.yaml`, пересобрать                         |
| `kubectl` показывает не ту версию                        | Перехвачен путь другим `kubectl` (например Docker) | Временно:`$env:Path = "C:\\kubectl;" + $env:Path`; проверить `kubectl version --client`                 |
| Приложение не открывается через `localhost:8080` | Не запущен `port-forward`/неверные порты                 | Проверить `kubectl get svc`, `targetPort`, держать `port-forward` активным                     |
| Поды не `Running`                                                      | Ошибка запуска контейнера                                 | `kubectl describe pod ...` и `kubectl logs ...`                                                                         |

---

## 11. Чеклист

- Kubernetes в Docker Desktop запущен.
- `kubectl get nodes` показывает `Ready`.
- Образ приложения собран локально.
- Deployment и Service применены.
- Минимум 2 пода в `Running`.
- `/` и `/health` открываются через `port-forward`.
- Показаны логи и базовая диагностика.

---

## 12. Полезные команды

```powershell
kubectl config current-context
# Показывает текущий активный контекст
kubectl get all
# Быстрый обзор основных ресурсов в namespace
kubectl describe deployment lab1-api
# Подробное состояние Deployment и его событий
kubectl describe pod <pod-name>
# Диагностика конкретного pod: события, причины ошибок, статус контейнеров
kubectl logs <pod-name>
# Логи конкретного pod для отладки запуска
kubectl delete -f k8s/service.yaml
# Удаляет Service
kubectl delete -f k8s/deployment.yaml
# Удаляет Deployment и его pod-реплики
```

---

## 13. Усложнение: зачем реально нужен Kubernetes

Цель этого раздела - показать, что Kubernetes нужен не "для запуска одного контейнера", а для управления сервисом в условиях изменений и сбоев.

### 13.1. Масштабирование под нагрузку

Увеличьте число реплик:

```powershell
kubectl scale deployment lab1-api --replicas=3
kubectl get pods -w
```

Что увидеть:

- было 2 pod, стало 3;
- приложение продолжает работать без ручного запуска каждого контейнера.

Почему это важно:

- в Docker без оркестратора вы масштабируете вручную;
- в Kubernetes желаемое состояние задается одной командой, а система сама приводит фактическое состояние к нему.

### 13.2. Самовосстановление после сбоя

Удалите один pod:

```powershell
kubectl get pods
kubectl delete pod <pod-name>
kubectl get pods -w
```

Что увидеть:

- удаленный pod исчезает;
- Kubernetes автоматически создает новый pod.

Почему это важно:

- Kubernetes поддерживает доступность сервиса даже при падении отдельных экземпляров;
- оператор задает "сколько должно быть", а не "как запускать каждый процесс".

#### Вариант A (без изменения кода): удалить pod вручную

Это самый быстрый способ показать self-healing без доработки приложения.

```powershell
kubectl get pods
kubectl delete pod <pod-name>
kubectl get pods -w
```

Что наблюдаем:

- удаленный pod исчезает из списка;
- Kubernetes автоматически создает новый pod;
- сервис продолжает отвечать (особенно при 2 и более репликах).

#### Вариант B (через `/docs`): падение по endpoint `/crash`

Если нужно инициировать сбой именно из Swagger UI (`http://127.0.0.1:8080/docs`), добавьте endpoint, который завершает процесс:

```python
@app.post("/crash")
def crash():
    import os
    os._exit(1)
```

Далее:

1. Пересоберите образ и обновите Deployment.
   Важно: используйте **новый тег** (`1.2`, `1.3`, ...), а не перезаписывайте старый.
   При `imagePullPolicy: IfNotPresent` Kubernetes может оставить локальный старый образ с тем же тегом.

```powershell
docker build -t lab1-api:1.2 .
kubectl set image deployment/lab1-api lab1-api=lab1-api:1.2
kubectl rollout status deployment/lab1-api
```

1. Откройте `/docs` и вызовите `POST /crash`.
2. Наблюдайте восстановление:

```powershell
kubectl get pods -w
kubectl logs -l app=lab1-api --previous
kubectl describe pod <pod-name>
```

Что показать студентам:

- после вызова `/crash` контейнер в pod завершается;
- Kubernetes перезапускает/пересоздает pod, чтобы вернуть заданное число реплик;
- `--previous` в логах показывает вывод завершившегося контейнера.
- если новый endpoint не появился в `/docs`, перезапустите `port-forward` и обновите страницу (`Ctrl+F5`).

Почему после `/crash` может появиться ошибка `error: lost connection to pod`:

- `kubectl port-forward` держит туннель к конкретному pod/контейнеру;
- при `POST /crash` процесс в контейнере завершается, pod перезапускается/заменяется;
- старый туннель теряет цель и разрывается - это ожидаемое поведение.

Как восстановить доступ после crash:

```powershell
kubectl get pods -w
kubectl port-forward service/lab1-api 8080:80
curl.exe http://127.0.0.1:8080/health
```

Плавная демонстрация (меньше визуальных "провалов"):

- перед экспериментом выставьте 2-3 реплики;
- тогда при падении одного pod сервис чаще всего продолжит отвечать через оставшиеся реплики.

```powershell
kubectl scale deployment lab1-api --replicas=3
kubectl get pods
```

### 13.3. Сравнение "без Kubernetes" и "с Kubernetes" на падении `/crash`

Цель: увидеть практическую разницу в восстановлении сервиса после сбоя.

#### Режим A: без Kubernetes (только Docker)

Запустите контейнер напрямую:

```powershell
docker run --rm -p 18080:8000 --name no-k8s-lab lab1-api:1.2
```

Далее:

1. Откройте `http://127.0.0.1:18080/docs`.
2. Вызовите `POST /crash`.
3. Проверьте состояние:

```powershell
docker ps -a --filter "name=no-k8s-lab"
curl.exe http://127.0.0.1:18080/health
```

Что увидеть:

- контейнер перейдет в `Exited` (или завершится и удалится при `--rm`);
- endpoint перестанет отвечать;
- сервис не поднимется сам, пока вы не запустите контейнер вручную.

#### Режим B: с Kubernetes (Deployment)

Убедитесь, что реплик >= 2:

```powershell
kubectl scale deployment lab1-api --replicas=2
kubectl get pods
```

Далее:

1. Через `http://127.0.0.1:8080/docs` вызовите `POST /crash`.
2. Наблюдайте восстановление:

```powershell
kubectl get pods -w
```

Что увидеть:

- один pod падает/перезапускается;
- Deployment автоматически возвращает заданное число реплик;
- сервис восстанавливается без ручного запуска.

Краткий вывод:

- без Kubernetes после сбоя нужен ручной запуск контейнера;
- с Kubernetes система сама поддерживает "желаемое состояние" (self-healing).

### 13.4. Контролируемое обновление версии (rollout)

1. Измените ответ в `main.py` (например, `"v1.1"`),
2. пересоберите образ и обновите тег:

```powershell
docker build -t lab1-api:1.1 .
```

1. В `k8s/deployment.yaml` замените `image: lab1-api:1.0` на `image: lab1-api:1.1`, затем:

```powershell
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/lab1-api
kubectl get pods
```

Что увидеть:

- pod обновляются по очереди, без полной остановки сервиса.

Почему это важно:

- безопасные обновления без "выключили все -> включили все";
- есть контроль процесса обновления.

### 13.5. Кейс: что Kubernetes считает ошибкой

Задание:

1. Добавьте endpoint с медленным ответом в `main.py`:

```python
@app.get("/slow")
def slow():
    import time
    time.sleep(20)
    return {"msg": "slow response"}
```

2. В `k8s/deployment.yaml` добавьте (или измените) `livenessProbe` у контейнера:

```yaml
livenessProbe:
  httpGet:
    path: /slow
    port: 8000
  timeoutSeconds: 2
  periodSeconds: 5
  failureThreshold: 3
```

3. Пересоберите образ с новым тегом и обновите Deployment.

Наблюдение:

- pod начнет периодически перезапускаться;
- в `kubectl describe pod <pod-name>` появятся события `Unhealthy` и перезапуски контейнера.

Команды для наблюдения:

```powershell
kubectl get pods -w
kubectl describe pod <pod-name>
kubectl logs <pod-name> --previous
```

Вывод:

Kubernetes не знает, что "правильно" для вашего бизнеса, он действует строго по заданному контракту проб (`Probe`).

### 13.6. Кейс: Readiness и Liveness probes

Задача:

Показать разницу между "процесс в контейнере запущен" и "приложение готово принимать пользовательский трафик".

Добавьте в `k8s/deployment.yaml` (внутрь контейнера) такие пробы:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 3
```

Что означают параметры:

- `initialDelaySeconds` - задержка перед первой проверкой после старта контейнера;
- `periodSeconds` - как часто выполнять проверку;
- `livenessProbe` - если долго неуспешна, Kubernetes перезапускает контейнер;
- `readinessProbe` - если неуспешна, pod исключается из Service endpoints (трафик на него не идет).

Шаги эксперимента:

1. Примените манифест с пробами.
2. Искусственно "сломайте" `/health` (например, временно возвращайте HTTP 500).

Пример кода для `main.py`:

```python
from fastapi import HTTPException

@app.get("/health")
def health():
    raise HTTPException(status_code=500, detail="принудительная ошибка health для демонстрации probes")
```

После демонстрации верните рабочий вариант:

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

3. Пересоберите образ с новым тегом, обновите Deployment и дождитесь rollout.
4. Наблюдайте состояние:

```powershell
kubectl get pods
kubectl describe pod <pod-name>
kubectl get endpoints lab1-api
```

Что показать студентам:

- pod может быть в `Running`, но при этом `READY 0/1` (`NOT READY`);
- Service перестает направлять трафик в неготовый pod (он исчезает из endpoints);
- если падает только `readinessProbe`, Kubernetes не обязан "убивать" контейнер;
- если начинает падать `livenessProbe`, контейнер будет перезапускаться.

Практический вывод:

- `Liveness` отвечает на вопрос: "жив ли процесс?";
- `Readiness` отвечает на вопрос: "можно ли пускать к нему пользователей прямо сейчас?".

### 13.7. Кейс: ограничения CPU и памяти

Задача:

Показать, как Kubernetes ограничивает контейнеры по ресурсам и защищает узел от "прожорливых" приложений.

Добавьте в контейнер `resources` (в `k8s/deployment.yaml`):

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "200m"
    memory: "256Mi"
```

Эксперимент:

1. Добавьте endpoint `/memory`, который пытается занять около 300 МБ памяти:

```python
@app.get("/memory")
def memory():
    chunk = "x" * (300 * 1024 * 1024)
    return {"allocated_bytes": len(chunk)}
```

2. Пересоберите образ с новым тегом, обновите Deployment и дождитесь rollout.
3. Вызовите endpoint `/memory` из `/docs` или `curl`.
4. Наблюдайте:

```powershell
kubectl get pods
kubectl describe pod <pod-name>
```

Что увидят студенты:

- pod будет перезапускаться после вызова;
- в описании pod появится причина завершения контейнера: `OOMKilled`.

Практический вывод:

Kubernetes принудительно защищает узел от "плохих" контейнеров, которые выходят за установленные лимиты памяти/CPU.

### 13.8. Откат, если новая версия плохая

Если после обновления приложение работает неправильно:

```powershell
kubectl rollout undo deployment/lab1-api
kubectl rollout status deployment/lab1-api
```

Что увидеть:

- возврат на предыдущую стабильную версию.

Почему это важно:

- быстрый rollback снижает риск простоев в проде.

### 13.9. Вывод для отчета (своими словами)

Kubernetes нужен не для "запуска контейнера", а для:

- автоматического масштабирования под нагрузку;
- самовосстановления после сбоев;
- безопасных обновлений и быстрых откатов;
- управления сервисом как целевой системой, а не набором ручных команд.
