from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Evento, Notificacao, Tarefa
from datetime import datetime, timedelta, date
import json
import calendar

agenda_bp = Blueprint('agenda', __name__)

@agenda_bp.route('/')
@login_required
def index():
    """Página principal da agenda com visualização mensal"""
    # Obter parâmetros da URL
    ano = request.args.get('ano', datetime.now().year, type=int)
    mes = request.args.get('mes', datetime.now().month, type=int)

    # Garantir que ano e mês são válidos
    if mes < 1:
        mes = 12
        ano -= 1
    elif mes > 12:
        mes = 1
        ano += 1

    # Obter eventos do usuário
    eventos = Evento.query.filter_by(usuario_id=current_user.id).all()

    # Obter tarefas com prazos para mostrar na agenda
    tarefas_com_prazos = Tarefa.query.filter(
        Tarefa.usuario_id == current_user.id,
        Tarefa.data_vencimento.isnot(None),
        Tarefa.concluida == False
    ).all()

    # Gerar dados do calendário
    calendario_data = gerar_calendario_mes(ano, mes, eventos, tarefas_com_prazos)

    # Obter eventos "em breve" (próximos 7 dias)
    hoje = datetime.now().date()
    daqui_7_dias = hoje + timedelta(days=7)

    eventos_proximos = []
    for evento in eventos:
        if evento.data_inicio.date() >= hoje and evento.data_inicio.date() <= daqui_7_dias:
            eventos_proximos.append(evento)

    # Adicionar tarefas com prazos próximos
    for tarefa in tarefas_com_prazos:
        if tarefa.data_vencimento.date() >= hoje and tarefa.data_vencimento.date() <= daqui_7_dias:
            # Criar um "evento" temporário para a tarefa
            evento_temp = {
                'titulo': f'📋 {tarefa.descricao}',
                'data_inicio': tarefa.data_vencimento,
                'cor': '#f59e0b',  # amarelo para tarefas
                'tipo': 'tarefa'
            }
            eventos_proximos.append(evento_temp)

    # Ordenar eventos próximos por data
    eventos_proximos.sort(key=lambda x: x['data_inicio'] if isinstance(x, dict) else x.data_inicio)

    return render_template(
        'agenda.html',
        calendario=calendario_data,
        eventos=eventos,
        eventos_proximos=eventos_proximos,
        ano=ano,
        mes=mes,
        mes_nome=calendar.month_name[mes],
        current_user=current_user,
        current_year=datetime.now().year
    )

@agenda_bp.route('/evento/novo', methods=['GET', 'POST'])
@login_required
def novo_evento():
    """Criar novo evento"""
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        data_inicio_str = request.form.get('data_inicio')
        hora_inicio = request.form.get('hora_inicio', '00:00')
        data_fim_str = request.form.get('data_fim')
        hora_fim = request.form.get('hora_fim', '23:59')
        tipo_recorrencia = request.form.get('tipo_recorrencia', 'nenhum')
        intervalo_recorrencia = request.form.get('intervalo_recorrencia', 1, type=int)
        cor = request.form.get('cor', '#3b82f6')
        local = request.form.get('local')
        tarefa_id = request.form.get('tarefa_id')

        if not titulo or not data_inicio_str:
            flash('Título e data de início são obrigatórios!', 'error')
            return redirect(url_for('agenda.novo_evento'))

        try:
            # Converter datas
            data_inicio = datetime.strptime(f"{data_inicio_str} {hora_inicio}", '%Y-%m-%d %H:%M')
            data_fim = None
            if data_fim_str:
                data_fim = datetime.strptime(f"{data_fim_str} {hora_fim}", '%Y-%m-%d %H:%M')

            # Processar recorrência semanal
            dias_semana = None
            if tipo_recorrencia == 'semanal' and request.form.get('dias_semana'):
                dias_semana = ','.join(request.form.getlist('dias_semana'))

            # Data fim da recorrência
            data_fim_recorrencia = None
            if request.form.get('data_fim_recorrencia'):
                data_fim_recorrencia = datetime.strptime(request.form.get('data_fim_recorrencia'), '%Y-%m-%d')

            novo_evento = Evento(
                titulo=titulo,
                descricao=descricao,
                data_inicio=data_inicio,
                data_fim=data_fim,
                tipo_recorrencia=tipo_recorrencia,
                intervalo_recorrencia=intervalo_recorrencia,
                dias_semana=dias_semana,
                data_fim_recorrencia=data_fim_recorrencia,
                cor=cor,
                local=local,
                usuario_id=current_user.id,
                tarefa_id=tarefa_id if tarefa_id else None
            )

            db.session.add(novo_evento)
            db.session.commit()

            # Criar notificação se solicitado
            if request.form.get('criar_notificacao') == 'on':
                titulo_notif = f"Lembrete: {titulo}"
                mensagem_notif = f"Evento: {titulo}"
                if descricao:
                    mensagem_notif += f"\n\n{descricao}"
                if local:
                    mensagem_notif += f"\nLocal: {local}"

                notificacao = Notificacao(
                    titulo=titulo_notif,
                    mensagem=mensagem_notif,
                    tipo='info',
                    data_agendada=data_inicio - timedelta(hours=1),  # 1 hora antes
                    usuario_id=current_user.id,
                    evento_id=novo_evento.id
                )
                db.session.add(notificacao)
                db.session.commit()

            flash('Evento criado com sucesso!', 'success')
            return redirect(url_for('agenda.index'))

        except ValueError as e:
            flash(f'Erro nos dados: {str(e)}', 'error')
            return redirect(url_for('agenda.novo_evento'))

    # GET - mostrar formulário
    # Obter tarefas do usuário para associar ao evento
    tarefas = Tarefa.query.filter_by(usuario_id=current_user.id, concluida=False).all()

    return render_template(
        'agenda_form.html',
        titulo='Novo Evento',
        evento=None,
        tarefas=tarefas,
        current_user=current_user,
        current_year=datetime.now().year
    )

