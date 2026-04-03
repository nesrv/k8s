# Практическое занятие

## Деплой и CI/CD на VPS (Kubernetes / k3s)

## 1. Цель работы

Научиться собирать и публиковать Docker-образ через CI, затем автоматически выкатывать приложение на VPS в кластер **Kubernetes (k3s)** через CD. **Опционально:** познакомиться с **GitOps** и **Argo CD** как наглядной pull-моделью выката (состояние кластера из Git).

---

## 2. Что получите в итоге

- после `git push` запускается CI-пайплайн;
- проходят проверки и собирается образ;
- образ публикуется в registry;
- на VPS в k3s выполняется обновление Deployment (новый образ в кластере);
- при проблеме можно сделать rollback (`kubectl rollout undo`).
- **(дополнение)** при прохождении блока GitOps: кластер подтягивает манифесты из репозитория, интерфейс Argo CD показывает синхронизацию и здоровье приложения.

---

## 3. Архитектура (учебный минимум)

- GitHub-репозиторий;
- GitHub Actions (CI/CD);
- Docker Hub (или GHCR) как registry;
- VPS (Ubuntu) с SSH-доступом;
- **[k3s](https://k3s.io/)** — один узел, достаточно для учебы;
- приложение FastAPI в контейнере; деплой через манифесты `k8s/`.

**CI:** сборка и push образа.

**CD в этой методичке:** SSH на VPS и команды `kubectl` (**push-модель**: CI «толкает» изменения в кластер).

**Дополнение (GitOps):** на кластере работает **Argo CD**; он **сам** сверяет Git с кластером (**pull-модель**). Подробнее — раздел **«GitOps (опционально): Argo CD»** в конце методички.

**Как читать документ дальше:** блоки идут в **рабочем порядке** — сначала **Docker Hub** (образ в registry), затем **ручной деплой на VPS** (k3s, `kubectl`, сеть). После шагов 1–10 — **типичные ошибки** (п. 11). **Argo CD** в конце — **отдельная ветка**: базовую лабу можно пройти без неё.

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

Файл **`ci-cd.yml`** в методичке не разбирается по строкам: в нём обычно **сборка образа** и при желании **SSH + `kubectl`** (тот же смысл, что ручные шаги ниже, но автоматически после `git push`).

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

### Ручной деплой на VPS

Ниже — **пошаговый выкат** с SSH на сервер: клонирование репозитория, `kubectl apply`, проверки. Это основной **CD-путь** методички (без Argo CD). Образ к этому моменту уже должен быть **в Docker Hub** (как в разделе выше или через CI).

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

Такой `kubectl` **не подхватывает** `~/.kube/config`, если переменная **`KUBECONFIG` не задана**, и снова пытается читать `/etc/rancher/k3s/k3s.yaml`. Задайте явно:

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

Проверьте в `deployment.yaml` поле **`image:`** — образ в Docker Hub, например `DOCKERHUB_USERNAME/lab1-api:latest` (`nano deployment.yaml` при необходимости).

Для доступа из браузера в `service.yaml` нужны тип **`NodePort`** и поле **`nodePort`** (например **`30080`**). Если у сервиса указан **`ClusterIP`**, замените `spec` на вариант с **`type: NodePort`** и **`nodePort: 30080`** (как в актуальном `service.yaml` репозитория).

---

#### 5. Примените манифесты

Рабочий каталог — `k8s/`: после клона это `~/ИМЯ_РЕПО/k8s`.

```bash
sudo kubectl apply -f deployment.yaml
sudo kubectl apply -f service.yaml
```

---

#### 6. Проверьте поды и сервисы

```bash
kubectl get pods -l app=lab1-api
kubectl get svc lab1-api
```

У подов в колонке `STATUS` должно быть **`Running`**, в **`READY`** — **`1/1`**. Если не настроили `KUBECONFIG` и копию `~/.kube/config` (п. 2), используйте **`sudo kubectl`** вместо `kubectl`.

Для сервиса типа **NodePort** в `PORT(S)` должен быть вид **`80:30080/TCP`** (внешний порт узла **30080** совпадает с `nodePort` в `service.yaml`).

Проверка с самого VPS (когда поды уже `Running`):

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:30080/docs
```

Ожидается код **200** (или редирект **3xx**). Если **`000`** / «Couldn't connect» при живых подах — смотрите файрвол (п. 7); если поды не в `Running` — сначала устраните **ImagePullBackOff** (п. 11).

---

#### 7. Разрешите вход с интернета

В **панели провайдера** (Hostiman и т.п.) откройте inbound **TCP 30080** и **TCP 22** (SSH) — это отдельно от UFW на машине.

На VPS с **ufw**:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 30080/tcp
sudo ufw status
```

Если в выводе **`Status: inactive`**, правила только сохранены, **трафик пока не фильтруется** UFW. Чтобы включить файрвол:

```bash
sudo ufw enable
sudo ufw status verbose
```

Должно быть **`Status: active`** и в списке разрешения для **22** и **30080**. Перед `enable` убедитесь, что **22/tcp** уже разрешён, чтобы не потерять SSH.

---

#### 8. Откройте приложение в браузере (Swagger)

- `http://81.90.182.174:30080/docs`
- или `http://alekseeva.h1n.ru:30080/docs`

Порт должен совпадать с `nodePort` в `service.yaml`. Домен должен иметь **A-запись** на тот же IP, что у VPS.

**Если страница не открывается:** сервис не должен быть **`ClusterIP`** — для доступа из браузера нужен **NodePort** и поле **`nodePort: 30080`** (см. п. 4). Дополнительно проверьте поды (п. 6), UFW и файрвол провайдера (п. 7).

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

#### 11. Частые проблемы и диагностика

Этот пункт — **справочник**: возвращайтесь к нему при ошибках на любом из шагов 5–10.

**`kubectl`: `permission denied` для `/etc/rancher/k3s/k3s.yaml`**  
Пока не скопировали kubeconfig в `~/.kube/config` и не задали `KUBECONFIG` (п. 2), вызывайте **`sudo kubectl …`**.

---

**Образ в Docker Hub и тег**

Имя и тег в трёх местах должны **совпадать**:

1. `docker build -t ВАШ_LOGIN/lab1-api:ТЕГ .`
2. `docker push ВАШ_LOGIN/lab1-api:ТЕГ`
3. в `deployment.yaml`: `image: ВАШ_LOGIN/lab1-api:ТЕГ`

Строка вида `docker push nesrv2026/lab1-api:tagname` в шпаргалках — **заглушка**: вместо **`tagname`** укажите реальный тег (**`latest`**, **`v1`** и т.д.). На [hub.docker.com](https://hub.docker.com/) в репозитории на вкладке **Tags** должен быть этот тег **до** того, как k3s сделает pull.

---

**`ImagePullBackOff` / `ErrImagePull`**

Посмотреть причину:

```bash
kubectl describe pod -l app=lab1-api | sed -n '/Events:/,$p'
```

(или `sudo kubectl`, если без `KUBECONFIG`.)

| Сообщение в Events | Что делать |
|--------------------|------------|
| **`not found`** / `failed to resolve reference` | Образа с таким именем/тегом **нет** в registry. Соберите, запушьте, проверьте теги на Docker Hub; в `deployment.yaml` то же `image:`. |
| **`unauthorized`** / **`pull access denied`** | Часто **приватный** репозиторий. Создайте секрет: `kubectl create secret docker-registry regcred --docker-server=https://index.docker.io/v1/ --docker-username=… --docker-password=… --docker-email=…` и в `deployment.yaml` в `spec.template.spec` добавьте `imagePullSecrets: [{ name: regcred }]`, затем `kubectl apply -f deployment.yaml`. |
| **`toomanyrequests`** | Лимит анонимных pull с Docker Hub; войдите в Hub через **`imagePullSecrets`** (как выше). |

Проверка pull с узла (диагностика):

```bash
sudo crictl pull ВАШ_LOGIN/lab1-api:latest
```

---

**Сайт / `curl` на `:30080` не отвечает**

1. Поды **`Running`**, **`1/1`** — иначе NodePort некому обслуживать.  
2. Сервис — **NodePort**, в `get svc` вид **`80:30080/TCP`**.  
3. **UFW** активен и разрешён **30080**; в панели провайдера открыт **TCP 30080**.

---

**`kubectl get pods … -w` после выката**

Видны **старые** поды в **`Terminating`** / **`Completed`** и **новые** в **`Running 1/1`** — это **нормально** при rolling update. Остановите поток (**Ctrl+C**), финальное состояние:

```bash
kubectl get pods -l app=lab1-api
```

Должны остаться только поды в **`Running`**.

---

## GitOps (опционально): Argo CD

**Когда читать:** после того, как **лабораторное приложение уже работает** (поды `Running`, при необходимости открыт **NodePort**), и понятен **ручной выкат** через `kubectl`. Этот раздел **не заменяет** шаги выше: он показывает **другой способ CD** (pull из Git).

Если включили Argo CD для тех же манифестов, **не смешивайте** постоянно **ручной `kubectl apply`** и **синхронизацию из Argo CD** для одного и того же Deployment без договорённости — возможны «откаты» состояния при следующем Sync.

### Зачем это в курсе

В базовой части методички CD строится так: **GitHub Actions** по SSH вызывает **`kubectl`** на VPS (**push**). В **GitOps** наоборот: **желаемое состояние** описано в Git, а контроллер в кластере **периодически подтягивает** репозиторий и применяет манифесты (**pull**). Источник правды — **Git**, а не последняя команда из пайплайна.

Среди инструментов (**Flux**, **Argo CD** и др.) для занятия удобнее **Argo CD**:

- **наглядно:** веб-интерфейс — статус приложения, синхронизация с репозиторием, отклонения (drift);
- **проще донести идею:** после `git push` студент **видит** в UI, как кластер «догоняет» репозиторий;
- **установка на k3s:** один манифест из официальной документации, без отдельного «бутстрапа» как у Flux.

**Flux** имеет смысл, если важнее минимум сервисов и всё в YAML/CLI; для демонстрации на паре чаще выигрывает **Argo CD**.

---

### Условия на VPS

- **Ресурсы:** Argo CD — набор подов в namespace `argocd`; на слабом VPS оставьте **Traefik отключённым** (`disable: traefik` в k3s), чтобы не конкурировать с **nginx** на 80/443 (см. **`k3s_traefik_nginx_conflict.md`**).
- **Доступ к UI:** проще всего на занятии использовать **`kubectl port-forward`** (не занимает 80/443 на хосте). Проброс HTTPS с сервера:

```bash
# после установки Argo CD (см. ниже)
kubectl port-forward svc/argocd-server -n argocd 8443:443 --address 127.0.0.1
```

Дальше в браузере на VPS (или через SSH tunnel с вашего ПК): `https://127.0.0.1:8443` — предупреждение о сертификате можно принять в учебных целях.

Альтернатива: изменить тип сервиса **`argocd-server`** на **NodePort** и открыть порт в UFW/панели провайдера — наглядно с другой машины, но больше настроек и вопросов безопасности.

---

### Установка Argo CD (официальный манифест)

На машине с настроенным **`kubectl`** к k3s (на VPS или с ПК при корректном `KUBECONFIG`):

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Дождитесь готовности подов:

```bash
kubectl get pods -n argocd -w
```

Пароль начального пользователя **`admin`**:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo
```

Войдите в UI под **`admin`** и этим паролем; после занятия смените пароль или отключите начальный секрет по [документации Argo CD](https://argo-cd.readthedocs.io/).

---

### Подключить репозиторий с манифестами `k8s/`

1. В UI: **Applications → New App** (или создайте YAML **Application** и примените `kubectl apply -f`).
2. Укажите **URL** GitHub-репозитория (для **приватного** репо добавьте учётные данные в **Settings → Repositories** в Argo CD).
3. **Revision:** ветка (например `main`).
4. **Path:** каталог **`k8s`** (если манифесты лежат в корне репо — укажите `.` или нужный подкаталог).
5. **Cluster:** `https://kubernetes.default.svc` (текущий кластер), namespace **`default`** (или тот, куда вы деплоите).

Сохраните приложение и выполните **Sync** — Argo CD применит **`deployment.yaml`** и **`service.yaml`** из Git. Дальнейшие изменения в Git после **commit/push** можно подтянуть кнопкой **Refresh/Sync** или включить автоматический политикой sync (осторожно в проде; для учебы удобно).

---

### Связка с CI (образ + GitOps)

Типичная схема:

1. **CI** по-прежнему собирает образ и делает **`docker push`** в registry.
2. В **`deployment.yaml`** в Git обновляется поле **`image:`** (новый тег) — вручную, отдельным коммитом или шагом в GitHub Actions (**commit** в репозиторий с `GITHUB_TOKEN`).
3. **Argo CD** видит новый коммит и синхронизирует кластер — поды пересоздаются с новым образом (при **`imagePullPolicy: Always`** или смене тега).

Так **сборка** остаётся в CI, а **выкат манифестов** — в зоне ответственности GitOps.

---

### Что не входит в минимум методички

- **Argo CD Image Updater** и автоматическое обновление тегов из registry — отдельная тема.
- **Отдельный GitOps-репозиторий** только под `k8s/` — продвинутый вариант; для учебы достаточно папки **`k8s/`** в том же репозитории, что и приложение.

---

### Кратко

| | Push-CD (основа методички) | GitOps (Argo CD) |
|---|---------------------------|------------------|
| Кто применяет манифесты | CI по SSH + `kubectl` | Argo CD из кластера |
| Источник правды на практике | последний успешный пайплайн + Git | **Git** (репозиторий) |
| Наглядность | логи Actions | **UI** Argo CD |

---

