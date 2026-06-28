import os
import telebot
from telebot.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timezone, timedelta
import analisador

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
bot = telebot.TeleBot(TOKEN)

# Identificadores de tópicos e canais
TOPICO_PRE_JOGO = os.getenv("TOPICO_PRE_JOGO")
TOPICO_AO_VIVO = os.getenv("TOPICO_AO_VIVO")
TOPICO_RESENHA = os.getenv("TOPICO_RESENHA")
TOPICO_ADMINS = os.getenv("TOPICO_ADMINS")
CHAT_ID_GERAL = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

def obter_id_topico(message):
    if message.reply_to_message and message.reply_to_message.forum_topic_created_metadata:
        return str(message.message_thread_id)
    if hasattr(message, 'message_thread_id'):
        return str(message.message_thread_id)
    return None

def eh_admin(message):
    topico_atual = obter_id_topico(message)
    if topico_atual == TOPICO_ADMINS:
        return True
    try:
        status = bot.get_chat_member(message.chat.id, message.from_user.id).status
        return status in ["creator", "administrator"]
    except Exception:
        return False

def validar_canal_comando(message, topico_esperado, nome_sala):
    topico_atual = obter_id_topico(message)
    if topico_atual != topico_esperado:
        bot.reply_to(
            message, 
            f"❌ <b>Acesso Negado</b>\nEste comando só pode ser executado no canal/tópico de {nome_sala}.", 
            parse_mode="HTML"
        )
        return False
    return True

# ==========================================
# INTERAÇÕES DO ADMIN E DE COMUNIDADE
# ==========================================

@bot.message_handler(commands=['bomdia'])
def cmd_bomdia(message):
    if not validar_canal_comando(message, TOPICO_RESENHA, "Resenha"):
        return
    prompt = "Crie uma mensagem divertida de bom dia para o grupo de apostadores e analistas, incentivando a lucrar hoje."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(commands=['bemvindo'])
def cmd_bemvindo(message):
    if not validar_canal_comando(message, TOPICO_RESENHA, "Resenha"):
        return
    prompt = "Gere uma saudação divertida e acolhedora para um novo membro que acabou de entrar no grupo VAR do Lucro."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(commands=['green'])
def cmd_green(message):
    if not validar_canal_comando(message, TOPICO_RESENHA, "Resenha"):
        return
    prompt = "Comemore um GREEN espetacular de forma enérgica e provocativa, mantendo a seriedade analítica do VAR do Lucro."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(commands=['red'])
def cmd_red(message):
    if not validar_canal_comando(message, TOPICO_RESENHA, "Resenha"):
        return
    prompt = "Gere uma mensagem analítica e resiliente sobre um RED que aconteceu, destacando que a gestão de banca e longo prazo nos salvará."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(commands=['resenha'])
def cmd_resenha(message):
    if not validar_canal_comando(message, TOPICO_RESENHA, "Resenha"):
        return
    prompt = "Inicie um debate divertido chamando a comunidade para debater as melhores entradas do mercado para as próximas horas."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(content_types=['new_chat_members'])
def acolher_membro_automatico(message):
    thread_id = int(TOPICO_RESENHA) if TOPICO_RESENHA else None
    prompt = "Dê as boas-vindas calorosas a um novo membro no canal VAR do Lucro, sem utilizar asteriscos."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.send_message(message.chat.id, resposta, message_thread_id=thread_id, parse_mode="HTML")

# ==========================================
# CRONOGRAMA DIÁRIO (ROTEAMENTO PRE-JOGO)
# ==========================================

@bot.message_handler(commands=['cronograma'])
def cmd_cronograma(message):
    if not eh_admin(message):
        bot.reply_to(message, "Apenas administradores podem rodar este comando.")
        return
    
    bot.reply_to(message, "<i>Gerando e enviando cronograma para o canal Pré-Jogo...</i>", parse_mode="HTML")
    enviar_cronograma_diario()

