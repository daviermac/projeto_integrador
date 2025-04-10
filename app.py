from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import io
import csv
import json
import uuid
from sqlalchemy import func, extract, inspect, text

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.secret_key = 'minha_chave_secreta_12345'

# Configuração do SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gerenciador_tarefas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração para upload de arquivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

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
    config_pomodoro = db.Column(db.String(200), default='{"trabalho": 25, "pausa_curta": 5, "pausa_longa": 15, "ciclos": 4}')  # Configurações do Pomodoro
    tarefas = db.relationship('Tarefa', backref='usuario', lazy=True, cascade="all, delete-orphan")
    
    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
        
    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
    
    def get_id(self):
        return str(self.id)
    
    def get_config_pomodoro(self):
        return json.loads(self.config_pomodoro)
    
    def set_config_pomodoro(self, config):
        self.config_pomodoro = json.dumps(config)
    
    def __repr__(self):
        return f'<Usuario {self.nome}>'

# Tabela de anexos
class Anexo(db.Model):
    __tablename__ = 'anexos'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(255), nullable=False)
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)
    tarefa_id = db.Column(db.Integer, db.ForeignKey('tarefas.id', ondelete='CASCADE'), nullable=False)
    
    def __repr__(self):
        return f'<Anexo {self.nome_arquivo}>'

