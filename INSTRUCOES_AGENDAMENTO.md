# 🤖 Sistema de Processamento Automático - Gestta

## ✅ CONFIGURAÇÃO ATUALIZADA

O sistema agora está configurado para executar **automaticamente todos os dias às 8:30** e processar as tarefas da **data atual**.

## 🕐 Configuração do Agendamento

- **Horário**: 08:30 (todos os dias)
- **Data**: Sempre a data atual (hoje)
- **Frequência**: Diária (incluindo fins de semana)

## 🚀 Como Executar

### 1. Via Docker (Recomendado)
```bash
cd /home/roboestatistica/Documents/GitHub/DocumentosGestta
docker compose up --build -d
```

### 2. Via Scheduler Dedicado
```bash
python scheduler.py
```

### 3. Via Main.py (Execução Manual)
```bash
# Processar data atual
python main.py

# Processar data específica
python main.py --start-date 2025-09-22 --end-date 2025-09-22
```

## 📊 Logs e Monitoramento

- **Interface Web**: http://127.0.0.1:5010
- **Logs do Sistema**: `logs/gestta_system.log`
- **Logs de Execução**: `logs/execucao_YYYYMMDD_HHMMSS.txt`
- **Resumos JSON**: `logs/last_run_summary_YYYYMMDD_HHMMSS.json`

## 🎯 O que o Robô Faz Automaticamente

1. **08:30** - Inicia processamento
2. **Busca** tarefas com vencimento da data atual
3. **Filtra** apenas tarefas de cobrança de documentos
4. **Verifica** se há documentos anexados
5. **Baixa** documentos quando disponíveis
6. **Envia** alertas para clientes quando documentos estão faltando
7. **Finaliza** tarefas processadas
8. **Gera** relatórios e logs

## 🔧 Funcionalidades Principais

- ✅ 1494 empresas carregadas
- ✅ 257 usuários monitorados
- ✅ Processamento de data atual automático
- ✅ Download de documentos
- ✅ Envio de alertas
- ✅ Interface web de monitoramento
- ✅ Logs detalhados

## 📝 Exemplo de Uso Manual

Para processar uma data específica:
```bash
python main.py --start-date 2025-09-23 --end-date 2025-09-23
```

Para processar um intervalo:
```bash
python main.py --start-date 2025-09-20 --end-date 2025-09-22
```

## ⚙️ Arquivos de Configuração

- `gestta_config.json` - Credenciais e empresas selecionadas
- `task_phrases.json` - Frases para filtrar tarefas
- `docker-compose.yml` - Configuração do container

## 🆘 Solução de Problemas

Se o robô não executar:

1. **Verificar logs**: `docker logs gestta_container`
2. **Verificar credenciais** no `gestta_config.json`
3. **Verificar conectividade** com a API Gestta
4. **Recriar container**: `docker compose up --build -d`

## 📈 Status Atual

- ✅ **Sistema 100% funcional**
- ✅ **Agendamento configurado para 8:30**
- ✅ **Processamento de data atual**
- ✅ **1494 empresas + 257 usuários**