def enviar_cronograma_diario():
    jogos = analisador.obter_jogos_do_dia(forcar=True)
    topico_envio = int(TOPICO_PRE_JOGO) if TOPICO_PRE_JOGO else None

    if not jogos:
        texto = "⚽ <b>VAR DO LUCRO - CRONOGRAMA DIÁRIO</b>\n\nNenhuma partida monitorada para hoje."
        bot.send_message(CHAT_ID_GERAL, texto, message_thread_id=topico_envio, parse_mode="HTML")
        return

    mensagem = ["⚽ <b>VAR DO LUCRO - CRONOGRAMA DIÁRIO</b>\n"]
    
    for j in jogos:
        try:
            dt_utc = datetime.fromisoformat(j["data_utc"].replace("Z", "+00:00"))
            dt_br = dt_utc.astimezone(timezone(timedelta(hours=-3)))
            data_formatada = dt_br.strftime("%d %b, %H:%M").upper()
        except Exception:
            data_formatada = "DATA INDEFINIDA"

        flag_m = analisador.obter_bandeira(j["mandante"])
        flag_v = analisador.obter_bandeira(j["visitante"])

        card = (
            f"  {data_formatada}\n"
            f"  {flag_m} {j['mandante']} - {flag_v} {j['visitante']}\n"
            f"  ({j['estadio']})\n"
            f"──────────────────────────"
        )
        mensagem.append(card)

    texto_final = "\n\n".join(mensagem)
    bot.send_message(CHAT_ID_GERAL, texto_final, message_thread_id=topico_envio, parse_mode="HTML")

# ==========================================
# SINAL AO VIVO (/aovivo)
# ==========================================

