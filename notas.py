from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Nota, CategoriaNota, VersaoNota, Tarefa
from datetime import datetime, timedelta
import json
import re

notas_bp = Blueprint('notas', __name__)

@notas_bp.route('/')
@login_required
def index():
    """Página principal do gerenciador de notas"""
    # Obter parâmetros de filtro
    categoria_id = request.args.get('categoria', type=int)
    busca = request.args.get('busca', '').strip()
    ordenar_por = request.args.get('ordenar', 'data_modificacao')  # data_modificacao, titulo, data_criacao
    favoritas = request.args.get('favoritas', 'false').lower() == 'true'

    # Query base
    query = Nota.query.filter_by(usuario_id=current_user.id)

    # Aplicar filtros
    if categoria_id:
        query = query.filter_by(categoria_id=categoria_id)

    if favoritas:
        query = query.filter_by(favorita=True)

    if busca:
        # Busca no título e conteúdo
        query = query.filter(
            db.or_(
                Nota.titulo.contains(busca),
                Nota.conteudo.contains(busca)
            )
        )

    # Aplicar ordenação
    if ordenar_por == 'titulo':
        query = query.order_by(Nota.titulo)
    elif ordenar_por == 'data_criacao':
        query = query.order_by(Nota.data_criacao.desc())
    else:  # data_modificacao
        query = query.order_by(Nota.data_modificacao.desc())

    notas = query.all()

    # Obter categorias do usuário
    categorias = CategoriaNota.query.filter_by(usuario_id=current_user.id).all()

    # Adicionar categoria "Todas" e "Sem categoria"
    todas_categorias = [CategoriaNota(id=0, nome='Todas', cor='#6b7280')] + categorias

    # Estatísticas
    total_notas = Nota.query.filter_by(usuario_id=current_user.id).count()
    notas_favoritas = Nota.query.filter_by(usuario_id=current_user.id, favorita=True).count()
    notas_por_categoria = {}
    for categoria in categorias:
        notas_por_categoria[categoria.id] = Nota.query.filter_by(
            usuario_id=current_user.id,
            categoria_id=categoria.id
        ).count()

    return render_template(
        'notas.html',
        notas=notas,
        categorias=todas_categorias,
        categoria_atual=categoria_id,
        busca=busca,
        ordenar_por=ordenar_por,
        favoritas=favoritas,
        total_notas=total_notas,
        notas_favoritas=notas_favoritas,
        notas_por_categoria=notas_por_categoria,
        current_user=current_user,
        current_year=datetime.now().year
    )

