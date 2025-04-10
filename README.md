# Gerenciador de Tarefas Web Avançado

Um sistema completo de gerenciamento de tarefas com Kanban, Pomodoro e estatísticas, desenvolvido em Python com Flask.

## 🚀 Funcionalidades Principais

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

## 📦 Requisitos

- Python 3.8+
- pip
- SQLite3 (incluído no Python)

## 🔧 Instalação

1. Clone o repositório:
```bash
git clone https://github.com/daviermac/projeto_integrador
cd projeto_integrador
```

2. Crie e ative o ambiente virtual:
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Execute a aplicação:
```bash
python app.py
```

5. Acesse no navegador:
```
http://localhost:5000
```

## 🏗️ Estrutura do Projeto

```
projeto_integrador/
├── app.py              # Aplicação principal
├── models.py           # Modelos de banco de dados
├── implementos.py      # Utilitários e helpers
├── requirements.txt    # Dependências
├── static/             # CSS, JS, imagens
│   └── uploads/        # Arquivos enviados
├── templates/          # Templates HTML
└── instance/           # Banco de dados SQLite
```

# Rodar em modo desenvolvimento
export FLASK_ENV=development
flask run
```