@bot.message_handler(commands=['aovivo'])
def cmd_aovivo(message):
    if not validar_canal_comando(message, TOPICO_AO_VIVO, "Sinais Ao Vivo"):
        return

    partes = message.text.split(maxsplit=1)
    if len(partes) < 2:
        bot.reply_to(message, "Use o formato: /aovivo NOME_DO_TIME", parse_mode="HTML")
        return

    termo = partes[1]
    msg_carregando = bot.reply_to(message, "<i>Consultando dados em tempo real...</i>", parse_mode="HTML")

    try:
        dados = analisador.consultar_dados_ao_vivo(termo)
        if not dados:
            bot.edit_message_text(
                "❌ <b>Partida Não Encontrada</b>\nNão foi identificado nenhum jogo ao vivo ocorrendo agora para o time informado.",
                chat_id=message.chat.id,
                message_id=msg_carregando.message_id,
                parse_mode="HTML"
            )
            return

        arbitro_partida = {
            "media_cartoes": 5.2,
            "media_faltas": 26.0,
            "rigor_cartao_por_falta": 0.20
        }
        
        projecoes = analisador.calcular_projecoes_secundarias(dados, arbitro_partida)

        barra_posse = analisador.gerar_barra_proporcional(dados["posse_m"], dados["posse_v"])
        barra_chutes = analisador.gerar_barra_proporcional(dados["cg_m"], dados["cg_v"])
        barra_escanteios = analisador.gerar_barra_proporcional(dados["esc_m"], dados["esc_v"])

        layout = (
            f"🏟️ <b>{dados['liga']}</b>\n"
            f"⚽ <b>{dados['mandante']} {dados['gols_m']}</b> x <b>{dados['gols_v']} {dados['visitante']}</b>\n"
            f"⏱️ Tempo: {dados['tempo']}' ({dados['status']})\n\n"
            f"📊 <b>ESTATÍSTICAS EM TEMPO REAL (FOTO 2 STYLE):</b>\n"
            f"🔵 {dados['mandante']} | 🔴 {dados['visitante']}\n\n"
            f"Posse de Bola: {dados['posse_m']}% vs {dados['posse_v']}%\n"
            f"[{barra_posse}]\n"
            f"Chutes ao Gol: {dados['cg_m']} vs {dados['cg_v']}\n"
            f"[{barra_chutes}]\n"
            f"Escanteios: {dados['esc_m']} vs {dados['esc_v']}\n"
            f"[{barra_escanteios}]\n\n"
            f"📈 <b>PROJEÇÕES MATEMÁTICAS (90 MIN):</b>\n"
            f"📐 Escanteios Projetados: <b>{projecoes['escanteios_final_projetado']}</b>\n"
            f"🟨 Cartões Projetados: <b>{projecoes['cartoes_final_projetado']}</b>\n"
            f"🏃‍♂️ Faltas Projetadas: <b>{projecoes['faltas_final_projetado']}</b>\n\n"
            f"🤖 <b>PROCESSANDO ANÁLISE DE IA...</b>"
        )

        bot.edit_message_text(
            layout,
            chat_id=message.chat.id,
            message_id=msg_carregando.message_id,
            parse_mode="HTML"
        )

        prompt_ia = (
            f"AJA COMO O ANALISTA QUANTITATIVO DO CANAL VAR DO LUCRO.\n\n"
            f"O jogo atual está aos {dados['tempo']} minutos. Placar: {dados['mandante']} {dados['gols_m']} x {dados['gols_v']} {dados['visitante']}.\n"
            f"Nossas projeções matemáticas:\n"
            f"- Escanteios finais totais projetados: {projecoes['escanteios_final_projetado']}\n"
            f"- Cartões finais totais projetados: {projecoes['cartoes_final_projetado']}\n"
            f"Gere um palpite esportivo ao vivo de alto valor (+EV) fundamentado nestas estatísticas. "
            "Defina o tamanho ideal da aposta usando o Critério de Kelly Fracionário (Kelly 1/4). "
            "Inclua o link de afiliado exatamente dessa forma: <a href='https://superbet.com'>Aproveitar Oportunidade na Superbet</a>. "
            "Nunca utilize asteriscos no texto."
        )

        analise_ia = analisador.perguntar_ao_gemini(prompt_ia)
        layout_final = layout.replace("🤖 <b>PROCESSANDO ANÁLISE DE IA...</b>", f"🤖 <b>SINAL DE MERCADOS SECUNDÁRIOS:</b>\n\n{analise_ia}")
        
        bot.send_message(
            CHAT_ID_GERAL,
            layout_final,
            message_thread_id=int(TOPICO_AO_VIVO) if TOPICO_AO_VIVO else None,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        bot.delete_message(message.chat.id, msg_carregando.message_id)

    except Exception as e:
        print(f"[ERRO AO VIVO] {str(e)}")
        bot.edit_message_text(
            "❌ <b>Erro Interno</b>\nHouve uma falha ao obter estatísticas do jogo.",
            chat_id=message.chat.id,
            message_id=msg_carregando.message_id,
            parse_mode="HTML"
        )

# ==========================================
# PAINEL DO TIME (ADMINS ONLY)
# ==========================================

@bot.message_handler(commands=['painel'])
def cmd_painel(message):
    if not validar_canal_comando(message, TOPICO_ADMINS, "Mesa dos Admins"):
        return

    partes = message.text.split(maxsplit=1)
    if len(partes) < 2:
        bot.reply_to(message, "Use o formato: /painel NOME_DO_TIME", parse_mode="HTML")
        return

    time_busca = partes[1]
    if not WEBHOOK_URL:
        bot.reply_to(message, "Configuração de painel pendente (WEBHOOK_URL vazia).")
        return

    url_painel = f"{WEBHOOK_URL}/painel?time={time_busca}"
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton(text="Abrir Painel Estatístico", web_app=WebAppInfo(url=url_painel))
    markup.add(btn)

    bot.reply_to(
        message,
        f"📊 <b>Painel Interativo do {time_busca}</b>\n\nAbra o painel interativo abaixo para ver o desempenho do time no formato avançado.",
        reply_markup=markup,
        parse_mode="HTML"
    )

# ==========================================
# RESUMO DO DIA (ROTEAMENTO PRE-JOGO)
# ==========================================

@bot.message_handler(commands=['resumo'])
def cmd_resumo(message):
    if not eh_admin(message):
        bot.reply_to(message, "Apenas administradores podem acionar o resumo do dia.")
        return

    msg_auditoria = bot.reply_to(message, "<i>Coletando resultados e enviando auditoria para o canal Pré-Jogo...</i>", parse_mode="HTML")

    try:
        jogos = analisador.obter_jogos_do_dia()
        if not jogos:
            bot.edit_message_text("Nenhum jogo cadastrado hoje.", chat_id=message.chat.id, message_id=msg_auditoria.message_id, parse_mode="HTML")
            return

        relatorio_jogos = []
        for j in jogos:
            relatorio_jogos.append(
                f"- {j['mandante']} {j['gols_mandante']} x {j['gols_visitante']} {j['visitante']} ({j['liga']})"
            )
        
        relatorio_texto = "\n".join(relatorio_jogos)

        prompt_ia = (
            f"Abaixo estão os resultados das partidas de hoje:\n{relatorio_texto}\n\n"
            "Atue como o Auditor Estatístico do VAR do Lucro. Faça um consolidado divertido "
            "e direto determinando quais partidas terminaram em GREEN (🟢) para opções de Over ou Ambas Marcam, "
            "e quais deram RED (🔴). Encerre de forma motivadora sem utilizar asteriscos."
        )

        resumo_gerado = analisador.perguntar_ao_gemini(prompt_ia)
        
        bot.send_message(
            CHAT_ID_GERAL,
            f"🏆 <b>VAR DO LUCRO - AUDITORIA DE RESULTADOS</b>\n\n{resumo_gerado}",
            message_thread_id=int(TOPICO_PRE_JOGO) if TOPICO_PRE_JOGO else None,
            parse_mode="HTML"
        )

        bot.delete_message(message.chat.id, msg_auditoria.message_id)

    except Exception as e:
        print(f"[ERRO RESUMO] {str(e)}")
        bot.edit_message_text("Erro ao realizar a auditoria dos palpites.", chat_id=message.chat.id, message_id=msg_auditoria.message_id, parse_mode="HTML")