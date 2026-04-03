# Практическое занятие

## Деплой и CI/CD на VPS (Kubernetes / k3s)

## 1. Цель работы

Научиться собирать и публиковать Docker-образ через CI, затем автоматически выкатывать приложение на VPS в кластер **Kubernetes (k3s)** через CD. **Опционально:** познакомиться с **GitOps** и **Argo CD** как наглядной pull-моделью выката (состояние кластера из Git).

---

## 2. Что получите в итоге

- после `git push` запускается CI-пайплайн (в примере **`.github/workflows/ci-cd.yml`** — сборка и выкат, **без** отдельных шагов тестов/линтеров, их при желании добавьте сами);
- собирается Docker-образ и публикуется в registry;
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

**Как читать документ дальше:** блоки идут в **рабочем порядке** — сначала **§5 Docker Hub** (образ в registry), затем **ручной деплой на VPS** (нумерованные **п. 1–10**: k3s, `kubectl`, сеть, в т.ч. **п. 8 — браузер**), затем **CD через GitHub Actions**. После **п. 11** — **типичные ошибки**. **GitOps (Argo CD)** в конце — **своя нумерация шагов 0–9** (не путать с п. 8 ручного деплоя). Базовую лабу можно пройти без Actions и без Argo.

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

Файл **`.github/workflows/ci-cd.yml`** лежит в репозитории (пример ниже). Подробная **привязка GitHub → VPS** (секреты, SSH, команды на сервере) — в разделе **«CD через GitHub Actions»** после ручного деплоя.

---

## 5. Публикация образов в Docker Hub

Образ должен лежать в **публичном или приватном registry**, иначе k3s на VPS не сможет выполнить `pull` с Docker Hub — только локальная сборка на вашем ПК недостаточна.

В **CI** образ собирается и **пушится** в registry. В манифестах Kubernetes указывается полное имя:

`<registry>/<пользователь или org>/<репозиторий>:<тег>`

Ниже в примерах workflow используется **Docker Hub**. **GHCR** — равноценная альтернатива для репозитория на GitHub.

---

### Docker Hub

#### Подготовка аккаунта и токена

