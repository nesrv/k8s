# Методические указания

## Лабораторная работа 1

### Первый запуск собственного приложения в Kubernetes (вариант «свой образ»)


| Поле             | Заполняется по месту                                                    |
| ---------------- | ----------------------------------------------------------------------- |
| **Дисциплина**   | Разработка высоконагруженных систем (или по учебному плану)             |
| **Тема модуля**  | Оркестрация контейнеров, основы Kubernetes                              |
| **Время**        | 2–4 академических часа (в зависимости от подготовки группы)             |
| **Форма отчёта** | выполнение чеклиста (разд. 16) + краткий письменный ответ по содержанию |


**Для кого:** студенты с **нулевым** опытом Kubernetes.  
**Что уже должны уметь:** Docker, Dockerfile, сборка образа, основы HTTP API (в методичке используется **FastAPI**).  
**Связь с курсом:** вводная лекция `lect_k8s.md` (Pod, Deployment, Service).

### Преамбула: Kubernetes («k8s») и k3s

Совет «начать с k3s» чаще всего относится к **способу развернуть кластер**, а не к «другому предмету вместо Kubernetes».

**Kubernetes** — это платформа и **единый API** оркестрации: те же ресурсы (`Pod`, `Deployment`, `Service`), те же манифесты и **kubectl**. **k3s** — **дистрибутив** (упрощённая поставка) того же Kubernetes: меньше накладных расходов, проще поднять на одном сервере (VPS, edge). Изучая k3s, вы изучаете **Kubernetes**; отличается в основном установка и состав компонентов control plane, а не модель работы с приложениями.

В **этой** работе локальный кластер на ПК по умолчанию поднимается через **minikube**; альтернативы — **kind** и **k3d** (у **k3d** внутри Docker крутится **k3s**). Отдельная установка **k3s** на виртуальную машину или VPS обычно выносится в занятия про деплой на сервер (например, CI/CD).

---

## Содержание

