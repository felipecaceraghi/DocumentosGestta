# gui.py

import os
import json
import time
import requests
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox,
    QScrollArea, QMessageBox, QFileDialog, QGroupBox
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette, QFontDatabase, QPixmap

# Ajuste estes imports de acordo com sua estrutura
from config import COLORS, CONFIG_FILE, DOWNLOAD_BASE_DIR
from logger_config import logger
from api import get_token  # se você usa a função get_token do seu arquivo api.py
from api import get_all_companies, get_all_users  # idem
# Se não tiver esses módulos, você pode incorporar as funções diretamente aqui.

def set_app_style(app):
    """
    Aplica estilo retrô na aplicação
    """
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["dark_purple"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["light_cream"]))
    palette.setColor(QPalette.Base, QColor(COLORS["dark_purple"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["purple"]))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS["yellow"]))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS["black"]))
    palette.setColor(QPalette.Text, QColor(COLORS["light_cream"]))
    palette.setColor(QPalette.Button, QColor(COLORS["purple"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["light_cream"]))
    palette.setColor(QPalette.BrightText, QColor(COLORS["red"]))
    palette.setColor(QPalette.Link, QColor(COLORS["orange"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["teal"]))
    palette.setColor(QPalette.HighlightedText, QColor(COLORS["white"]))

    app.setPalette(palette)

    # Definir fonte padrão maior
    font = QFont("Arial", 12)
    app.setFont(font)

    # Aplicar estilo para os componentes
    qss = f"""
    QWidget {{
        background-color: {COLORS["dark_purple"]};
        color: {COLORS["light_cream"]};
        font-size: 14px;
    }}
    
    QTabWidget::pane {{
        border: 2px solid {COLORS["teal"]};
        border-radius: 10px;
        background-color: {COLORS["dark_purple"]};
    }}
    
    QTabBar::tab {{
        background-color: {COLORS["purple"]};
        color: {COLORS["light_cream"]};
        border: 2px solid {COLORS["teal"]};
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        min-width: 120px;
        min-height: 40px;
        padding: 8px;
        font-size: 16px;
        font-weight: bold;
    }}
    
    QTabBar::tab:selected {{
        background-color: {COLORS["teal"]};
        color: {COLORS["white"]};
    }}
    
    QPushButton {{
        background-color: {COLORS["red"]};
        color: {COLORS["white"]};
        border: none;
        border-radius: 20px;
        padding: 15px;
        font-size: 16px;
        font-weight: bold;
        min-height: 50px;
    }}
    
    QPushButton:hover {{
        background-color: {COLORS["orange"]};
    }}
    
    QPushButton:pressed {{
        background-color: {COLORS["yellow"]};
        color: {COLORS["black"]};
    }}
    
    QLineEdit {{
        background-color: {COLORS["light_cream"]};
        color: {COLORS["black"]};
        border: 2px solid {COLORS["teal"]};
        border-radius: 10px;
        padding: 10px;
        font-size: 16px;
        min-height: 40px;
    }}
    
    QCheckBox {{
        font-size: 16px;
        spacing: 10px;
    }}
    
    QCheckBox::indicator {{
        width: 24px;
        height: 24px;
    }}
    
    QGroupBox {{
        border: 2px solid {COLORS["teal"]};
        border-radius: 10px;
        margin-top: 20px;
        font-size: 18px;
        font-weight: bold;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top center;
        padding: 0 10px;
        color: {COLORS["yellow"]};
    }}
    
    QLabel {{
        font-size: 16px;
    }}
    
    QScrollArea {{
        border: 2px solid {COLORS["teal"]};
        border-radius: 10px;
    }}
    """
    app.setStyleSheet(qss)


class GesttaConfigurador(QMainWindow):
    """
    Classe principal da interface de configuração do Gestta.
    Permite inserir credenciais, selecionar empresas e usuários,
    definir diretório de download e modo debug, e salvar em um JSON.
    """
    def __init__(self):
        super().__init__()

        # Configuração da janela principal
        self.setWindowTitle("Configurador Gestta - Estilo Retrô")
        self.setGeometry(100, 100, 1000, 800)

        # Variáveis internas
        self.token = None
        self.all_companies = []
        self.all_users = []
        self.selected_companies = []
        self.selected_users = []
        self.company_checkboxes = {}
        self.user_checkboxes = {}

        # Valores padrão
        self.email = ""
        self.password = ""
        self.debug_mode = True
        self.download_dir = DOWNLOAD_BASE_DIR

        # Configurar interface
        self.setup_ui()

        # Carregar configuração existente
        self.load_config()

    def setup_ui(self):
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout principal
        main_layout = QVBoxLayout(central_widget)

        # Título em estilo retrô
        title_label = QLabel("GESTTA CONFIGURADOR")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont("Arial", 26, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {COLORS['yellow']}; margin-bottom: 20px;")
        main_layout.addWidget(title_label)

        # Subtítulo
        subtitle_label = QLabel("Sistema de Cobrança de Documentos")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_font = QFont("Arial", 18)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet(f"color: {COLORS['orange']}; margin-bottom: 30px;")
        main_layout.addWidget(subtitle_label)

        # Criar tabs
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Adicionar abas
        self.setup_login_tab()
        self.setup_companies_tab()
        self.setup_users_tab()
        self.setup_settings_tab()

        # Botão de salvar na parte inferior
        button_layout = QHBoxLayout()
        save_button = QPushButton("SALVAR CONFIGURAÇÃO")
        save_button.setFixedHeight(60)
        save_button.setFixedWidth(350)
        save_button.setFont(QFont("Arial", 16, QFont.Bold))
        save_button.clicked.connect(self.save_config)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Adicionar label de rodapé
        footer_label = QLabel("© 2025 Go Further - Sempre à Frente")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setStyleSheet(f"color: {COLORS['teal']}; margin-top: 10px;")
        main_layout.addWidget(footer_label)

    def setup_login_tab(self):
        login_tab = QWidget()
        login_layout = QVBoxLayout(login_tab)

        # Grupo de login
        login_group = QGroupBox("CREDENCIAIS GESTTA")
        login_group.setFont(QFont("Arial", 16, QFont.Bold))
        login_group_layout = QVBoxLayout(login_group)

        # Campo de email
        email_layout = QHBoxLayout()
        email_label = QLabel("Email:")
        email_label.setFont(QFont("Arial", 16))
        self.email_input = QLineEdit(self.email)
        self.email_input.setFont(QFont("Arial", 16))
        self.email_input.setMinimumHeight(50)
        email_layout.addWidget(email_label)
        email_layout.addWidget(self.email_input)
        login_group_layout.addLayout(email_layout)

        # Campo de senha
        password_layout = QHBoxLayout()
        password_label = QLabel("Senha:")
        password_label.setFont(QFont("Arial", 16))
        self.password_input = QLineEdit(self.password)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFont(QFont("Arial", 16))
        self.password_input.setMinimumHeight(50)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        login_group_layout.addLayout(password_layout)

        # Botão de login
        login_button = QPushButton("CONECTAR AO GESTTA")
        login_button.setFont(QFont("Arial", 16, QFont.Bold))
        login_button.setMinimumHeight(60)
        login_button.clicked.connect(self.login)
        login_group_layout.addWidget(login_button)

        login_layout.addWidget(login_group)
        login_layout.addStretch()

        # Imagem decorativa (opcional)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        # Se tiver uma imagem, defina:
        # image_label.setPixmap(QPixmap("caminho/para/imagem.png"))
        login_layout.addWidget(image_label)

        self.tab_widget.addTab(login_tab, "LOGIN")

    def setup_companies_tab(self):
        companies_tab = QWidget()
        companies_layout = QVBoxLayout(companies_tab)

        # Título da aba
        title_label = QLabel("SELECIONE AS EMPRESAS")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {COLORS['yellow']}; margin-bottom: 20px;")
        companies_layout.addWidget(title_label)

        # Botões de controle
        controls_layout = QHBoxLayout()
        select_all_button = QPushButton("SELECIONAR TODAS")
        select_all_button.setFont(QFont("Arial", 14, QFont.Bold))
        select_all_button.clicked.connect(self.select_all_companies)

        clear_all_button = QPushButton("LIMPAR SELEÇÃO")
        clear_all_button.setFont(QFont("Arial", 14, QFont.Bold))
        clear_all_button.clicked.connect(self.clear_all_companies)

        controls_layout.addWidget(select_all_button)
        controls_layout.addWidget(clear_all_button)
        companies_layout.addLayout(controls_layout)

        # Área de scroll para as empresas
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.companies_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        companies_layout.addWidget(scroll_area)

        self.tab_widget.addTab(companies_tab, "EMPRESAS")

    def setup_users_tab(self):
        users_tab = QWidget()
        users_layout = QVBoxLayout(users_tab)

        # Título da aba
        title_label = QLabel("SELECIONE OS USUÁRIOS")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {COLORS['yellow']}; margin-bottom: 20px;")
        users_layout.addWidget(title_label)

        # Botões de controle
        controls_layout = QHBoxLayout()
        select_all_button = QPushButton("SELECIONAR TODOS")
        select_all_button.setFont(QFont("Arial", 14, QFont.Bold))
        select_all_button.clicked.connect(self.select_all_users)

        clear_all_button = QPushButton("LIMPAR SELEÇÃO")
        clear_all_button.setFont(QFont("Arial", 14, QFont.Bold))
        clear_all_button.clicked.connect(self.clear_all_users)

        controls_layout.addWidget(select_all_button)
        controls_layout.addWidget(clear_all_button)
        users_layout.addLayout(controls_layout)

        # Área de scroll para os usuários
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.users_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        users_layout.addWidget(scroll_area)

        self.tab_widget.addTab(users_tab, "USUÁRIOS")

    def setup_settings_tab(self):
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        # Título da aba
        title_label = QLabel("CONFIGURAÇÕES DO SISTEMA")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {COLORS['yellow']}; margin-bottom: 20px;")
        settings_layout.addWidget(title_label)

        # Grupo de configurações
        settings_group = QGroupBox("OPÇÕES GERAIS")
        settings_group.setFont(QFont("Arial", 16, QFont.Bold))
        settings_group_layout = QVBoxLayout(settings_group)

        # Diretório de download
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Diretório de Download:")
        dir_label.setFont(QFont("Arial", 16))
        self.dir_input = QLineEdit(self.download_dir)
        self.dir_input.setFont(QFont("Arial", 16))
        self.dir_input.setMinimumHeight(50)
        dir_button = QPushButton("PROCURAR...")
        dir_button.setFont(QFont("Arial", 14))
        dir_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(dir_button)
        settings_group_layout.addLayout(dir_layout)

        # Modo debug
        self.debug_checkbox = QCheckBox("Modo Debug (baixar arquivos mas não mover/atualizar status)")
        self.debug_checkbox.setFont(QFont("Arial", 16))
        self.debug_checkbox.setChecked(self.debug_mode)
        settings_group_layout.addWidget(self.debug_checkbox)

        settings_layout.addWidget(settings_group)
        settings_layout.addStretch()

        self.tab_widget.addTab(settings_tab, "CONFIGURAÇÕES")

    def login(self):
        """
        Método chamado ao clicar no botão 'CONECTAR AO GESTTA'.
        Faz login na API do Gestta e obtém o token de autenticação.
        """
        try:
            email = self.email_input.text().strip()
            password = self.password_input.text().strip()
            print(f"Email: '{email}'")
            print(f"Password: '{password}'")


            if not email or not password:
                QMessageBox.warning(self, "Atenção", "Por favor, informe email e senha.")
                return

            QApplication.setOverrideCursor(Qt.WaitCursor)

            # Exemplo usando a função get_token() do seu módulo api.py
            # Caso queira fazer manualmente: 
            #   login_url = "https://api.gestta.com.br/core/login"
            #   ...
            self.email = email
            self.password = password

            # Na função login() do arquivo gui.py
            token = get_token(self.email, self.password)  # Pega do módulo api.py, que usa self.email e self.password do config
            # Se o seu get_token() não usa config.py, mas sim argumentos, mude para get_token(email, password)

            if token:
                self.token = token
                QMessageBox.information(self, "Sucesso", "Conectado com sucesso ao Gestta!")
                # Ao logar com sucesso, já podemos carregar empresas e usuários:
                self.fetch_companies()
                self.fetch_users()
            else:
                QMessageBox.critical(self, "Erro", "Não foi possível obter token. Verifique suas credenciais.")

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao conectar: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def fetch_companies(self):
        """
        Faz a busca das empresas via API e preenche o layout de checkboxes.
        """
        if not self.token:
            QMessageBox.warning(self, "Aviso", "Faça login primeiro.")
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            companies = get_all_companies(self.token, company_ids=None)  # se quiser filtrar, passe IDs
            if companies:
                self.all_companies = companies
                self.populate_companies()
                QMessageBox.information(self, "Empresas", f"{len(companies)} empresas carregadas com sucesso.")
            else:
                QMessageBox.information(self, "Empresas", "Nenhuma empresa encontrada ou erro na API.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao buscar empresas: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def fetch_users(self):
        """
        Faz a busca dos usuários via API e preenche o layout de checkboxes.
        """
        if not self.token:
            QMessageBox.warning(self, "Aviso", "Faça login primeiro.")
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            users = get_all_users(self.token, user_ids=None)  # se quiser filtrar, passe IDs
            if users:
                self.all_users = users
                self.populate_users()
                QMessageBox.information(self, "Usuários", f"{len(users)} usuários carregados com sucesso.")
            else:
                QMessageBox.information(self, "Usuários", "Nenhum usuário encontrado ou erro na API.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao buscar usuários: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def populate_companies(self):
        """
        Preenche o layout de empresas com checkboxes.
        """
        # Limpa layout atual
        self.clear_layout(self.companies_layout)
        self.company_checkboxes = {}

        title_label = QLabel("SELECIONE AS EMPRESAS PARA PROCESSAR:")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet(f"color: {COLORS['yellow']};")
        self.companies_layout.addWidget(title_label)

        for company in self.all_companies:
            company_id = company.get("_id", "")
            company_name = f"{company.get('code', 'N/A')} - {company.get('name', 'Desconhecido')}"
            checkbox = QCheckBox(company_name)
            checkbox.setFont(QFont("Arial", 16))
            if company_id in self.selected_companies:
                checkbox.setChecked(True)
            self.company_checkboxes[company_id] = checkbox
            self.companies_layout.addWidget(checkbox)

        self.companies_layout.addStretch()

    def populate_users(self):
        """
        Preenche o layout de usuários com checkboxes.
        """
        self.clear_layout(self.users_layout)
        self.user_checkboxes = {}

        title_label = QLabel("SELECIONE OS USUÁRIOS PARA PROCESSAR:")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet(f"color: {COLORS['yellow']};")
        self.users_layout.addWidget(title_label)

        for user in self.all_users:
            user_id = user.get("_id", "")
            user_name = f"{user.get('name', 'Desconhecido')} ({user.get('email', 'Sem email')})"
            checkbox = QCheckBox(user_name)
            checkbox.setFont(QFont("Arial", 16))
            if user_id in self.selected_users:
                checkbox.setChecked(True)
            self.user_checkboxes[user_id] = checkbox
            self.users_layout.addWidget(checkbox)

        self.users_layout.addStretch()

    def clear_layout(self, layout):
        """
        Remove todos os widgets de um layout recursivamente.
        """
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def select_all_companies(self):
        for checkbox in self.company_checkboxes.values():
            checkbox.setChecked(True)

    def clear_all_companies(self):
        for checkbox in self.company_checkboxes.values():
            checkbox.setChecked(False)

    def select_all_users(self):
        for checkbox in self.user_checkboxes.values():
            checkbox.setChecked(True)

    def clear_all_users(self):
        for checkbox in self.user_checkboxes.values():
            checkbox.setChecked(False)

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Selecionar Diretório de Download",
            self.dir_input.text(), QFileDialog.ShowDirsOnly
        )
        if directory:
            self.dir_input.setText(directory)

    def save_config(self):
        """
        Salva as configurações em arquivo JSON.
        """
        try:
            selected_companies = [
                comp_id for comp_id, checkbox in self.company_checkboxes.items() if checkbox.isChecked()
            ]
            selected_users = [
                user_id for user_id, checkbox in self.user_checkboxes.items() if checkbox.isChecked()
            ]

            # Atualiza variáveis internas
            self.selected_companies = selected_companies
            self.selected_users = selected_users
            self.email = self.email_input.text()
            self.password = self.password_input.text()
            self.download_dir = self.dir_input.text()
            self.debug_mode = self.debug_checkbox.isChecked()

            # Monta dicionário de config
            config = {
                "credentials": {
                    "email": self.email,
                    "password": self.password
                },
                "settings": {
                    "debug_mode": self.debug_mode,
                    "download_dir": self.download_dir
                },
                "selected_companies": selected_companies,
                "selected_users": selected_users
            }

            # Salva em JSON
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)

            # Mensagem de sucesso
            msg = f"Configuração salva com:\n\n"
            msg += f"• {len(selected_companies)} empresas selecionadas\n\n"
            msg += f"• {len(selected_users)} usuários selecionados\n\n"
            msg += f"• Modo debug: {'Ativado' if self.debug_mode else 'Desativado'}\n\n"
            msg += f"O sistema agora utilizará estas configurações."

            msg_box = QMessageBox()
            msg_box.setStyleSheet("QLabel{ font-size: 16px; min-width: 500px; }")
            msg_box.setWindowTitle("Configuração Salva")
            msg_box.setText(msg)

            # Se tiver um ícone de sucesso (opcional):
            if os.path.exists("check_icon.png"):
                msg_box.setIconPixmap(QPixmap("check_icon.png"))

            msg_box.exec_()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar configuração: {str(e)}")

    def load_config(self):
        """
        Carrega as configurações do arquivo JSON (se existir) e preenche os campos.
        """
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)

            # Carregar credenciais
            if "credentials" in config:
                creds = config["credentials"]
                if "email" in creds:
                    self.email = creds["email"]
                    self.email_input.setText(self.email)
                if "password" in creds:
                    self.password = creds["password"]
                    self.password_input.setText(self.password)

            # Carregar configurações
            if "settings" in config:
                settings = config["settings"]
                if "debug_mode" in settings:
                    self.debug_mode = settings["debug_mode"]
                    self.debug_checkbox.setChecked(self.debug_mode)
                if "download_dir" in settings:
                    self.download_dir = settings["download_dir"]
                    self.dir_input.setText(self.download_dir)

            # Seleções prévias de empresas/usuários
            self.selected_companies = config.get("selected_companies", [])
            self.selected_users = config.get("selected_users", [])

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar configuração: {str(e)}")