# Tabela de subtarefas
class Subtarefa(db.Model):
    __tablename__ = 'subtarefas'
    
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    concluida = db.Column(db.Boolean, default=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    tarefa_id = db.Column(db.Integer, db.ForeignKey('tarefas.id', ondelete='CASCADE'), nullable=False)
    
    def __repr__(self):
        return f'<Subtarefa {self.id}: {self.descricao}>'

# Tabela de sessões Pomodoro
class SessaoPomodoro(db.Model):
    __tablename__ = 'sessoes_pomodoro'
    
    id = db.Column(db.Integer, primary_key=True)
    data_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    data_fim = db.Column(db.DateTime, nullable=True)
    duracao_minutos = db.Column(db.Integer, nullable=True)
    ciclos_completos = db.Column(db.Integer, default=0)
    tarefa_id = db.Column(db.Integer, db.ForeignKey('tarefas.id'), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    def __repr__(self):
        return f'<SessaoPomodoro {self.id}: {self.duracao_minutos} minutos>'

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
    status_kanban = db.Column(db.String(20), default='pendente')  # pendente, em_progresso, concluida
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    # Relacionamentos
    subtarefas = db.relationship('Subtarefa', backref='tarefa', lazy=True, cascade="all, delete-orphan")
    anexos = db.relationship('Anexo', backref='tarefa', lazy=True, cascade="all, delete-orphan")
    sessoes_pomodoro = db.relationship('SessaoPomodoro', backref='tarefa', lazy=True)
    
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
    
    def progresso_subtarefas(self):
        if not self.subtarefas:
            return 0
        total = len(self.subtarefas)
        concluidas = sum(1 for st in self.subtarefas if st.concluida)
        return int((concluidas / total) * 100) if total > 0 else 0

# User loader para o Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Função para verificar e adicionar colunas faltantes
def verificar_e_atualizar_schema():
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Verificar se as tabelas existem
        tabelas_existentes = inspector.get_table_names()
        
        # Se as tabelas não existem, não precisamos verificar colunas
        if 'usuarios' not in tabelas_existentes or 'tarefas' not in tabelas_existentes:
            return
        
        # Verificar e adicionar coluna 'tema' na tabela 'usuarios'
        if 'tema' not in [col['name'] for col in inspector.get_columns('usuarios')]:
            print("Adicionando coluna 'tema' à tabela 'usuarios'")
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN tema VARCHAR(20) DEFAULT 'light'"))
            db.session.commit()
        
        # Verificar e adicionar coluna 'config_pomodoro' na tabela 'usuarios'
        if 'config_pomodoro' not in [col['name'] for col in inspector.get_columns('usuarios')]:
            print("Adicionando coluna 'config_pomodoro' à tabela 'usuarios'")
            db.session.execute(text("ALTER TABLE usuarios ADD COLUMN config_pomodoro VARCHAR(200) DEFAULT '{\"trabalho\": 25, \"pausa_curta\": 5, \"pausa_longa\": 15, \"ciclos\": 4}'"))
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
        
        # Verificar e adicionar coluna 'status_kanban' na tabela 'tarefas'
        if 'status_kanban' not in [col['name'] for col in inspector.get_columns('tarefas')]:
            print("Adicionando coluna 'status_kanban' à tabela 'tarefas'")
            db.session.execute(text("ALTER TABLE tarefas ADD COLUMN status_kanban VARCHAR(20) DEFAULT 'pendente'"))
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
    status_kanban = request.form.get('status_kanban', 'pendente')
    
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
        notas=notas,
        status_kanban=status_kanban
    )
    db.session.add(nova_tarefa)
    db.session.commit()
    
    # Processar subtarefas (se houver)
    subtarefas = request.form.get('subtarefas')
    if subtarefas:
        try:
            subtarefas_lista = json.loads(subtarefas)
            for st in subtarefas_lista:
                nova_subtarefa = Subtarefa(
                    descricao=st,
                    concluida=False,
                    tarefa_id=nova_tarefa.id
                )
                db.session.add(nova_subtarefa)
            db.session.commit()
        except:
            flash('Erro ao processar subtarefas', 'error')
    
    # Processar anexos (se houver)
    if 'anexo' in request.files:
        arquivo = request.files['anexo']
        if arquivo and arquivo.filename != '':
            nome_seguro = secure_filename(arquivo.filename)
            nome_unico = f"{uuid.uuid4()}_{nome_seguro}"
            caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_unico)
            arquivo.save(caminho_arquivo)
            
            novo_anexo = Anexo(
                nome_arquivo=nome_seguro,
                caminho_arquivo=nome_unico,
                tarefa_id=nova_tarefa.id
            )
            db.session.add(novo_anexo)
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
            tarefa.status_kanban = 'concluida'
        else:
            tarefa.data_conclusao = None
            tarefa.status_kanban = 'pendente'
        db.session.commit()
        flash('Status da tarefa atualizado com sucesso!', 'success')
    else:
        flash('Tarefa não encontrada ou você não tem permissão para modificar!', 'error')
    
    return redirect(request.referrer or url_for('index'))

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
        status_kanban = request.form.get('status_kanban', tarefa.status_kanban)
        
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
        tarefa.status_kanban = status_kanban
        
        db.session.commit()
        
        # Processar anexos 
        if 'anexo' in request.files:
            arquivo = request.files['anexo']
            if arquivo and arquivo.filename != '':
                nome_seguro = secure_filename(arquivo.filename)
                nome_unico = f"{uuid.uuid4()}_{nome_seguro}"
                caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_unico)
                arquivo.save(caminho_arquivo)
                
                novo_anexo = Anexo(
                    nome_arquivo=nome_seguro,
                    caminho_arquivo=nome_unico,
                    tarefa_id=tarefa.id
                )
                db.session.add(novo_anexo)
                db.session.commit()
        
        flash('Tarefa atualizada com sucesso!', 'success')
        return redirect(url_for('index'))
    
    return render_template('editar.html', tarefa=tarefa, current_user=current_user, current_year=datetime.now().year)

@app.route('/deletar_tarefa/<int:id>', methods=['POST'])
@login_required
def deletar_tarefa(id):
    tarefa = Tarefa.query.get(id)
    if tarefa and tarefa.usuario_id == current_user.id:
        # Excluir anexos físicos
        for anexo in tarefa.anexos:
            try:
                caminho_completo = os.path.join(app.config['UPLOAD_FOLDER'], anexo.caminho_arquivo)
                if os.path.exists(caminho_completo):
                    os.remove(caminho_completo)
            except:
                pass
        
        db.session.delete(tarefa)
        db.session.commit()
        flash('Tarefa deletada com sucesso!', 'success')
    else:
        flash('Tarefa não encontrada ou você não tem permissão para deletar!', 'error')
    
    return redirect(request.referrer or url_for('index'))

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

