docker push nesrv2026/lab1-api:tagname


To use the access token from your Docker CLI client:

1. Run

docker login -u nesrv2026

2. At the password prompt, enter the personal access token. Локально его можно хранить в `etc.secrets.local` (файл в `.gitignore`, переменная `DOCKER_PAT=`).


GitHub Secrets