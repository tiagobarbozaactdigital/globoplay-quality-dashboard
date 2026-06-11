# Slack Métricas — #globoplay-ratings

Extrai reviews do canal Slack `#globoplay-ratings`, gera **métricas estratégicas de qualidade de software** e alimenta um **dashboard Grafana local** — tudo gratuito, sem banco de dados.

## Arquitetura

```
Slack API (#globoplay-ratings)
  → Python (cron diário)
    → CSVs (out/)
      → Grafana OSS (local, plugin CSV)
```

## Métricas Estratégicas

| Métrica | Arquivo CSV | Painel no Grafana |
|---|---|---|
| NPS estimado (global) | `nps_global.csv` | Stat |
| NPS por plataforma | `nps_por_plataforma.csv` | Bar chart |
| NPS por versão do app | `nps_por_versao.csv` | Table |
| Quality Score por versão | `quality_score_por_versao.csv` | Table com cores |
| Top categorias de problema | `top_problemas.csv` | Pie chart (donut) |
| Problemas × plataforma | `problemas_por_plataforma.csv` | Table heatmap |
| Dispositivos problemáticos | `dispositivos_problematicos.csv` | Table |
| Sugestões de melhoria | `sugestoes_usuarios.csv` | Table |
| Tendência diária | `tendencia_diaria.csv` | Time series |
| Sentimento geral | `sentimento_geral.csv` | Pie chart (donut) |
| Sentimento por plataforma | `sentimento_por_plataforma.csv` | Table |
| Tendência de sentimento | `sentimento_diario.csv` | Time series (área empilhada) |
| Reviews individuais | `reviews_detalhadas.csv` | — |

> 📖 Para documentação completa de cada painel, métricas, fórmulas e casos de uso, veja [`docs/DASHBOARD.md`](docs/DASHBOARD.md).

## Pré-requisitos

- Python 3.13+
- Docker (para Grafana)
- Token de bot Slack com scope `channels:history`

## Setup rápido

```bash
cd slack-metricas-globoplay
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configurar o token

```bash
export SLACK_TOKEN="xoxb-SEU-TOKEN-AQUI"
```

> **Nunca** commite o token. Use variável de ambiente ou um arquivo `.env` (já no `.gitignore`).

## Executar o script

```bash
# Últimos 30 dias (padrão)
python3 slack_ratings_metrics.py --outdir out

# Últimos 3 dias
python3 slack_ratings_metrics.py --days 3 --outdir out

# Canal diferente
python3 slack_ratings_metrics.py --channel C0XXXXXXX --days 14 --outdir out
```

## 📊 Subir o Grafana (dashboard automático)

```bash
# 1. Gere os CSVs primeiro
export SLACK_TOKEN="xoxb-..."
python3 slack_ratings_metrics.py --days 30 --outdir out

# 2. Suba o Grafana com Docker
docker compose up -d

# 3. Acesse
open http://localhost:3000
# Login: admin / admin
```

O dashboard **"📊 Globoplay — Qualidade de Software"** já estará provisionado automaticamente na pasta "Globoplay Quality".

### O que o dashboard mostra

- **Linha 1** — KPIs: Nota Média, NPS, Total Reviews, Problemas, Sugestões, % Negativo
- **Linha 2** — Gráfico de tendência diária (nota média vs problemas)
- **Linha 3** — Top Problemas (donut) + NPS por Plataforma (bar)
- **Linha 4** — Quality Score por Versão (table) + Dispositivos Problemáticos (table)
- **Linha 5** — Sentimento Geral (donut) + Sentimento por Plataforma (table)
- **Linha 6** — Tendência Diária de Sentimento (área empilhada)
- **Linha 7** — Problemas × Plataforma (table) + Sugestões dos Usuários (table)

## Agendamento diário no macOS

### Opção 1 — cron

```bash
crontab -e
```

Adicione (exemplo: todo dia às 06:00):

```cron
SLACK_TOKEN=xoxb-SEU-TOKEN
0 6 * * * cd /Users/actdigital/slack-metricas-globoplay && /Users/actdigital/slack-metricas-globoplay/venv/bin/python slack_ratings_metrics.py --days 1 --outdir out >> out/run.log 2>&1
```

### Opção 2 — launchd (recomendado no macOS)

Crie `~/Library/LaunchAgents/com.globoplay.slack-metrics.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.globoplay.slack-metrics</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/actdigital/slack-metricas-globoplay/venv/bin/python</string>
        <string>/Users/actdigital/slack-metricas-globoplay/slack_ratings_metrics.py</string>
        <string>--days</string>
        <string>1</string>
        <string>--outdir</string>
        <string>/Users/actdigital/slack-metricas-globoplay/out</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>SLACK_TOKEN</key>
        <string>xoxb-SEU-TOKEN-AQUI</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>/Users/actdigital/slack-metricas-globoplay</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/actdigital/slack-metricas-globoplay/out/run.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/actdigital/slack-metricas-globoplay/out/run.log</string>
</dict>
</plist>
```

Carregar/descarregar:

```bash
launchctl load   ~/Library/LaunchAgents/com.globoplay.slack-metrics.plist
launchctl unload ~/Library/LaunchAgents/com.globoplay.slack-metrics.plist
```

## Estrutura do projeto

```
slack-metricas-globoplay/
├── slack_ratings_metrics.py      # Script principal
├── requirements.txt              # Dependências Python
├── docker-compose.yml            # Grafana local
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yml   # Datasources CSV
│   │   └── dashboards/
│   │       └── dashboards.yml    # Provider de dashboards
│   └── dashboards/
│       └── globoplay-quality.json  # Dashboard provisionado
├── out/                          # CSVs gerados (gitignored)
├── .env                          # SLACK_TOKEN (gitignored)
└── README.md
```

## .gitignore

```
.env
out/
venv/
.venv/
__pycache__/
*.pyc
```