# Rotas para subtarefas
@app.route('/adicionar_subtarefa/<int:tarefa_id>', methods=['POST'])
@login_required
def adicionar_subtarefa(tarefa_id):
    tarefa = Tarefa.query.get(tarefa_id)
    if not tarefa or tarefa.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Tarefa não encontrada ou sem permissão'})
    
    descricao = request.form.get('descricao')
    if not descricao:
        return jsonify({'success': False, 'message': 'Descrição não pode estar vazia'})
    
    nova_subtarefa = Subtarefa(
        descricao=descricao,
        concluida=False,
        tarefa_id=tarefa_id
    )
    db.session.add(nova_subtarefa)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'id': nova_subtarefa.id,
        'descricao': nova_subtarefa.descricao,
        'concluida': nova_subtarefa.concluida
    })

@app.route('/toggle_subtarefa/<int:id>', methods=['POST'])
@login_required
def toggle_subtarefa(id):
    subtarefa = Subtarefa.query.get(id)
    if not subtarefa or subtarefa.tarefa.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Subtarefa não encontrada ou sem permissão'})
    
    subtarefa.concluida = not subtarefa.concluida
    if subtarefa.concluida:
        subtarefa.data_conclusao = datetime.utcnow()
    else:
        subtarefa.data_conclusao = None
    
    db.session.commit()
    
    # Verificar se todas as subtarefas estão concluídas
    tarefa = subtarefa.tarefa
    todas_concluidas = all(st.concluida for st in tarefa.subtarefas) if tarefa.subtarefas else False
    
    return jsonify({
        'success': True, 
        'concluida': subtarefa.concluida,
        'progresso': tarefa.progresso_subtarefas(),
        'todas_concluidas': todas_concluidas
    })

@app.route('/deletar_subtarefa/<int:id>', methods=['POST'])
@login_required
def deletar_subtarefa(id):
    subtarefa = Subtarefa.query.get(id)
    if not subtarefa or subtarefa.tarefa.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Subtarefa não encontrada ou sem permissão'})
    
    tarefa_id = subtarefa.tarefa_id
    db.session.delete(subtarefa)
    db.session.commit()
    
    tarefa = Tarefa.query.get(tarefa_id)
    
    return jsonify({
        'success': True,
        'progresso': tarefa.progresso_subtarefas() if tarefa else 0
    })

# Rotas para anexos
@app.route('/download_anexo/<int:id>')
@login_required
def download_anexo(id):
    anexo = Anexo.query.get(id)
    if not anexo or anexo.tarefa.usuario_id != current_user.id:
        flash('Anexo não encontrado ou sem permissão para acessar', 'error')
        return redirect(url_for('index'))
    
    caminho_completo = os.path.join(app.config['UPLOAD_FOLDER'], anexo.caminho_arquivo)
    return send_file(caminho_completo, as_attachment=True, download_name=anexo.nome_arquivo)

@app.route('/deletar_anexo/<int:id>', methods=['POST'])
@login_required
def deletar_anexo(id):
    anexo = Anexo.query.get(id)
    if not anexo or anexo.tarefa.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Anexo não encontrado ou sem permissão'})
    
    try:
        caminho_completo = os.path.join(app.config['UPLOAD_FOLDER'], anexo.caminho_arquivo)
        if os.path.exists(caminho_completo):
            os.remove(caminho_completo)
    except:
        pass
    
    db.session.delete(anexo)
    db.session.commit()
    
    return jsonify({'success': True})