@agenda_bp.route('/evento/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_evento(id):
    """Editar evento existente"""
    evento = Evento.query.get_or_404(id)

    if evento.usuario_id != current_user.id:
        flash('Você não tem permissão para editar este evento!', 'error')
        return redirect(url_for('agenda.index'))

    if request.method == 'POST':
        evento.titulo = request.form.get('titulo')
        evento.descricao = request.form.get('descricao')
        data_inicio_str = request.form.get('data_inicio')
        hora_inicio = request.form.get('hora_inicio', '00:00')
        data_fim_str = request.form.get('data_fim')
        hora_fim = request.form.get('hora_fim', '23:59')
        evento.tipo_recorrencia = request.form.get('tipo_recorrencia', 'nenhum')
        evento.intervalo_recorrencia = request.form.get('intervalo_recorrencia', 1, type=int)
        evento.cor = request.form.get('cor', '#3b82f6')
        evento.local = request.form.get('local')

        # Converter tarefa_id se fornecido
        tarefa_id = request.form.get('tarefa_id')
        evento.tarefa_id = tarefa_id if tarefa_id else None

        if not evento.titulo or not data_inicio_str:
            flash('Título e data de início são obrigatórios!', 'error')
            return redirect(url_for('agenda.editar_evento', id=id))

        try:
            # Converter datas
            evento.data_inicio = datetime.strptime(f"{data_inicio_str} {hora_inicio}", '%Y-%m-%d %H:%M')
            evento.data_fim = None
            if data_fim_str:
                evento.data_fim = datetime.strptime(f"{data_fim_str} {hora_fim}", '%Y-%m-%d %H:%M')

            # Processar recorrência semanal
            if evento.tipo_recorrencia == 'semanal' and request.form.get('dias_semana'):
                evento.dias_semana = ','.join(request.form.getlist('dias_semana'))
            else:
                evento.dias_semana = None

            # Data fim da recorrência
            data_fim_recorrencia_str = request.form.get('data_fim_recorrencia')
            evento.data_fim_recorrencia = None
            if data_fim_recorrencia_str:
                evento.data_fim_recorrencia = datetime.strptime(data_fim_recorrencia_str, '%Y-%m-%d')

            db.session.commit()
            flash('Evento atualizado com sucesso!', 'success')
            return redirect(url_for('agenda.index'))

        except ValueError as e:
            flash(f'Erro nos dados: {str(e)}', 'error')
            return redirect(url_for('agenda.editar_evento', id=id))

    # GET - mostrar formulário
    tarefas = Tarefa.query.filter_by(usuario_id=current_user.id, concluida=False).all()

    return render_template(
        'agenda_form.html',
        titulo='Editar Evento',
        evento=evento,
        tarefas=tarefas,
        current_user=current_user,
        current_year=datetime.now().year
    )

@agenda_bp.route('/evento/<int:id>/deletar', methods=['POST'])
@login_required
def deletar_evento(id):
    """Deletar evento"""
    evento = Evento.query.get_or_404(id)

    if evento.usuario_id != current_user.id:
        flash('Você não tem permissão para deletar este evento!', 'error')
        return redirect(url_for('agenda.index'))

    db.session.delete(evento)
    db.session.commit()

    flash('Evento deletado com sucesso!', 'success')
    return redirect(url_for('agenda.index'))

@agenda_bp.route('/api/eventos')
@login_required
def api_eventos():
    """API para obter eventos em formato JSON (para calendário)"""
    data_inicio_str = request.args.get('start')
    data_fim_str = request.args.get('end')

    if not data_inicio_str or not data_fim_str:
        return jsonify({'error': 'Parâmetros start e end são obrigatórios'}), 400

    try:
        data_inicio = datetime.fromisoformat(data_inicio_str.replace('Z', '+00:00'))
        data_fim = datetime.fromisoformat(data_fim_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Formato de data inválido'}), 400

    # Obter eventos do usuário
    eventos = Evento.query.filter_by(usuario_id=current_user.id).all()

    # Obter tarefas com prazos
    tarefas = Tarefa.query.filter(
        Tarefa.usuario_id == current_user.id,
        Tarefa.data_vencimento.isnot(None),
        Tarefa.concluida == False
    ).all()

    eventos_json = []

    # Processar eventos
    for evento in eventos:
        # Adicionar ocorrência base
        eventos_json.append({
            'id': f"evento_{evento.id}",
            'title': evento.titulo,
            'start': evento.data_inicio.isoformat(),
            'end': (evento.data_fim or evento.data_inicio).isoformat(),
            'backgroundColor': evento.cor,
            'borderColor': evento.cor,
            'textColor': '#ffffff',
            'extendedProps': {
                'tipo': 'evento',
                'descricao': evento.descricao,
                'local': evento.local,
                'recorrente': evento.eh_recorrente()
            }
        })

        # Adicionar ocorrências recorrentes
        if evento.eh_recorrente():
            ocorrencias = evento.gerar_ocorrencias(data_inicio, data_fim)
            for ocorrencia in ocorrencias:
                eventos_json.append({
                    'id': f"evento_{evento.id}_{ocorrencia['data'].isoformat()}",
                    'title': ocorrencia['titulo'],
                    'start': ocorrencia['data'].isoformat(),
                    'end': (ocorrencia['data'] + timedelta(hours=1)).isoformat(),  # duração padrão de 1h
                    'backgroundColor': ocorrencia['cor'],
                    'borderColor': ocorrencia['cor'],
                    'textColor': '#ffffff',
                    'extendedProps': {
                        'tipo': 'evento_recorrente',
                        'evento_original_id': evento.id,
                        'descricao': ocorrencia['descricao']
                    }
                })

    # Processar tarefas como eventos
    for tarefa in tarefas:
        if data_inicio <= tarefa.data_vencimento <= data_fim:
            eventos_json.append({
                'id': f"tarefa_{tarefa.id}",
                'title': f'📋 {tarefa.descricao[:30]}...' if len(tarefa.descricao) > 30 else f'📋 {tarefa.descricao}',
                'start': tarefa.data_vencimento.isoformat(),
                'end': (tarefa.data_vencimento + timedelta(hours=1)).isoformat(),
                'backgroundColor': '#f59e0b',  # amarelo para tarefas
                'borderColor': '#f59e0b',
                'textColor': '#ffffff',
                'extendedProps': {
                    'tipo': 'tarefa',
                    'prioridade': tarefa.prioridade,
                    'categoria': tarefa.categoria
                }
            })

    return jsonify(eventos_json)

def gerar_calendario_mes(ano, mes, eventos, tarefas_com_prazos):
    """Gera dados do calendário para um mês específico"""
    # Obter o primeiro dia do mês e quantos dias tem o mês
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])

    # Obter o dia da semana do primeiro dia (0 = segunda, 6 = domingo)
    dia_semana_inicio = primeiro_dia.weekday()

    # Ajustar para começar na segunda-feira (se necessário)
    if dia_semana_inicio == 6:  # domingo
        dia_semana_inicio = -1

    # Criar lista de semanas
    semanas = []
    dia_atual = primeiro_dia - timedelta(days=dia_semana_inicio + 1)

    # Gerar 6 semanas (alguns meses precisam de 6 linhas)
    for semana in range(6):
        semana_data = []
        for dia_semana in range(7):  # 7 dias da semana
            dia = dia_atual.day
            mes_dia = dia_atual.month
            ano_dia = dia_atual.year

            # Verificar se é um dia do mês atual
            eh_mes_atual = (mes_dia == mes)

            # Obter eventos/tarefas do dia
            eventos_dia = []
            tarefas_dia = []

            if eh_mes_atual:
                # Eventos do dia
                for evento in eventos:
                    if (evento.data_inicio.date() == dia_atual or
                        (evento.eh_recorrente() and dia_atual in [datetime.combine(ocorrencia['data'].date(), datetime.min.time())
                                                                 for ocorrencia in evento.gerar_ocorrencias(dia_atual, dia_atual)])):
                        eventos_dia.append(evento)

                # Tarefas do dia
                for tarefa in tarefas_com_prazos:
                    if tarefa.data_vencimento.date() == dia_atual:
                        tarefas_dia.append(tarefa)

            semana_data.append({
                'dia': dia,
                'mes': mes_dia,
                'ano': ano_dia,
                'eh_mes_atual': eh_mes_atual,
                'data_completa': dia_atual,
                'eventos': eventos_dia,
                'tarefas': tarefas_dia,
                'tem_eventos': len(eventos_dia) > 0,
                'tem_tarefas': len(tarefas_dia) > 0
            })

            dia_atual += timedelta(days=1)

        semanas.append(semana_data)

        # Parar se passou do mês atual
        if dia_atual.month != mes and dia_atual.day > 7:
            break

    return {
        'ano': ano,
        'mes': mes,
        'semanas': semanas,
        'dias_semana': ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
    }