1. Зарегистрируйтесь на [hub.docker.com](https://hub.docker.com/). Запомните **логин** (Docker ID) — он участвует в имени образа.
2. Создайте **Access Token** (для входа из CLI и для GitHub Actions): *Account Settings → Security → New Access Token* — права **Read & Write** (или аналог для загрузки образов). **Пароль при `docker login` вводить не нужно** — вместо пароля вставляют этот токен.
3. Имя образа на Docker Hub всегда в виде **ВАШ_LOGIN/имя_репозитория:тег** (например `ivanov/lab1-api:latest`). Репозиторий на сайте можно создать заранее (*Repositories → Create*), но чаще он **появляется автоматически** после первого успешного `docker push` с таким именем.

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

**Пример ниже — учебный** (чужой VPS); подставьте **своего** пользователя Linux на сервере, **IP** или **DNS** из панели провайдера.

```bash
ssh alekseeva@81.90.182.174
```

**Имя хоста (DNS), пример:** `alekseeva.h1n.ru` — при настроенной A-записи на IP VPS:

```bash
ssh alekseeva@alekseeva.h1n.ru
```

Дальнейшие шаги выполняются **на VPS** в SSH-сессии. Подставьте вместо `DOCKERHUB_USERNAME` свой логин Docker Hub.

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

Если в п. 5 вы применяли манифесты через **`sudo kubectl`**, здесь тоже используйте **`sudo kubectl set image`** и **`sudo kubectl rollout status`**.

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

Этот пункт — **справочник**: возвращайтесь к нему при ошибках на любом из шагов 5–10 и при отладке **CD через GitHub Actions** (следующий раздел).

**`kubectl`: `permission denied` для `/etc/rancher/k3s/k3s.yaml`**  
Пока не скопировали kubeconfig в `~/.kube/config` и не задали `KUBECONFIG` (п. 2), вызывайте **`sudo kubectl …`**.

---

**GitHub Actions: deploy падает по SSH**

См. раздел **«CD через GitHub Actions»**: ключ в **`authorized_keys`**, секрет **`VPS_K8S_DIR`** = **абсолютный** путь к каталогу с `deployment.yaml` (как после `cd ~/ИМЯ_РЕПО/k8s` на VPS — выполните `pwd` и скопируйте), для **`sudo kubectl`** без пароля — отдельная строка в **`sudoers`** для пользователя **`VPS_USER`** (учебный вариант).

---

**Поды `Running`, но сразу `CrashLoopBackOff` / много рестартов**

Частая причина — **`livenessProbe`** / **`readinessProbe`**: путь HTTP в манифесте должен существовать в приложении и отвечать **2xx** быстрее **`timeoutSeconds`**. В этом репозитории FastAPI отдаёт **`GET /health`** — в **`deployment.yaml`** для пробы указан **`/health`**. Если поменяете путь в коде или в YAML несогласованно, kubelet будет перезапускать контейнер.

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

### CD через GitHub Actions: привязка репозитория к VPS

После того как **вручную** проверены k3s, `kubectl` и первый деплой (шаги выше), имеет смысл автоматизировать: при **`git push`** в GitHub **собирается образ**, пушится в **Docker Hub**, по **SSH** на VPS выполняется **`kubectl set image`** (или `apply`).

**Цепочка:** GitHub (runner) → registry (Docker Hub) → SSH → ваш пользователь на VPS → `sudo kubectl` → k3s.

#### Предпосылки на VPS

1. Уже выполнены **п. 1–5** ручного деплоя: k3s, `~/.kube/config`, **`KUBECONFIG`** в `~/.bashrc` (или готовность вызывать `sudo kubectl --kubeconfig "$HOME/.kube/config"`).
2. Известен **абсолютный путь** к каталогу с **`deployment.yaml`** на VPS: зайдите по SSH, выполните `cd ~/ИМЯ_РЕПО/k8s` (как в **п. 4** ручного деплоя), затем **`pwd`** — эту строку укажите в секрете **`VPS_K8S_DIR`**. Пример: репозиторий клонировали в **`~/my-lab`** → путь **`/home/ВАШ_USER/my-lab/k8s`** (не путать с именем репозитория на GitHub).
3. Пользователь VPS, под которым заходит **GitHub Actions по SSH**, может выполнять **`sudo kubectl`** **без интерактивного пароля** (настроить **`/etc/sudoers.d/…`** для этого пользователя и команды kubectl — учебный вариант; в проде лучше отдельный ключ и минимальные права).

#### Ключ SSH для GitHub

1. На **своём ПК** (или на VPS) сгенерируйте пару ключей **только для CI**, без passphrase (удобно для runner):

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ./gha_k3s_deploy -N ""
```

2. **Публичный** ключ `gha_k3s_deploy.pub` добавьте на VPS в **`~/.ssh/authorized_keys`** того пользователя, от имени которого пойдёт деплой (тот же, что в секрете **`VPS_USER`**).

3. **Приватный** ключ `gha_k3s_deploy` целиком (включая строки `BEGIN` / `END`) сохраните в GitHub: репозиторий → **Settings → Secrets and variables → Actions → New repository secret** → имя **`VPS_SSH_KEY`**, значение — содержимое файла.

**Не коммитьте** приватный ключ в Git.

#### Секреты GitHub Actions (репозиторий)

| Имя секрета | Назначение |
|-------------|------------|
| **`DOCKERHUB_USERNAME`** | Логин Docker Hub (как в имени образа). |
| **`DOCKERHUB_TOKEN`** | [Access Token](https://hub.docker.com/settings/security) Docker Hub (**Read & Write** для push). |
| **`VPS_HOST`** | IP или DNS VPS, например `81.90.182.174` или `alekseeva.h1n.ru`. |
| **`VPS_USER`** | SSH-пользователь на VPS (тот, у кого в `authorized_keys` ключ CI). |
| **`VPS_SSH_KEY`** | Приватный ключ (см. выше). |
| **`VPS_K8S_DIR`** | Абсолютный путь к каталогу с `deployment.yaml` (результат **`pwd`** в `~/ИМЯ_РЕПО/k8s` на VPS). |

При необходимости нестандартного SSH-порта добавьте в workflow параметр `port` у шага SSH (см. [appleboy/ssh-action](https://github.com/appleboy/ssh-action)).

#### Что делает пример `ci-cd.yml`

1. **Триггер:** push в ветки **`main`** или **`master`** (при необходимости измените в YAML).
2. **Сборка:** `docker build` из корня репозитория (где **Dockerfile**), теги образа: **`GITHUB_SHA`** (уникально на коммит) и **`latest`**.
3. **Публикация:** `docker login` + `docker push` в Docker Hub.
4. **Деплой:** по SSH одна команда вида **`kubectl set image deployment/lab1-api lab1-api=$DOCKERHUB_USERNAME/lab1-api:$GITHUB_SHA`**, затем **`kubectl rollout status`**. Имя деплоймента и контейнера должны совпадать с вашим **`deployment.yaml`**.

Так k3s **подтягивает новый слой** по смене тега (не полагается только на `latest` с **`imagePullPolicy: IfNotPresent`**).

**Совместимость с GitOps (Argo CD):** этот workflow — **push-CD** (SSH + `kubectl`), он **не обновляет** манифесты в Git. Если на кластере **Argo CD** уже ведёт те же ресурсы, не запускайте оба сценария без понимания (см. предупреждение в разделе Argo CD). Для **только GitOps** отключите job **`deploy`** в **`ci-cd.yml`** или замените его на шаг «commit нового `image:` в репозиторий».

#### Проверка пайплайна

1. Закоммитьте изменение, убедитесь, что секреты заданы: **Settings → Secrets and variables → Actions**.
2. Вкладка **Actions** → выберите последний workflow → шаги **build** и **deploy** должны быть зелёными.
3. На VPS: `kubectl get pods -l app=lab1-api` — новые поды после выката.

Типичные ошибки: **Permission denied (publickey)** — ключ не в `authorized_keys` или неверный **`VPS_USER`**; **`sudo: a password is required`** — не настроен passwordless sudo для `kubectl`; **`unable to resolve`** — неверный **`VPS_HOST`**.

Файл в репозитории: **`.github/workflows/ci-cd.yml`**.

---

## GitOps (опционально): Argo CD

**Когда читать:** после того, как **лабораторное приложение уже работает** (поды `Running`, при необходимости открыт **NodePort**), и понятен **ручной выкат** через `kubectl`. Раздел **не заменяет** шаги выше: это **другой способ CD** (pull из Git).

**Где выполнять команды:** на **VPS в SSH** (как в основной части) или на **своём ПК**, если `kubectl` настроен на тот же кластер (`KUBECONFIG`). Вывод в шагах может немного отличаться по времени и именам подов.

**Пример манифеста `Application`:** файл **`k8s/argocd-application.yaml`** в репозитории — подставьте свой **`repoURL`** и ветку (**`targetRevision`**).

Если включили Argo CD для тех же манифестов, **не смешивайте** постоянно **ручной `kubectl apply`** и **синхронизацию из Argo CD** для одного и того же Deployment без договорённости — возможны «откаты» при следующем Sync.

### Зачем это в курсе

В базовой части методички CD строится так: **GitHub Actions** по SSH вызывает **`kubectl`** на VPS (**push**). В **GitOps** наоборот: **желаемое состояние** описано в Git, а контроллер в кластере **периодически подтягивает** репозиторий и применяет манифесты (**pull**). Источник правды — **Git**, а не последняя команда из пайплайна.

Среди инструментов (**Flux**, **Argo CD** и др.) для занятия удобнее **Argo CD**:

- **наглядно:** веб-интерфейс — статус приложения, синхронизация с репозиторием, отклонения (drift);
- **проще донести идею:** после `git push` студент **видит** в UI, как кластер «догоняет» репозиторий;
- **установка на k3s:** один манифест из официальной документации, без отдельного «бутстрапа» как у Flux.

**Flux** имеет смысл, если важнее минимум сервисов и всё в YAML/CLI; для демонстрации на паре чаще выигрывает **Argo CD**.

---

### Шаг 0. Предпосылки

1. **k3s** (или другой Kubernetes) работает, `kubectl get nodes` показывает **Ready**.
2. **Ресурсы:** Argo CD — набор подов в namespace **`argocd`**. На VPS с **nginx** на 80/443 держите **Traefik в k3s отключённым** (`disable: traefik` в `/etc/rancher/k3s/config.yaml`), иначе см. **`k3s_traefik_nginx_conflict.md`**.
3. Репозиторий с манифестами в **`k8s/`** доступен с GitHub: для **публичного** репо достаточно HTTPS; для **приватного** позже добавьте учётные данные в Argo CD → **Settings → Repositories**.

---

### Шаг 1. Namespace для Argo CD

**Зачем:** компоненты Argo CD изолированы в своём namespace.

```bash
kubectl create namespace argocd
```

Ожидаемо: `namespace/argocd created`. Если namespace уже есть — сообщение об ошибке можно игнорировать.

---

### Шаг 2. Установка (официальный манифест)

**Зачем:** CRD **`Application`**, деплойменты **`argocd-server`**, **`argocd-repo-server`**, Redis, контроллеры.

```bash
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

**Возможная ошибка** (иногда на Docker Desktop и отдельных версиях Kubernetes): для CRD **ApplicationSet** — `metadata.annotations: Too long`. Остальные ресурсы часто уже созданы; проверьте поды (шаг 3). Подробности — [issues Argo CD](https://github.com/argoproj/argo-cd/issues) или фиксированная версия манифеста.

---

### Шаг 3. Дождаться готовности подов

**Зачем:** пока **`argocd-server`** и **`argocd-repo-server`** не в **Running**, UI и клон Git не работают.

```bash
kubectl get pods -n argocd -w
```

Остановите просмотр (**Ctrl+C**), когда у основных подов **READY 1/1**. Снимок:

```bash
kubectl get pods -n argocd
```

---

### Шаг 4. Пароль пользователя `admin`

**Зачем:** первый вход в веб-UI. Сохраните пароль **вне Git**.

**Linux / macOS / Git Bash:**

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo
```

**PowerShell:**

```powershell
$p = kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}'
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($p))
```

После занятия смените пароль или настройте SSO по [документации Argo CD](https://argo-cd.readthedocs.io/).

---

### Шаг 5. Веб-интерфейс (`port-forward`)

**Зачем:** не занимать 80/443 на хосте; для учебы безопаснее, чем сразу выставлять NodePort в интернет.

В **отдельном** терминале (процесс должен оставаться запущенным):

```bash
kubectl port-forward svc/argocd-server -n argocd 8443:443 --address 127.0.0.1
```

- Браузер: **`https://127.0.0.1:8443`**
- Логин: **`admin`**, пароль — из шага 4.
- Предупреждение о сертификате в учебных целях можно принять.