# Rotas para Kanban
@app.route('/kanban')
@login_required
def kanban():
    tarefas_pendentes = Tarefa.query.filter_by(
        usuario_id=current_user.id, 
        status_kanban='pendente'
    ).order_by(Tarefa.prioridade.desc(), Tarefa.data_criacao.desc()).all()
    
    tarefas_em_progresso = Tarefa.query.filter_by(
        usuario_id=current_user.id, 
        status_kanban='em_progresso'
    ).order_by(Tarefa.prioridade.desc(), Tarefa.data_criacao.desc()).all()
    
    tarefas_concluidas = Tarefa.query.filter_by(
        usuario_id=current_user.id, 
        status_kanban='concluida'
    ).order_by(Tarefa.data_conclusao.desc()).all()
    
    return render_template(
        'kanban.html',
        tarefas_pendentes=tarefas_pendentes,
        tarefas_em_progresso=tarefas_em_progresso,
        tarefas_concluidas=tarefas_concluidas,
        current_user=current_user,
        current_year=datetime.now().year
    )

@app.route('/atualizar_status_kanban/<int:id>', methods=['POST'])
@login_required
def atualizar_status_kanban(id):
    tarefa = Tarefa.query.get(id)
    if not tarefa or tarefa.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Tarefa não encontrada ou sem permissão'})
    
    novo_status = request.form.get('status')
    if novo_status not in ['pendente', 'em_progresso', 'concluida']:
        return jsonify({'success': False, 'message': 'Status inválido'})
    
    tarefa.status_kanban = novo_status
    
    # Se mover para concluída, marcar como concluída também
    if novo_status == 'concluida' and not tarefa.concluida:
        tarefa.concluida = True
        tarefa.data_conclusao = datetime.utcnow()
    # Se mover de concluída para outro status, desmarcar como concluída
    elif novo_status != 'concluida' and tarefa.concluida:
        tarefa.concluida = False
        tarefa.data_conclusao = None
    
    db.session.commit()
    
    return jsonify({'success': True})

# Rotas para Pomodoro
@app.route('/pomodoro')
@login_required
def pomodoro():
    tarefas = Tarefa.query.filter_by(
        usuario_id=current_user.id,
        concluida=False
    ).order_by(Tarefa.prioridade.desc(), Tarefa.data_criacao.desc()).all()
    
    config = current_user.get_config_pomodoro()
    
    return render_template(
        'pomodoro.html',
        tarefas=tarefas,
        config=config,
        current_user=current_user,
        current_year=datetime.now().year
    )

@app.route('/salvar_config_pomodoro', methods=['POST'])
@login_required
def salvar_config_pomodoro():
    try:
        trabalho = int(request.form.get('trabalho', 25))
        pausa_curta = int(request.form.get('pausa_curta', 5))
        pausa_longa = int(request.form.get('pausa_longa', 15))
        ciclos = int(request.form.get('ciclos', 4))
        
        config = {
            'trabalho': trabalho,
            'pausa_curta': pausa_curta,
            'pausa_longa': pausa_longa,
            'ciclos': ciclos
        }
        
        current_user.set_config_pomodoro(config)
        db.session.commit()
        
        return jsonify({'success': True})
    except:
        return jsonify({'success': False, 'message': 'Erro ao salvar configurações'})

@app.route('/registrar_sessao_pomodoro', methods=['POST'])
@login_required
def registrar_sessao_pomodoro():
    try:
        duracao = int(request.form.get('duracao', 0))
        ciclos = int(request.form.get('ciclos', 0))
        tarefa_id = request.form.get('tarefa_id')
        
        if duracao <= 0:
            return jsonify({'success': False, 'message': 'Duração inválida'})
        
        # Converter para minutos se necessário
        duracao_minutos = duracao // 60
        
        nova_sessao = SessaoPomodoro(
            duracao_minutos=duracao_minutos,
            ciclos_completos=ciclos,
            tarefa_id=tarefa_id if tarefa_id and tarefa_id != 'null' else None,
            usuario_id=current_user.id,
            data_fim=datetime.utcnow()
        )
        
        db.session.add(nova_sessao)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao registrar sessão: {str(e)}'})

