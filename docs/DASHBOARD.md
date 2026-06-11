# 📊 Dashboard Globoplay — Qualidade de Software

Documentação completa do dashboard Grafana que monitora a qualidade percebida do app Globoplay a partir das reviews postadas pelo Appbot no canal Slack `#globoplay-ratings`.

---

## 🏗️ Visão Geral

O dashboard é composto por **15 painéis** organizados em **7 linhas**, cobrindo desde KPIs de alto nível até detalhamentos por plataforma, versão do app e dispositivo.

| Linha | Painéis | Objetivo |
|-------|---------|----------|
| 1 | KPIs (6 stats) | Visão rápida da saúde do app |
| 2 | Tendência Diária | Evolução temporal |
| 3 | Top Problemas + NPS por Plataforma | Diagnóstico de problemas |
| 4 | Quality Score + Dispositivos | Análise por versão e hardware |
| 5 | Sentimento Geral + Sentimento por Plataforma | Análise de sentimento |
| 6 | Tendência de Sentimento | Evolução do sentimento no tempo |
| 7 | Problemas por Plataforma + Sugestões | Detalhamento e feedback |

---

## 📋 Detalhamento dos Painéis

### Linha 1 — KPIs de Saúde

#### ⭐ Nota Média Geral
- **Tipo:** Stat
- **Fonte:** `tendencia_diaria.csv`
- **Métrica:** Média aritmética de todas as notas (1-5 estrelas) do período
- **Thresholds:** 🔴 < 2.5 | 🟡 2.5–3.5 | 🟢 > 3.5
- **Para que serve:** Indicador principal de satisfação. Se cair abaixo de 2.5, há um problema grave.

#### 📈 NPS Estimado
- **Tipo:** Stat
- **Fonte:** `nps_global.csv`
- **Métrica:** Net Promoter Score estimado = `(% promotores - % detratores) × 100`
  - **Promotores:** notas 4-5★
  - **Neutros:** nota 3★
  - **Detratores:** notas 1-2★
- **Thresholds:** 🔴 < 0 | 🟡 0–30 | 🟢 > 30
- **Para que serve:** Mede a propensão dos usuários a recomendar o app. NPS negativo indica mais detratores que promotores.

#### 📝 Total de Reviews
- **Tipo:** Stat
- **Fonte:** `tendencia_diaria.csv`
- **Métrica:** Soma total de reviews analisadas no período
- **Para que serve:** Volume de feedback. Poucas reviews podem indicar baixo engajamento; muitas após um release podem sinalizar problemas.

#### 🔴 Reviews com Problema
- **Tipo:** Stat
- **Fonte:** `tendencia_diaria.csv`
- **Métrica:** Soma de reviews onde pelo menos 1 categoria de problema foi detectada
- **Para que serve:** Quantifica reviews que relatam bugs, crashes, lentidão etc. Comparar com o total dá a proporção de reclamações.

#### 💡 Sugestões
- **Tipo:** Stat
- **Fonte:** `tendencia_diaria.csv`
- **Métrica:** Total de reviews que contêm sugestões de melhoria
- **Para que serve:** Feedback construtivo dos usuários. Reviews com palavras como "deveria", "podia ter", "falta", "seria bom" são classificadas como sugestões.

#### % Negativo (média)
- **Tipo:** Stat
- **Fonte:** `tendencia_diaria.csv`
- **Métrica:** Média diária do percentual de reviews classificadas como "Negative" pelo Appbot
- **Thresholds:** 🟢 < 40% | 🟡 40–70% | 🔴 > 70%
- **Para que serve:** Indica o nível geral de insatisfação. Se a média de negativos ultrapassa 70%, a percepção de qualidade está crítica.

---

### Linha 2 — Tendência Temporal

#### 📈 Tendência Diária — Nota Média vs Problemas
- **Tipo:** Time Series
- **Fonte:** `tendencia_diaria.csv`
- **Métricas exibidas:**
  - 🟢 **Nota Média** (eixo esquerdo) — média das notas por dia
  - 🔴 **Problemas Reportados** (eixo direito) — quantidade de reviews com problema por dia
  - 🔵 **Reviews** (barras, eixo direito) — volume diário de reviews
- **Para que serve:** Correlacionar nota × problemas no tempo. Permite identificar:
  - 📉 Quedas de nota após um release problemático
  - 📈 Melhoria após correções
  - 🔺 Picos de problemas (possíveis incidentes)