**Доступ с ПК к UI на VPS:** туннель SSH, например:

```bash
ssh -L 8443:127.0.0.1:8443 пользователь@IP_VPS
```

На VPS в другом сеансе выполните тот же **`port-forward`**; браузер на ПК — снова **`https://127.0.0.1:8443`**.

**Альтернатива:** тип сервиса **`argocd-server`** → **NodePort**, порт открыть в UFW и у провайдера — удобно с другой машины, но больше настроек и вопросов безопасности.

---

### Шаг 6. Объявить `Application` (Git → кластер)

**Зачем:** указать репозиторий, ветку, каталог с YAML и целевой namespace в кластере.

#### Вариант A — через UI

1. **Applications → New App** (или **Edit as YAML**).
2. **Application name:** например `lab1-k8s`.
3. **Project:** `default`.
4. **Sync policy:** для начала **Manual**; **AUTO-SYNC** — осторожно в проде.
5. **Repository URL:** `https://github.com/ВАШ_АККАУНТ/ВАШ_РЕПО.git`
6. **Revision:** `main` или `master`.
7. **Path:** `k8s` (каталог с `deployment.yaml` и `service.yaml`).
8. **Cluster URL:** `https://kubernetes.default.svc`
9. **Namespace:** `default` (или ваш).

**Create** → **Sync** / **Synchronize**. Дальнейшие изменения в Git и повторный выкат — **GitOps, шаг 8** (не путать с **ручным п. 8 «браузер»** выше).