@notas_bp.route('/nota/nova', methods=['GET', 'POST'])
@login_required
def nova_nota():
    """Criar nova nota"""
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        conteudo = request.form.get('conteudo', '').strip()
        categoria_id = request.form.get('categoria_id', type=int)
        cor_fundo = request.form.get('cor_fundo', '#ffffff')
        tarefa_id = request.form.get('tarefa_id')

        if not titulo:
            titulo = 'Nota sem título'

        if not conteudo:
            flash('O conteúdo da nota não pode estar vazio!', 'error')
            return redirect(url_for('notas.nova_nota'))

        try:
            nova_nota = Nota(
                titulo=titulo,
                conteudo=conteudo,
                conteudo_html=converter_markdown_html(conteudo),
                cor_fundo=cor_fundo,
                usuario_id=current_user.id,
                categoria_id=categoria_id if categoria_id else None,
                tarefa_id=tarefa_id if tarefa_id else None
            )

            db.session.add(nova_nota)
            db.session.commit()

            flash('Nota criada com sucesso!', 'success')
            return redirect(url_for('notas.index'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar nota: {str(e)}', 'error')
            return redirect(url_for('notas.nova_nota'))

    # GET - mostrar formulário
    categorias = CategoriaNota.query.filter_by(usuario_id=current_user.id).all()
    tarefas = Tarefa.query.filter_by(usuario_id=current_user.id, concluida=False).all()

    return render_template(
        'nota_form.html',
        titulo='Nova Nota',
        nota=None,
        categorias=categorias,
        tarefas=tarefas,
        current_user=current_user,
        current_year=datetime.now().year
    )

@notas_bp.route('/nota/<int:id>', methods=['GET'])
@login_required
def ver_nota(id):
    """Visualizar nota específica"""
    nota = Nota.query.get_or_404(id)

    if nota.usuario_id != current_user.id:
        flash('Você não tem permissão para visualizar esta nota!', 'error')
        return redirect(url_for('notas.index'))

    # Obter versões da nota
    versoes = VersaoNota.query.filter_by(nota_id=id).order_by(VersaoNota.data_criacao.desc()).limit(10).all()

    return render_template(
        'nota_detalhe.html',
        nota=nota,
        versoes=versoes,
        current_user=current_user,
        current_year=datetime.now().year
    )

@notas_bp.route('/nota/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_nota(id):
    """Editar nota existente"""
    nota = Nota.query.get_or_404(id)

    if nota.usuario_id != current_user.id:
        flash('Você não tem permissão para editar esta nota!', 'error')
        return redirect(url_for('notas.index'))

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        conteudo = request.form.get('conteudo', '').strip()
        categoria_id = request.form.get('categoria_id', type=int)
        cor_fundo = request.form.get('cor_fundo', '#ffffff')
        tarefa_id = request.form.get('tarefa_id')

        if not titulo:
            titulo = 'Nota sem título'

        if not conteudo:
            flash('O conteúdo da nota não pode estar vazio!', 'error')
            return redirect(url_for('notas.editar_nota', id=id))

        try:
            # Salvar versão anterior se o conteúdo mudou
            if nota.conteudo != conteudo:
                nota.salvar_versao()

            # Atualizar nota
            nota.titulo = titulo
            nota.conteudo = conteudo
            nota.conteudo_html = converter_markdown_html(conteudo)
            nota.data_modificacao = datetime.utcnow()
            nota.cor_fundo = cor_fundo
            nota.categoria_id = categoria_id if categoria_id else None
            nota.tarefa_id = tarefa_id if tarefa_id else None

            db.session.commit()

            flash('Nota atualizada com sucesso!', 'success')
            return redirect(url_for('notas.index'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar nota: {str(e)}', 'error')
            return redirect(url_for('notas.editar_nota', id=id))

    # GET - mostrar formulário
    categorias = CategoriaNota.query.filter_by(usuario_id=current_user.id).all()
    tarefas = Tarefa.query.filter_by(usuario_id=current_user.id, concluida=False).all()

    return render_template(
        'nota_form.html',
        titulo='Editar Nota',
        nota=nota,
        categorias=categorias,
        tarefas=tarefas,
        current_user=current_user,
        current_year=datetime.now().year
    )

@notas_bp.route('/nota/<int:id>/deletar', methods=['POST'])
@login_required
def deletar_nota(id):
    """Deletar nota"""
    nota = Nota.query.get_or_404(id)

    if nota.usuario_id != current_user.id:
        flash('Você não tem permissão para deletar esta nota!', 'error')
        return redirect(url_for('notas.index'))

    try:
        db.session.delete(nota)
        db.session.commit()
        flash('Nota deletada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar nota: {str(e)}', 'error')

    return redirect(url_for('notas.index'))

@notas_bp.route('/nota/<int:id>/favoritar', methods=['POST'])
@login_required
def favoritar_nota(id):
    """Alternar status de favorita da nota"""
    nota = Nota.query.get_or_404(id)

    if nota.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permissão negada'}), 403

    nota.favorita = not nota.favorita
    db.session.commit()

    return jsonify({
        'success': True,
        'favorita': nota.favorita
    })

@notas_bp.route('/nota/<int:id>/versao/<int:versao_id>/restaurar', methods=['POST'])
@login_required
def restaurar_versao(id, versao_id):
    """Restaurar uma versão específica da nota"""
    nota = Nota.query.get_or_404(id)

    if nota.usuario_id != current_user.id:
        flash('Você não tem permissão para modificar esta nota!', 'error')
        return redirect(url_for('notas.ver_nota', id=id))

    try:
        nota.restaurar_versao(versao_id)
        flash('Versão restaurada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao restaurar versão: {str(e)}', 'error')

    return redirect(url_for('notas.ver_nota', id=id))

@notas_bp.route('/categoria/nova', methods=['POST'])
@login_required
def nova_categoria():
    """Criar nova categoria via AJAX"""
    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#6b7280')

    if not nome:
        return jsonify({'success': False, 'message': 'Nome da categoria é obrigatório'})

    # Verificar se categoria já existe
    categoria_existente = CategoriaNota.query.filter_by(
        usuario_id=current_user.id,
        nome=nome
    ).first()

    if categoria_existente:
        return jsonify({'success': False, 'message': 'Categoria já existe'})

    try:
        nova_categoria = CategoriaNota(
            nome=nome,
            cor=cor,
            usuario_id=current_user.id
        )

        db.session.add(nova_categoria)
        db.session.commit()

        return jsonify({
            'success': True,
            'categoria': {
                'id': nova_categoria.id,
                'nome': nova_categoria.nome,
                'cor': nova_categoria.cor
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar categoria: {str(e)}'})

@notas_bp.route('/categoria/<int:id>/editar', methods=['POST'])
@login_required
def editar_categoria(id):
    """Editar categoria via AJAX"""
    categoria = CategoriaNota.query.get_or_404(id)

    if categoria.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permissão negada'}), 403

    nome = request.form.get('nome', '').strip()
    cor = request.form.get('cor', '#6b7280')

    if not nome:
        return jsonify({'success': False, 'message': 'Nome da categoria é obrigatório'})

    try:
        categoria.nome = nome
        categoria.cor = cor
        db.session.commit()

        return jsonify({
            'success': True,
            'categoria': {
                'id': categoria.id,
                'nome': categoria.nome,
                'cor': categoria.cor
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao editar categoria: {str(e)}'})

@notas_bp.route('/categoria/<int:id>/deletar', methods=['POST'])
@login_required
def deletar_categoria(id):
    """Deletar categoria via AJAX"""
    categoria = CategoriaNota.query.get_or_404(id)

    if categoria.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permissão negada'}), 403

    try:
        # Mover notas para categoria "Sem categoria" (None)
        Nota.query.filter_by(categoria_id=id).update({'categoria_id': None})
        db.session.delete(categoria)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao deletar categoria: {str(e)}'})

@notas_bp.route('/api/salvar', methods=['POST'])
@login_required
def salvar_nota_api():
    """API para salvar nota automaticamente (AJAX)"""
    nota_id = request.form.get('id', type=int)
    titulo = request.form.get('titulo', '').strip()
    conteudo = request.form.get('conteudo', '').strip()

    if not nota_id:
        return jsonify({'success': False, 'message': 'ID da nota é obrigatório'})

    nota = Nota.query.get_or_404(nota_id)

    if nota.usuario_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permissão negada'}), 403

    try:
        # Salvar versão se conteúdo mudou
        if nota.conteudo != conteudo:
            nota.salvar_versao()

        # Atualizar nota
        nota.titulo = titulo or 'Nota sem título'
        nota.conteudo = conteudo
        nota.conteudo_html = converter_markdown_html(conteudo)
        nota.data_modificacao = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'nota': {
                'id': nota.id,
                'titulo': nota.titulo,
                'data_modificacao': nota.data_modificacao.strftime('%d/%m/%Y %H:%M')
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao salvar: {str(e)}'})

@notas_bp.route('/api/busca')
@login_required
def api_busca():
    """API para busca de notas"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'notas': []})

    # Buscar notas
    notas = Nota.query.filter(
        Nota.usuario_id == current_user.id,
        db.or_(
            Nota.titulo.contains(query),
            Nota.conteudo.contains(query)
        )
    ).limit(10).all()

    resultados = []
    for nota in notas:
        # Destacar texto da busca
        titulo_destacado = destacar_texto(nota.titulo, query)
        conteudo_destacado = destacar_texto(nota.conteudo[:200], query)

        resultados.append({
            'id': nota.id,
            'titulo': titulo_destacado,
            'conteudo_preview': conteudo_destacado,
            'categoria': nota.categoria_obj.nome if nota.categoria_obj else 'Sem categoria',
            'data_modificacao': nota.data_modificacao.strftime('%d/%m/%Y')
        })

    return jsonify({'notas': resultados})

def converter_markdown_html(texto):
    """Converte Markdown básico para HTML"""
    if not texto:
        return texto

    # Converter negrito **texto** ou __texto__
    texto = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', texto)
    texto = re.sub(r'__(.*?)__', r'<strong>\1</strong>', texto)

    # Converter itálico *texto* ou _texto_
    texto = re.sub(r'\*(.*?)\*', r'<em>\1</em>', texto)
    texto = re.sub(r'_(.*?)_', r'<em>\1</em>', texto)

    # Converter listas
    texto = re.sub(r'^\* (.*)$', r'<li>\1</li>', texto, flags=re.MULTILINE)
    texto = re.sub(r'^- (.*)$', r'<li>\1</li>', texto, flags=re.MULTILINE)

    # Envolver listas em <ul>
    linhas = texto.split('\n')
    texto = ''
    em_lista = False

    for linha in linhas:
        if linha.startswith('<li>'):
            if not em_lista:
                texto += '<ul>'
                em_lista = True
            texto += linha
        else:
            if em_lista:
                texto += '</ul>'
                em_lista = False
            texto += linha

    if em_lista:
        texto += '</ul>'

    # Converter quebras de linha para <br>
    texto = texto.replace('\n', '<br>')

    return texto

def destacar_texto(texto, query):
    """Destaca o texto da busca no resultado"""
    if not query or not texto:
        return texto

    # Escapar caracteres especiais da query
    query_escaped = re.escape(query)

    # Destacar ocorrências
    padrao = f'({query_escaped})'
    return re.sub(padrao, r'<mark>\1</mark>', texto, flags=re.IGNORECASE)
