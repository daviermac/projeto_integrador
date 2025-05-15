# Gerenciador de Tarefas Web Avançado

Um sistema completo de gerenciamento de tarefas com Kanban, Pomodoro e estatísticas, desenvolvido em Python com Flask.

## Funcionalidades Principais

- **Tarefas Básicas**
  - Adicionar/editar/remover tarefas
  - Marcar tarefas como concluídas
  - Busca e filtragem de tarefas

- **Kanban**
  - Organização visual em colunas (To-Do, Doing, Done)
  - Arrastar e soltar tarefas entre colunas

- **Pomodoro**
  - Temporizador configurável
  - Histórico de sessões
  - Notificações sonoras

- **Estatísticas**
  - Gráficos de produtividade
  - Relatório de tempo gasto por tarefa
  - Métricas semanais/mensais

- **Autenticação**
  - Login e registro de usuários
  - Perfil personalizado
  - Recuperação de senha

## Requisitos

- Python 3.8+
- pip
- SQLite3 (incluído no Python)

## Dependências

O projeto utiliza as seguintes bibliotecas Python, que estão listadas no arquivo `requirements.txt`:

- Flask==2.3.2
- Flask-SQLAlchemy==3.0.3
- Werkzeug==2.3.6
- Jinja2==3.1.2
- SQLAlchemy==2.0.19
- Flask-Login==0.6.2
- python-dotenv==1.0.0
- Flask-Mail (para envio de emails de redefinição de senha)

Para instalar todas as dependências, execute:

```bash
pip install -r requirements.txt

1: Instalação e Execução:

git clone https://github.com/daviermac/projeto_integrador.git
cd projeto_integrador


2: Crie e ative o ambiente virtual:
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate


3:Instale as dependências

pip install -r requirements.txt


4: Execute a aplicação:
python app.py