---

### Linha 3 — Diagnóstico de Problemas

#### 🔴 Top Categorias de Problema
- **Tipo:** Pie Chart (donut)
- **Fonte:** `top_problemas.csv`
- **Métrica:** Contagem de ocorrências por categoria de problema
- **Categorias detectadas automaticamente:**
  - Crash/Travamento
  - Playback/Reprodução
  - Cast/Espelhamento
  - Assinatura/Pagamento
  - Performance/Lentidão
  - Conectividade/Rede
  - Login/Autenticação
  - Interface/UX
  - Áudio
  - Conteúdo
- **Para que serve:** Priorizar bugs. Se "Crash/Travamento" lidera com 15%, é o foco nº 1 do time de QA.

#### 📱 NPS por Plataforma
- **Tipo:** Bar Chart (horizontal)
- **Fonte:** `nps_por_plataforma.csv`
- **Métricas por plataforma:** NPS, promotores, neutros, detratores, nota média, total de reviews
- **Plataformas:** Android, iOS, Smart TV, Chromecast, Apple TV, Fire TV, Web
- **Thresholds:** 🔴 NPS < 0 | 🟡 0–30 | 🟢 > 30
- **Para que serve:** Identificar qual plataforma está com pior percepção. Se Android tem NPS -80 e iOS tem NPS -30, o Android precisa de mais atenção.

---

### Linha 4 — Versão do App e Dispositivos

#### 🏗️ Quality Score por Versão do App
- **Tipo:** Tabela
- **Fonte:** `quality_score_por_versao.csv`
- **Fórmula:** `Quality Score = nota_média × 20 − (% reviews com problema) − (% detratores × 0.5)`
- **Colunas:** Versão, Total Reviews, Nota Média, % Problemas, % Detratores, Quality Score
- **Para que serve:** Comparar a qualidade entre releases. Se a v3.535.0 tem score 0.3 e a v4.227.0 tem score -61.8, a versão iOS está com qualidade muito inferior à Android.

#### 📱 Dispositivos Mais Problemáticos
- **Tipo:** Tabela
- **Fonte:** `dispositivos_problematicos.csv`
- **Colunas:** Dispositivo, Reviews com Problema, Nota Média
- **Para que serve:** Identificar hardware específico com problemas. Ex: se "Galaxy A54" lidera com 11 problemas, pode ser incompatibilidade de hardware, fragmentação Android, ou bug específico desse modelo.

---

### Linha 5 — Análise de Sentimento

#### 🎭 Distribuição de Sentimento
- **Tipo:** Pie Chart (donut)
- **Fonte:** `sentimento_geral.csv`
- **Métrica:** Proporção de reviews Positive, Negative e Neutral
- **Cores:** 🟢 Positivo | 🟡 Neutro | 🔴 Negativo
- **Para que serve:** Visão macro do humor dos usuários. Ideal: maioria verde. Se >60% é vermelho, a percepção está crítica.

#### 📱 Sentimento por Plataforma
- **Tipo:** Tabela
- **Fonte:** `sentimento_por_plataforma.csv`
- **Colunas:** Plataforma, Sentimento, Total
- **Para que serve:** Cruzar sentimento × plataforma. Responde: "Qual plataforma concentra mais insatisfação?" Se Android tem 722 reviews negativas vs iOS com apenas 100, o foco deve ser Android.

---

### Linha 6 — Evolução do Sentimento

#### 📈 Tendência Diária de Sentimento
- **Tipo:** Time Series (área empilhada)
- **Fonte:** `sentimento_diario.csv`
- **Métricas:** Contagem diária de reviews Positivas, Neutras e Negativas (empilhadas)
- **Cores:** 🟢 Positivo | 🟡 Neutro | 🔴 Negativo
- **Para que serve:** Detectar regressões no sentimento. Se após um deploy a área vermelha cresce, houve impacto negativo. Permite medir se hotfixes melhoraram a percepção.

---

### Linha 7 — Detalhamento

#### 🗂️ Problemas por Plataforma
- **Tipo:** Tabela
- **Fonte:** `problemas_por_plataforma.csv`
- **Colunas:** Categoria do Problema, Plataforma, Ocorrências
- **Para que serve:** Cruzar tipo de problema × plataforma. Ex: se "Playback/Reprodução" ocorre 85× no Android e 5× no iOS, o problema de vídeo é específico do Android.