#### Вариант B — манифест в репозитории

Подставьте **`repoURL`** и **`targetRevision`** в **`k8s/argocd-application.yaml`**, затем:

```bash
kubectl apply -f k8s/argocd-application.yaml
```

В примере по умолчанию **без** блока **`automated`** в `syncPolicy` — после создания нажмите **Sync** в UI (или CLI: `argocd app sync lab1-k8s`, если установлен **argocd** CLI). Раскомментировав **`automated`** в YAML, синхронизация пойдёт по расписанию сама.

Для **приватного** репозитория сначала настройте доступ в **Settings → Repositories**.

---

### Шаг 7. Проверка

```bash
kubectl get application -n argocd
kubectl get pods -n default -l app=lab1-api
```

В UI ожидаются статусы **Synced** и **Healthy** (после успешного pull образов из registry).

---

### Шаг 8 (GitOps). Деплой через Argo CD после правок в Git

Это **основной учебный цикл GitOps** (номер **8** относится только к разделу Argo CD, не к **ручному п. 8** про браузер): кластер приводится к состоянию **последнего коммита** в отслеживаемой ветке; **SSH на VPS для `kubectl apply` не нужен** (в отличие от раздела «CD через GitHub Actions»).

#### 8.1. Убедитесь, что приложение уже синхронизировано один раз

