from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import io
import csv
from sqlalchemy import func, extract, inspect, text

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.secret_key = 'minha_chave_secreta_12345'

# Configuração do SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gerenciador_tarefas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Adicionar hasattr ao contexto global do Jinja2
app.jinja_env.globals['hasattr'] = hasattr

# Inicializar o banco de dados
db = SQLAlchemy(app)

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modelo de Usuário
class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    tema = db.Column(db.String(20), default='light')  # Campo para tema (light/dark)
    tarefas = db.relationship('Tarefa', backref='usuario', lazy=True, cascade="all, delete-orphan")
    
    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
        
    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f'<Usuario {self.nome}>'

class Tarefa(db.Model):
    __tablename__ = 'tarefas'
    
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    concluida = db.Column(db.Boolean, default=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    data_vencimento = db.Column(db.DateTime, nullable=True)  # Data de vencimento
    prioridade = db.Column(db.String(20), default='normal')  # baixa, normal, alta
    categoria = db.Column(db.String(50), nullable=True)  # categoria da tarefa (ex: escola, trabalho, pessoal)
    notas = db.Column(db.Text, nullable=True)  # Notas adicionais
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    def __repr__(self):
        return f'<Tarefa {self.id}: {self.descricao}>'
    
    def esta_atrasada(self):
        if self.data_vencimento and not self.concluida:
            return self.data_vencimento < datetime.utcnow()
        return False
    
    def vence_em_breve(self):
        if self.data_vencimento and not self.concluida:
            agora = datetime.utcnow()
            return agora <= self.data_vencimento <= (agora + timedelta(days=3))
        return False

# User loader para o Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Função para verificar e adicionar colunas faltantes
def verificar_e_atualizar_schema():
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Verificar e adicionar coluna 'tema' na tabela 'usuarios'
        if 'tema' not in [col['name'] for col in inspector.get_columns('usuarios')]:
            print("Adicionando coluna 'tema' à tabela 'usuarios'")
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN tema VARCHAR(20) DEFAULT 'light'"))
            db.session.commit()
        
        # Verificar e adicionar coluna 'data_vencimento' na tabela 'tarefas'
        if 'data_vencimento' not in [col['name'] for col in inspector.get_columns('tarefas')]:
            print("Adicionando coluna 'data_vencimento' à tabela 'tarefas'")
            db.session.execute(text("ALTER TABLE tarefas ADD COLUMN data_vencimento DATETIME"))
            db.session.commit()
        
        # Verificar e adicionar coluna 'notas' na tabela 'tarefas'
        if 'notas' not in [col['name'] for col in inspector.get_columns('tarefas')]:
            print("Adicionando coluna 'notas' à tabela 'tarefas'")
            db.session.execute(text("ALTER TABLE tarefas ADD COLUMN notas TEXT"))
            db.session.commit()

# Criar as tabelas do banco de dados e verificar o schema
with app.app_context():
    db.create_all()
    verificar_e_atualizar_schema()

# Rotas de autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Email ou senha incorretos!', 'error')
    
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        confirmar_senha = request.form['confirmar_senha']
        
        if senha != confirmar_senha:
            flash('As senhas não coincidem!', 'error')
            return render_template('registro.html')
        
        if Usuario.query.filter_by(email=email).first():
            flash('Este email já está em uso!', 'error')
            return render_template('registro.html')
        
        novo_usuario = Usuario(nome=nome, email=email, tema='light')
        novo_usuario.set_senha(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        flash('Conta criada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/logout')
def logout():
    logout_user()
    flash('Você saiu da sua conta!', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # Implementação de filtros e busca
    filtro = request.args.get('filtro')
    busca = request.args.get('busca')
    
    query = Tarefa.query.filter_by(usuario_id=current_user.id)
    
    if filtro == 'pendentes':
        query = query.filter_by(concluida=False)
    elif filtro == 'concluidas':
        query = query.filter_by(concluida=True)
    elif filtro == 'alta':
        query = query.filter_by(prioridade='alta')
    elif filtro == 'atrasadas':
        query = query.filter(Tarefa.data_vencimento < datetime.utcnow(), Tarefa.concluida == False)
    elif filtro == 'hoje':
        hoje = datetime.utcnow().date()
        query = query.filter(
            func.date(Tarefa.data_vencimento) == hoje,
            Tarefa.concluida == False
        )
    
    if busca:
        query = query.filter(Tarefa.descricao.contains(busca))
    
    # Ordenar por prioridade e data de criação
    query = query.order_by(
        Tarefa.prioridade.desc(),
        Tarefa.data_criacao.desc()
    )
    
    usuario_tarefas = query.all()
    
    # Garantir que o usuário tenha um tema definido
    if not hasattr(current_user, 'tema') or current_user.tema is None:
        current_user.tema = 'light'
        db.session.commit()
    
    return render_template(
        'index.html', 
        tarefas=usuario_tarefas, 
        current_user=current_user, 
        current_year=datetime.now().year
    )

@app.route('/adicionar_tarefa', methods=['POST'])
@login_required
def adicionar_tarefa():
    descricao = request.form['descricao']
    categoria = request.form.get('categoria')
    prioridade = request.form.get('prioridade', 'normal')
    data_vencimento_str = request.form.get('data_vencimento')
    notas = request.form.get('notas')
    
    if not descricao:
        flash('A descrição da tarefa não pode estar vazia!', 'error')
        return redirect(url_for('index'))

    # Converter a string de data para objeto datetime
    data_vencimento = None
    if data_vencimento_str:
        try:
            data_vencimento = datetime.strptime(data_vencimento_str, '%Y-%m-%d')
        except ValueError:
            flash('Formato de data inválido!', 'error')
            return redirect(url_for('index'))

    nova_tarefa = Tarefa(
        descricao=descricao, 
        concluida=False, 
        usuario_id=current_user.id,
        categoria=categoria,
        prioridade=prioridade,
        data_vencimento=data_vencimento,
        notas=notas
    )
    db.session.add(nova_tarefa)
    db.session.commit()
    
    flash('Tarefa adicionada com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/toggle_tarefa/<int:id>', methods=['POST'])
@login_required
def toggle_tarefa(id):
    tarefa = Tarefa.query.get(id)
    if tarefa and tarefa.usuario_id == current_user.id:
        tarefa.concluida = not tarefa.concluida
        if tarefa.concluida:
            tarefa.data_conclusao = datetime.utcnow()
        else:
            tarefa.data_conclusao = None
        db.session.commit()
        flash('Status da tarefa atualizado com sucesso!', 'success')
    else:
        flash('Tarefa não encontrada ou você não tem permissão para modificar!', 'error')
    
    return redirect(url_for('index'))

@app.route('/editar_tarefa/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_tarefa(id):
    tarefa = Tarefa.query.get(id)
    
    if not tarefa or tarefa.usuario_id != current_user.id:
        flash('Tarefa não encontrada ou você não tem permissão para editar!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        descricao = request.form['descricao']
        categoria = request.form.get('categoria')
        prioridade = request.form.get('prioridade', 'normal')
        data_vencimento_str = request.form.get('data_vencimento')
        notas = request.form.get('notas')
        
        if not descricao:
            flash('A descrição da tarefa não pode estar vazia!', 'error')
            return render_template('editar.html', tarefa=tarefa)
        
        # Converter a string de data para objeto datetime
        data_vencimento = None
        if data_vencimento_str:
            try:
                data_vencimento = datetime.strptime(data_vencimento_str, '%Y-%m-%d')
            except ValueError:
                flash('Formato de data inválido!', 'error')
                return render_template('editar.html', tarefa=tarefa)
        
        tarefa.descricao = descricao
        tarefa.categoria = categoria
        tarefa.prioridade = prioridade
        tarefa.data_vencimento = data_vencimento
        tarefa.notas = notas
        
        db.session.commit()
        flash('Tarefa atualizada com sucesso!', 'success')
        return redirect(url_for('index'))
    
    return render_template('editar.html', tarefa=tarefa, current_user=current_user, current_year=datetime.now().year)

@app.route('/deletar_tarefa/<int:id>', methods=['POST'])
@login_required
def deletar_tarefa(id):
    tarefa = Tarefa.query.get(id)
    if tarefa and tarefa.usuario_id == current_user.id:
        db.session.delete(tarefa)
        db.session.commit()
        flash('Tarefa deletada com sucesso!', 'success')
    else:
        flash('Tarefa não encontrada ou você não tem permissão para deletar!', 'error')
    
    return redirect(url_for('index'))

@app.route('/alternar_tema', methods=['POST'])
@login_required
def alternar_tema():
    # Garantir que o usuário tenha um tema definido
    if not hasattr(current_user, 'tema') or current_user.tema is None:
        current_user.tema = 'light'
    
    if current_user.tema == 'light':
        current_user.tema = 'dark'
    else:
        current_user.tema = 'light'
    
    db.session.commit()
    
    # Se a requisição for AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'tema': current_user.tema})
    
    # Caso contrário, redirecionar de volta para a página anterior
    return redirect(request.referrer or url_for('index'))

# Contexto para os templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

if __name__ == '__main__':
    app.run(debug=True)
