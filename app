from flask import Flask, render_template, request, redirect, url_for, flash # type: ignore
from flask_sqlalchemy import SQLAlchemy # type: ignore
import os

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tarefas.db'
db = SQLAlchemy(app)

class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    concluida = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    tarefas = Tarefa.query.all()
    return render_template('index.html', tarefas=tarefas)

@app.route('/adicionar', methods=['POST'])
def adicionar():
    descricao = request.form['descricao']
    if not descricao:
        flash('A descrição da tarefa não pode estar vazia!', 'error')
        return redirect(url_for('index'))

    nova_tarefa = Tarefa(descricao=descricao)
    flash('Tarefa adicionada com sucesso!', 'success')

    db.session.add(nova_tarefa)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/concluir/<int:id>')
def concluir(id):
    tarefa = Tarefa.query.get_or_404(id)
    tarefa.concluida = not tarefa.concluida
    db.session.commit()
    flash('Tarefa concluída com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/deletar/<int:id>')
def deletar(id):
    tarefa = Tarefa.query.get_or_404(id)
    db.session.delete(tarefa)
    db.session.commit()
    flash('Tarefa deletada com sucesso!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
