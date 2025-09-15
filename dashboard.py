# dashboard.py
import os
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.gridspec import GridSpec
from logger_config import logger

def gerar_dashboard_estatisticas(estatisticas):
    """
    Gera um dashboard visual limpo e minimalista com as estatísticas do processamento.
    Usa um design retangular moderno sem círculos.
    """
    # Criar pasta para logs e estatísticas se não existir
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)
    
    # Obter valores das estatísticas
    tarefas_processadas = estatisticas.get("tarefas_processadas", 0)
    documentos_baixados = estatisticas.get("documentos_baixados", 0)
    alertas_enviados = estatisticas.get("alertas_enviados", 0)
    tempo_total_sec = estatisticas.get("tempo_total", 0)
    data_hora = estatisticas.get("data_hora", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    
    # Calcular métricas derivadas
    tempo_total_min = tempo_total_sec / 60
    tempo_por_tarefa = tempo_total_sec / max(tarefas_processadas, 1)  # Evita divisão por zero
    
    # Definir cores modernas para o dashboard
    cores = {
        'azul_principal': '#4161E8',       # Azul vibrante para títulos
        'laranja_accent': '#FF7D4D',       # Laranja para números importantes
        'texto_escuro': '#333333',         # Cor principal de texto
        'texto_secundario': '#666666',     # Cor secundária de texto
        'background': '#FFFFFF',           # Branco para fundo
        'cinza_claro': '#F8F9FA',          # Cinza claro para painéis
        'borda': '#E1E5EB'                 # Cor para bordas
    }
    
    # Configurar o estilo do matplotlib
    plt.style.use('default')
    
    # Criar figura com fundo branco
    fig = plt.figure(figsize=(10, 8), facecolor=cores['background'])
    
    # Configurar layout com GridSpec para mais controle
    gs = GridSpec(6, 2, figure=fig)
    
    # Adicionar título principal centralizado no topo
    fig.text(0.5, 0.94, 'DASHBOARD GESTTA', 
             ha='center', va='top', fontsize=28, fontweight='bold',
             color=cores['azul_principal'])
    
    # Adicionar subtítulo
    fig.text(0.5, 0.89, 'Sistema de Cobrança de Documentos', 
             ha='center', va='top', fontsize=16, 
             color=cores['texto_secundario'])
    
    # Criar funções para adicionar painéis de estatísticas
    def add_stat_panel(gridspec, title, value, color=cores['laranja_accent']):
        ax = fig.add_subplot(gridspec)
        ax.set_facecolor(cores['cinza_claro'])
        ax.axis('off')
        
        # Adicionar bordas sutis ao painel
        ax.spines['bottom'].set_color(cores['borda'])
        ax.spines['top'].set_color(cores['borda'])
        ax.spines['left'].set_color(cores['borda'])
        ax.spines['right'].set_color(cores['borda'])
        ax.patch.set_edgecolor(cores['borda'])
        ax.patch.set_linewidth(1)
        
        # Título do painel
        ax.text(0.5, 0.85, title, 
                ha='center', va='center', fontsize=14,
                color=cores['texto_escuro'])
        
        # Valor principal
        ax.text(0.5, 0.5, str(value), 
                ha='center', va='center', fontsize=32, fontweight='bold',
                color=color)
    
    # Painel para Tarefas Processadas
    add_stat_panel(gs[0:2, 0], "Tarefas Processadas", tarefas_processadas)
    
    # Painel para Documentos Baixados
    add_stat_panel(gs[0:2, 1], "Documentos Baixados", documentos_baixados)
    
    # Painéis de estatísticas adicionais
    add_stat_panel(gs[2:3, 0], "Alertas Enviados", alertas_enviados)
    
    # Painel para informações de tempo
    ax_tempo = fig.add_subplot(gs[2:4, 1])
    ax_tempo.set_facecolor(cores['cinza_claro'])
    ax_tempo.axis('off')
    ax_tempo.patch.set_edgecolor(cores['borda'])
    ax_tempo.patch.set_linewidth(1)
    
    # Título do painel de tempo
    ax_tempo.text(0.5, 0.85, "Informações de Tempo", 
                 ha='center', va='center', fontsize=14,
                 color=cores['texto_escuro'])
    
    # Valores de tempo
    ax_tempo.text(0.5, 0.6, f"Tempo Total: {tempo_total_min:.2f} min", 
                 ha='center', va='center', fontsize=14,
                 color=cores['texto_escuro'])
    
    ax_tempo.text(0.5, 0.35, f"Tempo Médio: {tempo_por_tarefa:.2f} seg/tarefa", 
                 ha='center', va='center', fontsize=14,
                 color=cores['texto_escuro'])
    
    # Atualizar esta parte para incluir a nova estatística de empresas processadas
    # e distinguir do número total de empresas carregadas
    items = [
        f"Tempo Total: {tempo_total_min:.2f} min",
        f"Empresas Carregadas: {estatisticas.get('empresas_carregadas', 0)}",
        f"Empresas Processadas: {estatisticas.get('empresas_processadas', 0)}",
        f"Usuários: {estatisticas.get('usuarios_processados', 0)}",
        f"Alertas Enviados: {estatisticas.get('alertas_enviados', 0)}",
        f"Tarefas Processadas: {estatisticas.get('tarefas_processadas', 0)}",
        f"Documentos Baixados: {estatisticas.get('documentos_baixados', 0)}"
    ]
    
    # Rodapé com data de geração
    fig.text(0.5, 0.05, f"Gerado em: {data_hora}", 
             ha='center', va='center', fontsize=10,
             color=cores['texto_secundario'])
    
    # Adicionar logo ou informações da empresa (opcional)
    fig.text(0.95, 0.05, "Go Further", 
             ha='right', va='center', fontsize=10, fontstyle='italic',
             color=cores['texto_secundario'])
    
    # Ajustar layout para melhor espaçamento
    plt.tight_layout(rect=[0.05, 0.1, 0.95, 0.85])
    
    # Salvar a imagem com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    imagem_path = os.path.join(logs_dir, f"dashboard_{timestamp}.png")
    plt.savefig(imagem_path, bbox_inches='tight', dpi=150, facecolor=cores['background'])
    plt.close()
    
    logger.info(f"Dashboard gerado e salvo em: {imagem_path}")
    return imagem_path