#### 💡 Sugestões de Melhoria dos Usuários
- **Tipo:** Tabela
- **Fonte:** `sugestoes_usuarios.csv`
- **Colunas:** Data, Plataforma, Nota, Texto da Review
- **Para que serve:** Listar reviews que contêm feedback construtivo. Útil para product discovery e priorização de backlog.

---

## 📁 Arquivos CSV Gerados

| Arquivo | Descrição | Painel(éis) |
|---------|-----------|-------------|
| `tendencia_diaria.csv` | Métricas agregadas por dia | Nota Média, NPS, Total Reviews, Problemas, Sugestões, % Negativo, Tendência Diária |
| `nps_global.csv` | NPS geral do período | NPS Estimado |
| `nps_por_plataforma.csv` | NPS por plataforma | NPS por Plataforma |
| `nps_por_versao.csv` | NPS por versão do app | — (dados disponíveis) |
| `quality_score_por_versao.csv` | Score de qualidade por versão | Quality Score por Versão |
| `top_problemas.csv` | Ranking de categorias de problema | Top Categorias de Problema |
| `problemas_por_plataforma.csv` | Problemas × plataforma | Problemas por Plataforma |
| `dispositivos_problematicos.csv` | Top 20 devices com mais problemas | Dispositivos Mais Problemáticos |
| `sugestoes_usuarios.csv` | Reviews com sugestões | Sugestões de Melhoria |
| `sentimento_geral.csv` | Distribuição Positive/Negative/Neutral | Distribuição de Sentimento |
| `sentimento_por_plataforma.csv` | Sentimento × plataforma | Sentimento por Plataforma |
| `sentimento_diario.csv` | Sentimento empilhado por dia | Tendência Diária de Sentimento |
| `reviews_detalhadas.csv` | Todas as reviews com todos os campos | — (análise offline) |

---

## 🔄 Como Atualizar os Dados

```bash
# Carregar token e executar
export $(cat .env | xargs) && python3 slack_ratings_metrics.py --days 30 --outdir out
```

O Grafana lê os CSVs via HTTP automaticamente — **não precisa reiniciar** o Grafana após atualizar os dados. Basta dar **Refresh** no dashboard.

Para agendamento automático diário, veja a seção de cron/launchd no `README.md`.

---

## 🧮 Fórmulas e Classificações

### NPS (Net Promoter Score)
$$NPS = \frac{\text{Promotores} - \text{Detratores}}{\text{Total com nota}} \times 100$$

- **Promotores:** 4-5★
- **Neutros:** 3★
- **Detratores:** 1-2★

### Quality Score
$$QS = \text{nota\_média} \times 20 - \text{pct\_com\_problema} - \text{pct\_detratores} \times 0.5$$

### Categorização de Problemas
Cada review é analisada por **10 categorias** usando regex. Uma review pode pertencer a múltiplas categorias (ex: "trava e o áudio some" = Crash + Áudio).

### Sentimento
Classificação do Appbot embarcada na mensagem do Slack: `Positive`, `Negative`, `Neutral` ou `Mixed`.

### Detecção de Sugestões
Reviews que contêm expressões como: "deveria", "podia ter", "falta", "seria bom", "sugiro", "gostaria que", etc.

---

## 🎯 Casos de Uso para o Time de QA

| Pergunta | Onde responder |
|----------|---------------|
| "O app está bom?" | Nota Média + NPS Estimado |
| "Qual o problema mais grave?" | Top Categorias de Problema |
| "Qual plataforma está pior?" | NPS por Plataforma + Sentimento por Plataforma |
| "O último release melhorou?" | Quality Score por Versão + Tendência Diária |
| "Quais dispositivos dão problema?" | Dispositivos Mais Problemáticos |
| "Os usuários estão sugerindo algo?" | Sugestões de Melhoria |
| "Tivemos uma regressão?" | Tendência Diária de Sentimento |
| "O sentimento está melhorando?" | Distribuição de Sentimento + Tendência |

---

## 🔧 Stack Técnica

- **Extração:** Python 3.13 + `slack-sdk` + `pandas`
- **Armazenamento:** CSV (sem banco de dados)
- **Visualização:** Grafana OSS + plugin Infinity (CSV via HTTP)
- **Servidor CSV:** Nginx (container Docker servindo `out/`)
- **Infraestrutura:** Docker Compose (Grafana + Nginx)

---

*Última atualização: Maio 2026*