1. [Цели работы](#1-цели-работы)
2. [Входные знания и перечень программного обеспечения](#2-входные-знания-и-перечень-программного-обеспечения)
3. [Краткий словарь терминов](#3-краткий-словарь-терминов)
4. [Утилита kubectl: назначение и установка](#4-утилита-kubectl-назначение-и-установка)
5. [Локальный кластер Kubernetes](#5-локальный-кластер-kubernetes)
6. [Проверка связи kubectl с кластером](#6-проверка-связи-kubectl-с-кластером)
7. [Мини-приложение на FastAPI](#7-мини-приложение-на-fastapi)
8. [Сборка образа (Dockerfile)](#8-сборка-образа-dockerfile)
9. [Манифесты Deployment и Service](#9-манифесты-deployment-и-service)
10. [Загрузка образа в кластер](#10-загрузка-образа-в-кластер)
11. [Развёртывание: kubectl apply](#11-развёртывание-kubectl-apply)
12. [Логи и диагностика](#12-логи-и-диагностика)
13. [Доступ к приложению: port-forward](#13-доступ-к-приложению-port-forward)
14. [Дополнительные эксперименты](#14-дополнительные-эксперименты)
15. [Типичные проблемы и решения](#15-типичные-проблемы-и-решения)
16. [Критерии зачёта и содержание отчёта](#16-критерии-зачёта-и-содержание-отчёта)
17. [Вариант с Django](#17-вариант-с-django)
18. [Направления дальнейшего изучения](#18-направления-дальнейшего-изучения)

---

## 1. Цели работы

По завершении лабораторной работы обучающийся должен уметь:

1. Объяснить назначение объектов **Deployment** и **Service** в Kubernetes простыми словами.
2. Собрать контейнерный образ приложения и обеспечить его доступность для **kubelet** в локальном кластере **без** публикации образа в публичный registry.
3. С помощью **kubectl** применить манифесты, проверить состояние подов и просмотреть логи.
4. Организовать доступ к сервису с хостовой машины через `**kubectl port-forward`**.
5. Выполнить масштабирование числа реплик и продемонстрировать **восстановление** пода после удаления.

---

## 2. Входные знания и перечень программного обеспечения

### 2.1. Входные знания

- работа в командной строке (терминал, PowerShell);  
- сборка и запуск контейнера из Dockerfile;  
- понимание порта приложения (в методичке — TCP **8000**).

### 2.2. Программное обеспечение (установить до занятия или на занятии по инструкции преподавателя)


| Компонент                                                        | Назначение                                                    |
| ---------------------------------------------------------------- | ------------------------------------------------------------- |
| **Docker Desktop** (Windows/macOS) или **Docker Engine** (Linux) | Сборка образа `lab1-api`                                      |
| **kubectl**                                                      | Клиент командной строки для API Kubernetes                    |
| **minikube** / **kind** / **k3d**                                | Локальный кластер Kubernetes (достаточно **одного** варианта) |


Официальная точка входа по инструментам: [Kubernetes — Install Tools](https://kubernetes.io/docs/tasks/tools/).

### 2.3. Рекомендуемая структура каталогов для отчёта

```text
k8s-lab1/
  main.py
  requirements.txt
  Dockerfile
  k8s/
    deployment.yaml
    service.yaml
  report.md         
```

---

## 3. Краткий словарь терминов

Перед выполнением работы просмотрите таблицу.


| Термин            | Пояснение                                                                              |
| ----------------- | -------------------------------------------------------------------------------------- |
| **Кластер**       | Совокупность узлов, на которых работает Kubernetes; управление — через единый API.     |
| **Под (Pod)**     | Минимальная единица планирования; чаще всего один контейнер.                           |
| **Deployment**    | Объект API: поддерживать заданное число реплик подов и обновлять их по правилам.       |
| **Service**       | Стабильная точка доступа к группе подов (DNS-имя и виртуальный IP внутри кластера).    |
| **Образ (image)** | Собранный артефакт Docker; в манифесте задаётся полем `image`.                         |
| **Namespace**     | Логическая область имён объектов; на первой работе допустимо использовать `default`.   |
| **kubectl**       | Программа-клиент: отправляет в API запросы на создание, изменение и просмотр ресурсов. |


---

## 4. Утилита kubectl: назначение и установка

### 4.1. Назначение

**kubectl** — клиент на вашем ПК: по HTTPS обращается к API кластера, настройки подключения хранит в **kubeconfig** (`%USERPROFILE%\.kube\config` в Windows, `~/.kube/config` в macOS/Linux). Без kubectl лабораторную по этой методичке не выполнить.

Пока локальный кластер **не запущен**, файл kubeconfig может отсутствовать, быть пустым или **без выбранного контекста** — тогда `kubectl config current-context` выдаст ошибку; это нормально. Команды `kubectl config get-contexts` и выбор контекста выполняйте **после** [разд. 5](#5-локальный-кластер-kubernetes) и шага 1 [разд. 6](#6-проверка-связи-kubectl-с-кластером).

Желательно, чтобы версия клиента не расходилась с версией кластера более чем на **одну минорную**; для локального учебного кластера обычно хватает актуального стабильного клиента.

### 4.2. Уже установлен?

```text
kubectl version --client
```

Если видите `Client Version` — клиент есть. Если «команда не найдена» — установите по п. 4.4–4.6. Если версия **старее нужной** — см. п. 4.3.

---

### 4.3. Обновление до **v1.35.3** (пример: сейчас v1.34.1)

Если `kubectl version --client` показывает, например:

```text
Client Version: v1.34.1
Kustomize Version: v5.7.1
```

а требуется клиент **v1.35.3**, **замените бинарник** `kubectl` (процедура та же, что при первой установке). Строка **Kustomize Version** идёт в одной сборке с `kubectl` и обновится вместе с ним после замены файла.

**Windows (amd64):** узнайте, какой файл сейчас в PATH:

```powershell
where kubectl
```

Скачайте [kubectl.exe v1.35.3](https://dl.k8s.io/release/v1.35.3/bin/windows/amd64/kubectl.exe) и **перезапишите** им файл по этому пути (или положите в ту же папку, что уже в PATH). Закройте все окна терминала, откройте новое и проверьте:

```powershell
kubectl version --client
```

Ожидаемо: `Client Version: v1.35.3` (номер Kustomize может отличаться от прежнего — это нормально).

**Chocolatey:** `choco upgrade kubernetes-cli`  
**Scoop:** `scoop update kubectl`

**macOS** — явная версия (Apple Silicon — `arm64`, Intel — `amd64`):

```bash
curl -LO "https://dl.k8s.io/release/v1.35.3/bin/darwin/arm64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/kubectl
kubectl version --client
```

С **Homebrew** обычно достаточно: `brew upgrade kubectl` (если в формуле уже есть v1.35.3).

**Linux** (x86_64; для arm64 в URL замените `amd64` на `arm64`):

```bash
curl -LO "https://dl.k8s.io/release/v1.35.3/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client
```

---

### 4.4. **Windows** (amd64, Intel/AMD)

**1) Прямая ссылка на `kubectl.exe` (v1.35.3):**

[https://dl.k8s.io/release/v1.35.3/bin/windows/amd64/kubectl.exe](https://dl.k8s.io/release/v1.35.3/bin/windows/amd64/kubectl.exe)

Сохраните файл в папку, например `C:\kubectl\`, добавьте эту папку в **PATH** пользователя (*Параметры → Система → О системе → Доп. параметры → Переменные среды → Path → Изменить*), **закройте и откройте** терминал и выполните: `kubectl version --client`.

**Быстро для текущего окна PowerShell (без перезапуска):**

```powershell
$env:Path = "C:\kubectl;" + $env:Path
kubectl version --client
```

**Другие варианты (по желанию):** `choco install kubernetes-cli` или `scoop install kubectl` (из нового окна терминала — та же проверка).

---

### 4.5. **macOS**

```bash
brew install kubectl
```

Или бинарник (Apple Silicon — `arm64`, Intel — `amd64`):

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/arm64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/
```

Подробности: [Install kubectl on macOS](https://kubernetes.io/docs/tasks/tools/install-kubectl-macos/).

---

### 4.6. **Linux**

Бинарник (x86_64; для arm64 в URL замените `amd64` на `arm64`):

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client
```

Или пакет из репозитория / `snap install kubectl --classic` — см. [Install kubectl on Linux](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/).

Автодополнение для bash/zsh — в [документации kubectl](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_completion/).

---

## 5. Локальный кластер Kubernetes

### 5.1. Когда это делать

Локальный кластер ставят **после**:

1. **Docker** (см. [разд. 2](#2-входные-знания-и-перечень-программного-обеспечения)) — minikube / kind / k3d используют контейнеры или виртуальную машину поверх хоста.
2. **kubectl** (см. [разд. 4](#4-утилита-kubectl-назначение-и-установка)) — дальше в [разд. 6](#6-проверка-связи-kubectl-с-кластером) вы проверяете кластер через `kubectl`.

Итого порядок: Docker → kubectl → **один** из инструментов ниже → проверка в разд. 6.

### 5.2. Какой инструмент выбрать

Нужен **ровно один** — все трое поднимают настоящий Kubernetes на вашей машине, API и объекты (`Pod`, `Deployment`…) те же.


| Инструмент   | Когда удобен                                                                                                                                                                                                    |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **minikube** | **Рекомендуется по умолчанию** для этой работы: много документации, на Windows часто проще старт; все команды в методичке (кроме [разд. 10](#10-загрузка-образа-в-кластер) для kind/k3d) даны для **minikube**. |
| **kind**     | Кластер внутри Docker; типичен в CI. Нужен **уже работающий Docker**.                                                                                                                                           |
| **k3d**      | Обёртка над лёгким **k3s** в Docker; тоже нужен **Docker**.                                                                                                                                                     |


Если преподаватель не указал иначе и вы не уверены — ставьте **minikube** по ссылке из таблицы и следуйте примерам `minikube start` и т.д. ниже.

### 5.3. Установка (официальные инструкции)

Установите выбранный инструмент по документации проекта:


| Инструмент   | Ссылка                                                                                             |
| ------------ | -------------------------------------------------------------------------------------------------- |
| **minikube** | [https://minikube.sigs.k8s.io/docs/start/](https://minikube.sigs.k8s.io/docs/start/)               |
| **kind**     | [https://kind.sigs.k8s.io/docs/user/quick-start/](https://kind.sigs.k8s.io/docs/user/quick-start/) |
| **k3d**      | [https://k3d.io/](https://k3d.io/)                                                                 |


**Windows — быстрая установка minikube через winget** (если доступен [App Installer / winget](https://learn.microsoft.com/windows/package-manager/winget/)):

```powershell
winget install Kubernetes.minikube
```

Закройте и снова откройте терминал (или обновите сессию), затем проверьте: `minikube version`. Выбор драйвера (Docker, Hyper-V и т.д.) и `minikube start` — по ссылке **minikube** в таблице выше.

В тексте ниже в примерах используется **minikube**. Для **kind** и **k3d** команды **загрузки образа** в кластер отличаются — см. [разд. 10](#10-загрузка-образа-в-кластер).

### 5.4. Windows: команда `minikube` не найдена (PATH)

Если `**winget install Kubernetes.minikube`** уже выполнялся, но PowerShell сообщает, что имя `**minikube**` не распознано:

- исполняемый файл обычно лежит в `**C:\Program Files\Kubernetes\Minikube\minikube.exe**`;
- чаще всего папка не попала в **PATH** именно **этого** окна терминала (оно было открыто до установки) или среда разработки не подхватила обновлённый системный PATH.

**Действия:**

1. **Закройте и снова откройте** терминал (при необходимости перезапустите Cursor / VS Code).
2. Чтобы обновить PATH **в текущем** окне PowerShell без перезапуска:

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
minikube version
```

1. Если после перезапуска терминала команда всё ещё не находится — добавьте в **PATH пользователя** каталог `C:\Program Files\Kubernetes\Minikube` (*Параметры → Система → О системе → Дополнительные параметры → Переменные среды → Path*). Либо выполните в PowerShell (один раз для учётной записи пользователя):

```powershell
$dir = "C:\Program Files\Kubernetes\Minikube"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notmatch [regex]::Escape($dir)) {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$dir", "User")
}
```

Снова откройте терминал и проверьте: `minikube version`. Далее — `minikube start` по документации minikube.

---

## 6. Проверка связи kubectl с кластером

1. Запустите локальный кластер (пример для minikube):

```bash
minikube start
```

Для **kind** / **k3d** используйте команды создания кластера из их quick start — после этого в kubeconfig тоже появится контекст.

1. **Kubeconfig и контекст.** После успешного запуска кластера minikube / kind / k3d обычно **сам дописывает** в `%USERPROFILE%\.kube\config` (Windows) или `~/.kube/config` запись о кластере и выставляет текущий контекст.

Проверьте:

```bash
kubectl config get-contexts
kubectl config current-context
```

Для **minikube** имя контекста чаще всего `**minikube`**. Если в таблице есть несколько строк и звёздочка `*` не у нужного кластера:

```bash
kubectl config use-context ИМЯ_ИЗ_КОЛОНКИ_NAME
```

Если `**current-context is not set**` или список контекстов пуст — кластер ещё не создан или команда запуска завершилась с ошибкой; вернитесь к [разд. 5](#5-локальный-кластер-kubernetes) и шагу 1 этого раздела.

1. Проверьте доступ к API:

```bash
kubectl cluster-info
kubectl get nodes
```

Ожидается: **Kubernetes control plane** доступен; узлы в статусе **Ready**.

Если видите `**Unable to connect to the server`** — кластер не запущен или kubectl смотрит не в тот контекст (повторите шаг 2). Другие типичные случаи — [разд. 15](#15-типичные-проблемы-и-решения).

---

## 7. Мини-приложение на FastAPI

Создайте каталог `k8s-lab1/`, файл `main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="K8s Lab 1")


@app.get("/")
def root():
    return {"msg": "hello from k8s lab", "service": "lab1-api"}


@app.get("/health")
def health():
    return {"status": "ok"}
```

Файл `requirements.txt`:

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
```

Эндпоинт `**/health**` пригодится в следующих работах (пробы готовности); в рамках лабораторной №1 достаточно проверить его через браузер или `curl` после `port-forward`.

---

## 8. Сборка образа (Dockerfile)

Файл `Dockerfile` в каталоге `k8s-lab1/`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Сборка образа с тегом `lab1-api:1.0`:

```bash
cd k8s-lab1
docker build -t lab1-api:1.0 .
```

Проверка на хосте (необязательно):

```bash
docker run --rm -p 8000:8000 lab1-api:1.0
```

В другом терминале: `curl http://127.0.0.1:8000/health`.

---

## 9. Манифесты Deployment и Service

Подкаталог `k8s/`, файл `**deployment.yaml**`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lab1-api
  labels:
    app: lab1-api
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
        - name: api
          image: lab1-api:1.0
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
```

**Пояснения для отчёта:**

- `replicas: 2` — целевое число идентичных подов.  
- `imagePullPolicy: IfNotPresent` — для локального образа: не запрашивать его из интернета, если образ уже есть на ноде.  
- Метки в `selector.matchLabels` и `template.metadata.labels` **должны совпадать**.

Файл `**service.yaml`**:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: lab1-api
spec:
  type: ClusterIP
  selector:
    app: lab1-api
  ports:
    - port: 80
      targetPort: 8000
```

Трафик к сервису на порт **80** внутри кластера перенаправляется на порт **8000** контейнера.

---

## 10. Загрузка образа в кластер

Kubernetes на отдельной виртуальной машине (minikube) или в отдельных контейнерах (kind) **не использует** напрямую образы из Docker Desktop на хосте. Образ нужно **импортировать** в среду, где работает kubelet.

### Minikube

```bash
minikube start
minikube image load lab1-api:1.0
```

Проверка (опционально):

```bash
minikube ssh -- docker images
```

### kind

```bash
kind create cluster --name lab1
kind load docker-image lab1-api:1.0 --name lab1
```

### k3d

```bash
k3d cluster create lab1
k3d image import lab1-api:1.0 -c lab1
```

---

## 11. Развёртывание: kubectl apply

Из каталога, содержащего `k8s/`:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

Проверка:

```bash
kubectl get pods
kubectl get deploy
kubectl get svc
```

Ожидается: Deployment **READY 2/2**, поды **Running**. Статус **ImagePullBackOff** означает, что образ не найден на ноде — вернитесь к [разд. 10](#10-загрузка-образа-в-кластер).

---

## 12. Логи и диагностика

```bash
kubectl logs -l app=lab1-api --tail=50
kubectl describe pod -l app=lab1-api
```

В конце вывода `describe` раздел **Events** объясняет причины **Pending**, **CrashLoopBackOff** и т.д.

---

## 13. Доступ к приложению: port-forward

Сервис типа `ClusterIP` недоступен с хоста напрямую. Выполните (процесс оставьте запущенным):

```bash
kubectl port-forward service/lab1-api 8080:80
```

В другом терминале:

```bash
curl http://127.0.0.1:8080/
curl http://127.0.0.1:8080/health
```

---

## 14. Дополнительные эксперименты

1. **Масштабирование**

```bash
kubectl scale deployment lab1-api --replicas=3
kubectl get pods
```

1. **Самовосстановление**

```bash
kubectl get pods
kubectl delete pod ИМЯ_ПОДА
kubectl get pods -w
```

Убедитесь, что создаётся **новый** под — Deployment поддерживает заданное число реплик.

1. **Новая версия образа**

Измените код, соберите `lab1-api:1.1`, загрузите в кластер, в `deployment.yaml` укажите `image: lab1-api:1.1`, выполните `kubectl apply -f k8s/deployment.yaml`, проверьте:

```bash
kubectl rollout status deployment/lab1-api
```

---

## 15. Типичные проблемы и решения


| Симптом                             | Действия                                                                                                                           |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `kubectl` не найден                 | Переустановить клиент ([разд. 4](#4-утилита-kubectl-назначение-и-установка)), проверить **PATH**, открыть новый терминал.          |
| `minikube` не найден (Windows)      | Minikube может быть уже установлен через winget, но не в PATH сессии — см. [п. 5.4](#54-windows-команда-minikube-не-найдена-path). |
| `Unable to connect to the server`   | Запустить кластер (`minikube start` и т.д.); проверить `kubectl config current-context`.                                           |
| `ImagePullBackOff` / `ErrImagePull` | Образ не загружен в кластер ([разд. 10](#10-загрузка-образа-в-кластер)); проверить имя и тег в `image:`.                           |
| Под Running, но connection refused  | Несовпадение портов: `containerPort`, `uvicorn --port`, `targetPort` в Service.                                                    |
| Ошибка при `port-forward`           | Проверить имя сервиса: `kubectl get svc`; не занят ли порт 8080 на хосте.                                                          |


---

## 16. Критерии зачёта и содержание отчёта

### 16.1. Чеклист (обязательно)

- Установлен **kubectl**, команда `kubectl version --client` выполняется успешно.  
- Запущен локальный кластер, `kubectl get nodes` показывает Ready.  
- Собран образ `lab1-api` с тегом (например `1.0`).  
- Образ **импортирован** в кластер (minikube / kind / k3d).  
- Применены `deployment.yaml` и `service.yaml`, не менее **двух** подов в **Running**.  
- Через `port-forward` открываются маршруты `/` и `/health`.  
- Выполнены масштабирование и удаление одного пода с наблюдением пересоздания.  
- В отчёте — **5–10 предложений** своими словами: что такое Deployment и Service.

### 16.2. Рекомендуемое содержание отчёта

1. Титульный лист (по шаблону вуза).
2. Цель работы (можно по [разд. 1](#1-цели-работы)).
3. Скриншоты или текст вывода: `kubectl version --client`, `kubectl get nodes`, `kubectl get pods`, `kubectl get svc`.
4. Листинги или приложения: `main.py`, `Dockerfile`, `deployment.yaml`, `service.yaml`.
5. Краткие выводы (Deployment, Service, роль kubectl).

---

## 17. Вариант с Django

Если преподаватель разрешил Django вместо FastAPI:

- запуск через **gunicorn** или **uvicorn** (ASGI);  
- настройка `ALLOWED_HOSTS` для учебной среды;  
- согласованность портов: процесс в контейнере, `containerPort`, `targetPort` в Service.

Объём отладки обычно выше, чем у однофайлового FastAPI.

---

## 18. Направления дальнейшего изучения

- ресурс **Ingress** и доступ по имени хоста без `port-forward`;  
- **ConfigMap** и **Secret**;  
- **liveness** и **readiness** probes на `/health`;  
- **StatefulSet**, **PVC**, базы данных и очереди в кластере.

---

**Литература и ссылки**

1. Kubernetes Documentation. *Install Tools.* URL: `https://kubernetes.io/docs/tasks/tools/`
2. Kubernetes Documentation. *kubectl.* URL: `https://kubernetes.io/docs/reference/kubectl/`
3. Методические материалы курса: `lect_k8s.md`, `lect_k8s_lecturer.md`.

---

*Конец методического указания.*