В UI у **Application** статусы **Synced** и **Healthy** (как в шаге 7). Если включён только ручной sync — после первого создания приложения вы уже нажимали **Sync**.

#### 8.2. Внесите изменение в манифесты в Git

На **своём ПК** (или в веб-редакторе GitHub) измените файлы в каталоге **`k8s/`**, например:

- **`deployment.yaml`:** другое значение **`replicas`**, другой тег в **`image:`** (образ должен уже существовать в registry), правка **`livenessProbe`** и т.д.;
- или **`service.yaml`** (осторожно с **`nodePort`** — не занимайте чужой порт).

Сохраните коммит и отправьте в **ту же ветку**, которую указали в **Application** (**`targetRevision`** / **Revision**):

```bash
git add k8s/deployment.yaml
git commit -m "chore(k8s): обновление манифеста для Argo CD"
git push origin main
```

(Вместо **`main`** укажите **`master`**, если так настроено в Argo CD.)

#### 8.3. Подтянуть изменения в кластер

- **Ручная синхронизация:** в UI Argo CD откройте приложение → **Refresh** (подтянуть коммиты с GitHub) → при статусе **OutOfSync** нажмите **Sync** / **Synchronize**.  
- **Автоматическая:** если в **`Application`** включён **`syncPolicy.automated`**, Argo CD сам периодически опрашивает репозиторий и применит изменения без кнопки (задержка до ~3 минут по умолчанию или настройте [webhook](https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/#argocd-server-and-ui-ingress-certificate)).

#### 8.4. Проверка

В UI: снова **Synced** / **Healthy**, в **History** видна новая ревизия (коммит).

В терминале (на VPS или с `kubectl` к кластеру):

```bash
kubectl get pods -l app=lab1-api
kubectl describe deployment lab1-api | sed -n '1,40p'
```

Должны отражаться ваши правки (число подов, образ и т.д.). Если меняли только **`image:`**, убедитесь, что тег **уже запушен** в Docker Hub, иначе поды уйдут в **ImagePullBackOff** (см. п. 11 основной части).

#### 8.5. Связь с CI

Сборка образа по-прежнему делается **локально** или **GitHub Actions** (без шага SSH `kubectl`, если вы на **чистом GitOps**). После **`docker push`** обновите **`image:`** в **`deployment.yaml`**, сделайте **commit + push** — затем снова шаги **8.3–8.4**. Подробнее — шаг 9.

---

### Шаг 9. Связка с CI (образ + GitOps)

1. **CI** собирает образ и делает **`docker push`** в registry.
2. В **`deployment.yaml`** в Git обновляют поле **`image:`** (новый тег) — вручную, коммитом или шагом GitHub Actions с **`GITHUB_TOKEN`**.
3. **Argo CD** обнаруживает новый коммит (опрос / webhook) и при включённой политике sync обновляет Deployment — поды пересоздаются при **`imagePullPolicy: Always`** или смене тега.

**Сборка** остаётся в CI, **выкат манифестов** — в зоне GitOps. **Не смешивайте** без договорённости постоянный **`kubectl apply`** тех же файлов и **Argo CD Sync**.

---

### Удаление Argo CD с кластера (по желанию)

```bash
kubectl delete -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl delete namespace argocd
```

Остаточные CRD и порядок действий — в [документации по uninstall](https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/#uninstall).

---

### Что не входит в минимум методички

- **Argo CD Image Updater** и автообновление тегов из registry — отдельная тема.
- **Отдельный репозиторий** только под `k8s/` — продвинутый вариант; для учебы достаточно папки **`k8s/`** в том же репо, что и приложение.

---

### Кратко

| | Push-CD (основа методички) | GitOps (Argo CD) |
|---|---------------------------|------------------|
| Кто применяет манифесты | CI по SSH + `kubectl` | Argo CD из кластера |
| Источник правды на практике | последний успешный пайплайн + Git | **Git** (репозиторий) |
| Наглядность | логи Actions | **UI** Argo CD |

---

