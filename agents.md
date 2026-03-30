laba_k8s_docker_desktop.md
нужно увеличить для 2-х часового занятия
придумать несколько интересных кейсов


# kubectl на Windows: версия 1.35.3

## Ситуация

- `kubectl version --client` показывает **v1.34.1** — чаще всего это **`kubectl` из Docker Desktop**:  
  `C:\Program Files\Docker\Docker\resources\bin\kubectl.exe`
- Нужная версия **v1.35.3** — в **`C:\kubectl\kubectl.exe`** (как в методичке `laba_k8s.md`, п. 4.4).

Docker Desktop при работе подмешивает свой каталог в **PATH** так, что он оказывается **раньше**, чем запись `C:\kubectl` в переменных среды пользователя. Поэтому одного «добавить `C:\kubectl` в PATH» в параметрах Windows может быть недостаточно.

## Что сделано

1. В **пользовательский PATH** по-прежнему должен быть **`C:\kubectl`** (параметры системы → переменные среды).
2. Создан профиль PowerShell, который при **каждом** запуске подставляет `C:\kubectl` **в начало** текущего `PATH` (перед путём Docker):

`C:\Users\user\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`

Содержимое:

```powershell
if (Test-Path 'C:\kubectl\kubectl.exe') {
    $env:Path = 'C:\kubectl;' + $env:Path
}
```

Закройте терминал и откройте снова (или выполните `& $PROFILE`), затем:

```text
kubectl version --client
```

Ожидается: **Client Version: v1.35.3**.

### Одна команда в текущем окне (без профиля)

```powershell
$env:Path = "C:\kubectl;" + $env:Path
kubectl version --client
```

### Вариант «навсегда» без профиля (нужны права администратора)

От **PowerShell от имени администратора** — добавить `C:\kubectl` в **начало системного (Machine) PATH**; системные каталоги идут в `PATH` раньше пользовательских, и Docker не перехватит приоритет через пользовательскую часть.

## Обновление самого Kubernetes (minikube)

Версия **клиента** kubectl и версия **кластера** — разные вещи. Кластер задаётся при `minikube start`, например:

```powershell
minikube start --kubernetes-version=v1.35.3
```

(если minikube поддерживает эту версию образа; иначе см. `minikube get-k8s-versions`).

## Minikube: VirtualBox и VT-X / `HOST_VIRT_UNAVAILABLE`

Если **`minikube start`** с **virtualbox** падает с *VT-X/AMD-v not enabled*:

1. Запустите **Docker Desktop**.
2. Выполните:

```powershell
minikube delete
minikube start --driver=docker
```

Подробнее — `laba_k8s.md`, п. **5.5**.
