from flask import Flask, render_template, request, redirect, url_for, flash, session

from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.secret_key = 'minha_chave_secreta_12345'

# Lista para armazenar usuários registrados
usuarios_registrados = []

# Lista para armazenar tarefas
tarefas = []

# Modelo de Usuário
class Usuario:
    def __init__(self, nome, email, senha):
        self.nome = nome
        self.email = email
        self.senha = senha

# Verificar se o usuário está logado
def verificar_login():
    return 'usuario_id' in session

# Rotas de autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        # Verificar se o usuário existe na lista
        usuario = next((u for u in usuarios_registrados if u.email == email), None)
        
        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.nome
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
        
        # Verificar se as senhas coincidem
        if senha != confirmar_senha:
            flash('As senhas não coincidem!', 'error')
            return render_template('registro.html')
        
        # Verificar se o email já está em uso
        if any(u.email == email for u in usuarios_registrados):
            flash('Este email já está em uso!', 'error')
            return render_template('registro.html')
        
        # Criar novo usuário
        novo_usuario = Usuario(nome=nome, email=email, senha=generate_password_hash(senha))
        usuarios_registrados.append(novo_usuario)
        
        flash('Conta criada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    flash('Você saiu da sua conta!', 'success')
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not verificar_login():
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    usuario_tarefas = [tarefa for tarefa in tarefas if tarefa.usuario_id == usuario_id]
    
    return render_template('index.html', usuario_nome=usuario_id, tarefas=usuario_tarefas)

@app.route('/adicionar', methods=['POST'])
def adicionar():
    if not verificar_login():
        return redirect(url_for('login'))
    
    descricao = request.form['descricao']
    if not descricao:
        flash('A descrição da tarefa não pode estar vazia!', 'error')
        return redirect(url_for('index'))

    nova_tarefa = {'id': len(tarefas) + 1, 'descricao': descricao, 'concluida': False, 'usuario_id': session['usuario_id']}
    tarefas.append(nova_tarefa)
    flash('Tarefa adicionada com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/filtrar', methods=['GET'])
def filtrar():
    if not verificar_login():
        return redirect(url_for('login'))
    
    status = request.args.get('status')
    usuario_id = session['usuario_id']
    
    if status == 'concluida':
        usuario_tarefas = [tarefa for tarefa in tarefas if tarefa['usuario_id'] == usuario_id and tarefa['concluida']]
    elif status == 'nao_concluida':
        usuario_tarefas = [tarefa for tarefa in tarefas if tarefa['usuario_id'] == usuario_id and not tarefa['concluida']]
    else:
        usuario_tarefas = [tarefa for tarefa in tarefas if tarefa['usuario_id'] == usuario_id]
    
    return render_template('index.html', tarefas=usuario_tarefas, usuario_nome=session.get('usuario_id'))

@app.route('/concluir/<int:id>')
def concluir(id):
    if not verificar_login():
        return redirect(url_for('login'))
    
    tarefa = next((t for t in tarefas if t['id'] == id and t['usuario_id'] == session['usuario_id']), None)
    
    if tarefa:
        tarefa['concluida'] = not tarefa['concluida']
        flash('Status da tarefa atualizado com sucesso!', 'success')
    else:
        flash('Tarefa não encontrada ou você não tem permissão para modificar!', 'error')
    
    return redirect(url_for('index'))

@app.route('/deletar/<int:id>')
def deletar(id):
    if not verificar_login():
        return redirect(url_for('login'))
    
    tarefa = next((t for t in tarefas if t['id'] == id and t['usuario_id'] == session['usuario_id']), None)
    
    if tarefa:
        tarefas.remove(tarefa)
        flash('Tarefa deletada com sucesso!', 'success')
    else:
        flash('Tarefa não encontrada ou você não tem permissão para deletar!', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
