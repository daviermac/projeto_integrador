from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_login import UserMixin
import json

# Inicialização do SQLAlchemy
db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    tema = db.Column(db.String(20), default='light')  # light, dark
    config_pomodoro = db.Column(db.String(200), default='{"trabalho": 25, "pausa_curta": 5, "pausa_longa": 15, "ciclos": 4}')
    titulo_pendente = db.Column(db.String(50), default='Pendentes')
    titulo_em_progresso = db.Column(db.String(50), default='Em Progresso')
    titulo_concluida = db.Column(db.String(50), default='Concluídas')
    tarefas = db.relationship('Tarefa', backref='usuario', lazy=True, cascade="all, delete-orphan")

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def get_id(self):
        return str(self.id)

    def get_config_pomodoro(self):
        """Retorna a configuração do Pomodoro como dicionário"""
        try:
            return json.loads(self.config_pomodoro)
        except:
            return {"trabalho": 25, "pausa_curta": 5, "pausa_longa": 15, "ciclos": 4}

    def set_config_pomodoro(self, config):
        """Define a configuração do Pomodoro"""
        self.config_pomodoro = json.dumps(config)

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

# Modelo para Agenda/Calendário
class Evento(db.Model):
    __tablename__ = 'eventos'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    data_inicio = db.Column(db.DateTime, nullable=False)
    data_fim = db.Column(db.DateTime, nullable=True)
    tipo_recorrencia = db.Column(db.String(20), default='nenhum')  # nenhum, diario, semanal, mensal
    intervalo_recorrencia = db.Column(db.Integer, default=1)  # a cada X dias/semanas/meses
    dias_semana = db.Column(db.String(50), nullable=True)  # para recorrência semanal (ex: "1,3,5" para seg, qua, sex)
    data_fim_recorrencia = db.Column(db.DateTime, nullable=True)  # quando parar a recorrência
    cor = db.Column(db.String(7), default='#3b82f6')  # cor do evento no calendário
    local = db.Column(db.String(100), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tarefa_id = db.Column(db.Integer, db.ForeignKey('tarefas.id'), nullable=True)  # link com tarefa se aplicável

    # Relacionamentos
    usuario = db.relationship('Usuario', backref='eventos')
    tarefa = db.relationship('Tarefa', backref='eventos')
    notificacoes = db.relationship('Notificacao', backref='evento', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Evento {self.id}: {self.titulo}>'

    def eh_recorrente(self):
        return self.tipo_recorrencia != 'nenhum'

    def gerar_ocorrencias(self, data_inicio, data_fim):
        """Gera todas as ocorrências do evento no período especificado"""
        ocorrencias = []
        data_atual = self.data_inicio

        while data_atual <= data_fim:
            if data_atual >= data_inicio:
                ocorrencias.append({
                    'data': data_atual,
                    'titulo': self.titulo,
                    'descricao': self.descricao,
                    'cor': self.cor
                })

            if self.tipo_recorrencia == 'diario':
                data_atual += timedelta(days=self.intervalo_recorrencia)
            elif self.tipo_recorrencia == 'semanal':
                data_atual += timedelta(weeks=self.intervalo_recorrencia)
            elif self.tipo_recorrencia == 'mensal':
                # Adicionar meses
                meses = data_atual.month + self.intervalo_recorrencia - 1
                anos = data_atual.year + (meses // 12)
                mes_final = ((meses % 12) + 1)
                data_atual = data_atual.replace(year=anos, month=mes_final)
            else:
                break

            # Verificar se passou da data fim da recorrência
            if self.data_fim_recorrencia and data_atual > self.data_fim_recorrencia:
                break

        return ocorrencias

# Modelo para Notificações
class Notificacao(db.Model):
    __tablename__ = 'notificacoes'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(20), default='info')  # info, warning, success, error
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_agendada = db.Column(db.DateTime, nullable=True)  # quando mostrar a notificação
    lida = db.Column(db.Boolean, default=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=True)

    # Relacionamentos
    usuario = db.relationship('Usuario', backref='notificacoes')

    def __repr__(self):
        return f'<Notificacao {self.id}: {self.titulo}>'

class Nota(db.Model):
    __tablename__ = 'notas'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    conteudo_html = db.Column(db.Text, nullable=True)  # versão renderizada em HTML
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_modificacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    favorita = db.Column(db.Boolean, default=False)
    cor_fundo = db.Column(db.String(7), default='#ffffff')  # cor de fundo da nota
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tarefa_id = db.Column(db.Integer, db.ForeignKey('tarefas.id'), nullable=True)  # link com tarefa se aplicável

    # Relacionamentos
    usuario = db.relationship('Usuario', backref='notas')
    tarefa = db.relationship('Tarefa', backref='notas_relacionadas')
    versoes = db.relationship('VersaoNota', backref='nota', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Nota {self.id}: {self.titulo}>'

    def salvar_versao(self):
        """Salva uma versão da nota antes de modificá-la"""
        versao = VersaoNota(
            conteudo=self.conteudo,
            conteudo_html=self.conteudo_html,
            nota_id=self.id
        )
        db.session.add(versao)
        db.session.commit()

    def restaurar_versao(self, versao_id):
        """Restaura uma versão específica da nota"""
        versao = VersaoNota.query.get(versao_id)
        if versao and versao.nota_id == self.id:
            self.conteudo = versao.conteudo
            self.conteudo_html = versao.conteudo_html
            self.data_modificacao = datetime.utcnow()
            db.session.commit()

class VersaoNota(db.Model):
    __tablename__ = 'versoes_notas'

    id = db.Column(db.Integer, primary_key=True)
    conteudo = db.Column(db.Text, nullable=False)
    conteudo_html = db.Column(db.Text, nullable=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    nota_id = db.Column(db.Integer, db.ForeignKey('notas.id'), nullable=False)

    def __repr__(self):
        return f'<VersaoNota {self.id} da nota {self.nota_id}>'

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
