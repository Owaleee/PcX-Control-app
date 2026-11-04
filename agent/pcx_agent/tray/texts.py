"""Todo texto visivel da bandeja e das janelas. Mude as frases por aqui.

Mensagens de erro de regra (senha curta, senhas diferentes, PC sem rede) vem do
AgentController, junto da regra.
"""

APP_NAME = "PcX Control"

# Menu da bandeja (nesta ordem)
MENU_PAIR = "Parear celular"
MENU_DEVICES = "Celulares pareados"
MENU_DIAGNOSTICS = "Verificar conexão"
MENU_PASSWORD = "Trocar senha"
MENU_AUTOSTART = "Iniciar com o Windows"
MENU_LOGS = "Abrir pasta de logs"
MENU_QUIT = "Sair"

# Avisos fora das janelas
ALREADY_RUNNING = "O PcX Control já está rodando."
NOTIFY_PAIRED = "Celular {nome} pareado."
STARTUP_ERROR = "O PcX Control não conseguiu iniciar. Os detalhes estão em {pasta}."

# Titulos das janelas
TITLE_FIRST_RUN = "PcX Control: configuração"
TITLE_PAIRING = "PcX Control: parear celular"
TITLE_DEVICES = "PcX Control: celulares pareados"
TITLE_PASSWORD = "PcX Control: trocar senha"
TITLE_DIAGNOSTICS = "PcX Control: verificar conexão"

# Botoes comuns
CLOSE = "Fechar"
CANCEL = "Cancelar"

# Primeira execucao
STEP_PASSWORD = "Senha"
STEP_PAIR = "Parear celular"
FIRST_RUN_HEADING = "Crie a senha deste PC"
FIRST_RUN_SUBTITLE = "Ela serve para parear um celular sem o QR code. Mínimo de 8 caracteres."
PASSWORD_LABEL = "Senha"
CONFIRM_LABEL = "Confirme a senha"
LATER = "Depois"
CONTINUE = "Continuar"
FINISH = "Concluir"

# Pareamento
PAIRING_HEADING = "Escaneie com o app"
PAIRING_SUBTITLE = "No celular: PcX Control › Adicionar PC › aponte a câmera."
VALID_FOR = "Vale por {tempo}"
ADDRESS_LABEL = "Endereço do PC"
NO_CAMERA_LABEL = "Sem câmera?"
NO_CAMERA_HINT = "Use IP e senha no app"
NEW_CODE = "Gerar outro código"
EXPIRED = "Código expirado.\nGere outro."
PAIRED = "Celular {nome} pareado!"
OPEN_NETWORK_SETTINGS = "Abrir configurações de rede"

# Celulares pareados
DEVICES_HEADING = "Celulares pareados"
DEVICES_SUBTITLE = "Só um celular fica conectado por vez. Desconectar apaga o acesso dele."
COLUMN_NAME = "Nome"
COLUMN_LAST_USED = "Último uso"
COLUMN_STATUS = "Status"
STATUS_ACTIVE = "Conectado agora"
STATUS_PAIRED = "Pareado"
NO_DEVICES = "Nenhum celular pareado ainda."
DISCONNECT = "Desconectar"
DISCONNECT_ALL = "Desconectar todos"
CONFIRM_DISCONNECT_ALL = "Desconectar todos os celulares? Eles vão precisar parear de novo."

# Trocar senha
PASSWORD_HEADING = "Nova senha do PC"
PASSWORD_SUBTITLE = "Não precisa da senha antiga: estar neste PC já prova que ele é seu."
NEW_PASSWORD_LABEL = "Nova senha"
CONFIRM_NEW_LABEL = "Confirme a nova senha"
SAVE = "Salvar"
PASSWORD_CHANGED = "Senha trocada."
ASK_REVOKE_ALL = "Senha trocada. Desconectar também todos os celulares pareados?"

# Diagnostico ("Verificar conexao")
DIAG_HEADING = "Verificar conexão"
DIAG_SUBTITLE = "Confere o que costuma impedir o celular de achar o PC."
DIAG_RUNNING = "Verificando…"
DIAG_SUMMARY_OK = "Nenhum problema encontrado."
DIAG_SUMMARY_PROBLEMS = "{n} problema(s) para resolver."
DIAG_SUMMARY_WARNINGS = "Nenhum problema, {n} ponto(s) de atenção."
DIAG_COPY = "Copiar relatório"
DIAG_COPIED = "Relatório copiado. Cole numa conversa para quem está ajudando."
DIAG_AGAIN = "Verificar de novo"
DIAG_FIX_NETWORK = "Abrir configurações de rede"
DIAG_FIX_FIREWALL = "Criar regra do firewall"
DIAG_STATUS_OK = "OK"
DIAG_STATUS_WARNING = "Atenção"
DIAG_STATUS_PROBLEM = "Problema"
DIAG_STATUS_INFO = "Info"
