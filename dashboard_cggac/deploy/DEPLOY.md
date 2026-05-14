# Passos de instalação e publicação — Dashboard CGGAC/SEGES

## 1. Instalar dependências

```bash
cd /home/daianasales/vscode/datapipeline
# Use o venv existente ou crie um novo:
python3 -m venv .venv
source .venv/bin/activate
pip install -r dashboard_cggac/requirements.txt
```

## 2. Configurar variáveis de ambiente

```bash
cp dashboard_cggac/.env.example dashboard_cggac/.env
# Edite .env com SECRET_KEY, ALLOWED_HOSTS e CGGAC_XLSX_PATH reais
```

Gere uma SECRET_KEY segura:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 3. Banco de dados e arquivos estáticos

```bash
cd dashboard_cggac
python manage.py migrate
python manage.py collectstatic --noinput
```

## 4. Carga inicial dos dados

```bash
python manage.py carregar_xlsx
# Para recarregar do zero:
# python manage.py carregar_xlsx --limpar
```

## 5. Criar superusuário (para /admin/)

```bash
python manage.py createsuperuser
```

## 6. Teste local

```bash
python manage.py runserver 0.0.0.0:8000
# Acesse: http://localhost:8000 (Executivo) e http://localhost:8000/operacional/
```

## 7. Deploy em produção (Linux)

### Criar diretório de logs
```bash
sudo mkdir -p /var/log/dashboard_cggac
sudo chown daianasales:www-data /var/log/dashboard_cggac
```

### Instalar o serviço Gunicorn
```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/dashboard_cggac.service
sudo systemctl daemon-reload
sudo systemctl enable dashboard_cggac
sudo systemctl start dashboard_cggac
sudo systemctl status dashboard_cggac
```

### Configurar Nginx
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/dashboard_cggac
sudo ln -s /etc/nginx/sites-available/dashboard_cggac /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Configurar cron de atualização diária
```bash
chmod +x deploy/cron_atualizar.sh
crontab -e
# Adicione a linha abaixo (todo dia útil às 06:00):
# 0 6 * * 1-5 /home/daianasales/vscode/datapipeline/dashboard_cggac/deploy/cron_atualizar.sh >> /var/log/dashboard_cggac/cron.log 2>&1
```

## URLs

| Painel | URL |
|--------|-----|
| Visão Executiva | `http://seu.dominio.gov.br/` |
| Visão Operacional | `http://seu.dominio.gov.br/operacional/` |
| Django Admin | `http://seu.dominio.gov.br/admin/` |

## Atualização do XLSX

Basta substituir o arquivo no caminho `CGGAC_XLSX_PATH` configurado no `.env`.
O cron diário executará `carregar_xlsx` automaticamente às 06:00 em dias úteis.
Para atualização manual imediata:

```bash
cd /home/daianasales/vscode/datapipeline/dashboard_cggac
source /home/daianasales/vscode/datapipeline/.venv/bin/activate
python manage.py carregar_xlsx
```