# Rota para estatísticas
@app.route('/estatisticas')
@login_required
def estatisticas():
    # Total de tarefas
    total_tarefas = Tarefa.query.filter_by(usuario_id=current_user.id).count()
    
    # Tarefas concluídas vs pendentes
    tarefas_concluidas = Tarefa.query.filter_by(usuario_id=current_user.id, concluida=True).count()
    tarefas_pendentes = total_tarefas - tarefas_concluidas
    
    # Tarefas por categoria
    categorias = db.session.query(
        Tarefa.categoria, 
        func.count(Tarefa.id)
    ).filter(
        Tarefa.usuario_id == current_user.id,
        Tarefa.categoria.isnot(None)
    ).group_by(Tarefa.categoria).all()
    
    # Tarefas por prioridade
    prioridades = db.session.query(
        Tarefa.prioridade, 
        func.count(Tarefa.id)
    ).filter(
        Tarefa.usuario_id == current_user.id
    ).group_by(Tarefa.prioridade).all()
    
    # Tarefas concluídas por mês (últimos 6 meses)
    hoje = datetime.utcnow()
    seis_meses_atras = hoje - timedelta(days=180)
    
    tarefas_por_mes = db.session.query(
        extract('year', Tarefa.data_conclusao).label('ano'),
        extract('month', Tarefa.data_conclusao).label('mes'),
        func.count(Tarefa.id).label('total')
    ).filter(
        Tarefa.usuario_id == current_user.id,
        Tarefa.concluida == True,
        Tarefa.data_conclusao >= seis_meses_atras
    ).group_by('ano', 'mes').order_by('ano', 'mes').all()
    
    # Formatar dados para o gráfico
    meses = []
    contagens = []
    
    for ano, mes, total in tarefas_por_mes:
        nome_mes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'][int(mes)-1]
        meses.append(f"{nome_mes}/{int(ano)}")
        contagens.append(total)
    
    # Tempo médio para conclusão de tarefas
    tempo_medio_query = db.session.query(
        func.avg(Tarefa.data_conclusao - Tarefa.data_criacao)
    ).filter(
        Tarefa.usuario_id == current_user.id,
        Tarefa.concluida == True,
        Tarefa.data_conclusao.isnot(None)
    ).scalar()
    
    tempo_medio = None
    if tempo_medio_query:
        tempo_medio = tempo_medio_query.total_seconds() / 86400  # Converter para dias
    
    # Estatísticas do Pomodoro
    total_sessoes = SessaoPomodoro.query.filter_by(usuario_id=current_user.id).count()
    
    tempo_total_pomodoro = db.session.query(
        func.sum(SessaoPomodoro.duracao_minutos)
    ).filter(
        SessaoPomodoro.usuario_id == current_user.id
    ).scalar() or 0
    
    # Sessões de Pomodoro por dia (últimos 30 dias)
    trinta_dias_atras = hoje - timedelta(days=30)
    
    sessoes_por_dia = db.session.query(
        func.date(SessaoPomodoro.data_inicio).label('dia'),
        func.sum(SessaoPomodoro.duracao_minutos).label('minutos')
    ).filter(
        SessaoPomodoro.usuario_id == current_user.id,
        SessaoPomodoro.data_inicio >= trinta_dias_atras
    ).group_by('dia').order_by('dia').all()
    
    dias_pomodoro = []
    minutos_pomodoro = []
    
    for dia, minutos in sessoes_por_dia:
        dias_pomodoro.append(dia.strftime('%d/%m'))
        minutos_pomodoro.append(minutos)
    
    estatisticas = {
        'total_tarefas': total_tarefas,
        'tarefas_concluidas': tarefas_concluidas,
        'tarefas_pendentes': tarefas_pendentes,
        'categorias': dict(categorias),
        'prioridades': dict(prioridades),
        'meses': meses,
        'contagens': contagens,
        'tempo_medio': tempo_medio,
        'total_sessoes_pomodoro': total_sessoes,
        'tempo_total_pomodoro': tempo_total_pomodoro,
        'dias_pomodoro': dias_pomodoro,
        'minutos_pomodoro': minutos_pomodoro
    }
    
    return render_template(
        'estatisticas.html', 
        estatisticas=estatisticas, 
        current_user=current_user, 
        current_year=datetime.now().year
    )

# Contexto para os templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

if __name__ == '__main__':
    app.run(debug=True)
