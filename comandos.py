# comandos.py
import os
import random
import requests
from telebot import TeleBot
from analisador import buscar_jogo_ao_vivo_por_time, analisar_ao_vivo_e_formatar, obter_jogos_do_dia, gerar_relatorio_pre_jogo, obter_cliente_gemini

# Captura os IDs das salas do ambiente (padrão 0 caso não configurados)
ID_PRE_JOGO = int(os.getenv("TOPICO_PRE_JOGO", "0"))
ID_AO_VIVO = int(os.getenv("TOPICO_AO_VIVO", "0"))
ID_RESENHA = int(os.getenv("TOPICO_RESENHA", "0"))
ID_ADMINS = int(os.getenv("TOPICO_ADMINS", "0"))

def eh_admin(bot: TeleBot, message) -> bool:
    """Verifica se o remetente é administrador do grupo."""
    if message.chat.type == "private":
        return True
    try:
        status_membro = bot.get_chat_member(message.chat.id, message.from_user.id).status
        return status_membro in ["administrator", "creator"]
    except Exception as e:
        print(f"Erro ao verificar permissões de admin: {e}")
        return False

def verificar_sala(message, id_sala_permitida: int) -> bool:
    """
    Compara o ID do tópico de onde veio a mensagem com o ID da sala permitida.
    Permite a execução em chats privados para facilitar testes.
    """
    if message.chat.type == "private":
        return True
    
    # Pega o ID do tópico (se for None, define como 0)
    thread_id = message.message_thread_id
    if thread_id is None:
        thread_id = 0
        
    return int(thread_id) == id_sala_permitida

def registrar_comandos(bot: TeleBot):
    """Registra todos os comandos e faz a triagem das salas de destino."""

    @bot.message_handler(commands=['start', 'ajuda'])
    def enviar_ajuda(message):
        texto = (
            "💎 Central de Inteligência Esportiva 💎\n\n"
            "Cada comando possui sua sala específica:\n"
            "• Use o comando /prejogo somente na sala Pré-Jogo.\n"
            "• Use o comando /aovivo somente na sala de Sinais Ao Vivo."
        )
        bot.reply_to(message, texto)

    # =====================================================================
    # COMANDO: PRÉ-JOGO (APENAS NA SALA PRÉ-JOGO)
    # =====================================================================
    @bot.message_handler(commands=['prejogo'])
    def comando_pre_jogo(message):
        # Filtro de sala
        if not verificar_sala(message, ID_PRE_JOGO):
            bot.reply_to(message, "⚠️ Este comando so pode ser utilizado na sala Pré-Jogo.")
            return

        args = message.text.replace('/prejogo', '').strip()
        if not args:
            bot.reply_to(message, "⚠️ Digite o nome do time. Exemplo: /prejogo Flamengo")
            return
            
        bot.reply_to(message, f"🔍 Buscando cronograma de hoje para '{args}'...")
        jogos_hoje = obter_jogos_do_dia()
        jogo_encontrado = None
        args_min = args.lower().strip()
        
        for jogo in jogos_hoje:
            casa = jogo["teams"]["home"]["name"].lower()
            fora = jogo["teams"]["away"]["name"].lower()
            if args_min in casa or args_min in fora:
                jogo_encontrado = jogo
                break
                
        if not jogo_encontrado:
            bot.send_message(message.chat.id, f"❌ Não encontrei nenhuma partida para hoje com o nome '{args}'.")
            return
            
        bot.send_message(message.chat.id, "🧠 Gerando Relatório de Inteligência VAR do Lucro...")
        relatorio = gerar_relatorio_pre_jogo(jogo_encontrado)
        bot.send_message(message.chat.id, relatorio)

    # =====================================================================
    # COMANDO: AO VIVO (APENAS NA SALA SINAIS AO VIVO)
    # =====================================================================
    @bot.message_handler(commands=['aovivo'])
    def comando_ao_vivo(message):
        # Filtro de sala
        if not verificar_sala(message, ID_AO_VIVO):
            bot.reply_to(message, "⚠️ Este comando so pode ser utilizado na sala de Sinais Ao Vivo.")
            return

        args = message.text.replace('/aovivo', '').strip()
        if not args:
            bot.reply_to(message, "⚠️ Digite o nome do time. Exemplo: /aovivo Real Madrid")
            return
        
        bot.reply_to(message, f"🔍 Procurando partida ao vivo para '{args}'...")
        dados_jogo = buscar_jogo_ao_vivo_por_time(args)
        
        if not dados_jogo:
            bot.send_message(message.chat.id, f"❌ Nenhuma partida ao vivo encontrada para '{args}' no momento.")
            return
            
        bot.send_message(message.chat.id, "📊 Partida encontrada! Calculando probabilidades e notícias...")
        analise_final = analisar_ao_vivo_e_formatar(dados_jogo)
        bot.send_message(message.chat.id, analise_final)

    # =====================================================================
    # COMANDOS DE ADMINS - GRUPO 1: APENAS NA "MESA DOS ADMINS"
    # =====================================================================
    @bot.message_handler(commands=['update', 'addliga', 'remliga', 'verligas', 'ids'])
    def comandos_criticos_admin(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return

        if not verificar_sala(message, ID_ADMINS):
            bot.reply_to(message, "⚠️ Este comando de configuração só é aceito dentro da sala Mesa dos Admins.")
            return

        comando = message.text.split()[0].replace('/', '').strip().lower()

        if comando == 'update':
            bot.send_message(message.chat.id, "Iniciando auto-diagnostico dos sistemas...")
            status_gemini = "OK"
            status_api_football = "OK"
            
            chave_gemini = os.getenv("GEMINI_API_KEY")
            chave_football = os.getenv("API_FOOTBALL_KEY")
            
            try:
                client = obter_cliente_gemini()
                client.models.generate_content(model='gemini-2.5-flash', contents="ping")
            except Exception as e:
                status_gemini = f"FALHA ({e})"
                
            try:
                headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': chave_football}
                res = requests.get("https://v3.football.api-sports.io/status", headers=headers, timeout=5)
                if res.status_code != 200:
                    status_api_football = f"FALHA (Status HTTP {res.status_code})"
            except Exception as e:
                status_api_football = f"FALHA ({e})"
                
            relatorio_update = (
                "DIAGNOSTICO DE SISTEMA COMPLETO\n\n"
                f"Variavel GEMINI KEY: {'Configurada' if chave_gemini else 'AUSENTE'}\n"
                f"Variavel FOOTBALL KEY: {'Configurada' if chave_football else 'AUSENTE'}\n\n"
                f"Conexao Google Gemini IA: {status_gemini}\n"
                f"Conexao API-Football: {status_api_football}\n\n"
                "Se todos os itens estiverem OK, seu bot esta operando em perfeito estado na nuvem."
            )
            bot.send_message(message.chat.id, relatorio_update)

        elif comando == 'addliga':
            try:
                id_liga = int(message.text.split()[1])
                from analisador import adicionar_liga_monitorada
                if adicionar_liga_monitorada(id_liga):
                    bot.reply_to(message, f"Sucesso! A liga ID {id_liga} foi adicionada ao monitoramento.")
                else:
                    bot.reply_to(message, f"A liga ID {id_liga} ja estava no monitoramento.")
            except Exception:
                bot.reply_to(message, "⚠️ Use: /addliga <numero_id>")

        elif comando == 'remliga':
            try:
                id_liga = int(message.text.split()[1])
                from analisador import remover_liga_monitorada
                if remover_liga_monitorada(id_liga):
                    bot.reply_to(message, f"Sucesso! A liga ID {id_liga} foi removida.")
                else:
                    bot.reply_to(message, f"A liga ID {id_liga} nao foi encontrada.")
            except Exception:
                bot.reply_to(message, "⚠️ Use: /remliga <numero_id>")

        elif comando == 'verligas':
            from analisador import listar_ligas_monitoradas
            bot.send_message(message.chat.id, f"LIGAS ATIVAS NO MONITORAMENTO DO VAR:\n\nIDs Monitorados: {listar_ligas_monitoradas()}")

        elif comando == 'ids':
            try:
                arg_busca = message.text.replace('/ids', '').strip()
                if not arg_busca:
                    bot.reply_to(message, "Para buscar IDs de ligas use: /ids <nome_ou_pais>\nTabela completa: https://dashboard.api-sports.io/football/ids", disable_web_page_preview=True)
                else:
                    from analisador import buscar_ids_ligas
                    res = buscar_ids_ligas(arg_busca)
                    if not res:
                        bot.send_message(message.chat.id, "Nenhuma liga encontrada.")
                    else:
                        linhas = [f"• ID: {r['id']} | {r['nome']} ({r['pais']})" for r in res[:15]]
                        bot.send_message(message.chat.id, "RESULTADO DA BUSCA DE LIGAS:\n\n" + "\n".join(linhas))
            except Exception as e:
                bot.reply_to(message, f"Erro ao buscar IDs: {e}")


    # =====================================================================
    # COMANDOS DE ADMINS - GRUPO 2: PERMITIDOS EM QUALQUER UMA DAS 4 SALAS
    # =====================================================================
    @bot.message_handler(commands=['bemvindo', 'bomdia', 'green', 'red', 'resenha'])
    def comandos_interacao_admin(message):
        # 1. Verifica se o usuário é administrador
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return

        # 2. Garante que o comando foi digitado em uma das 4 salas conhecidas do fórum
        thread_id = message.message_thread_id
        if thread_id is not None:
            thread_id = int(thread_id)
            if thread_id not in [ID_PRE_JOGO, ID_AO_VIVO, ID_RESENHA, ID_ADMINS]:
                bot.reply_to(message, "⚠️ Comandos administrativos nao sao permitidos nesta sala do forum.")
                return

        comando = message.text.split()[0].replace('/', '').strip().lower()

        if comando == 'bemvindo':
            bot.send_message(message.chat.id, (
                "Atencao cabine do VAR! Temos um novo integrante na mesa de operacoes!\n\n"
                "Analisando o perfil do novato em nossa tela de transmissao...\n"
                "Checando dados... Verificando batimentos cardiacos... Analisando a carteira...\n\n"
                "DECISAO CONFIRMADA NO MONITOR:\n"
                "Cadastro aprovado com sucesso! Seja muito bem-vindo ao VAR do Lucro!\n"
                "Prepare sua planilha, ajuste sua stake e junte-se aos operadores profissionais de elite."
            ))

        elif comando == 'bomdia':
            bot.send_message(message.chat.id, (
                "Bom dia, mercado! Os monitores ja estao ligados e as APIs aquecidas!\n\n"
                "Hoje o dia promete muitas oportunidades na nossa mesa de analise. "
                "Lembre-se das regras de ouro para hoje:\n"
                "1. Proteja seu capital (stake controlada).\n"
                "2. Estude os relatorios antes de clicar.\n"
                "3. Mantenha a calma de um monge, ganhando ou perdendo.\n\n"
                "Que o valor esperado positivo esteja conosco. Bons investimentos a todos!"
            ))

        elif comando == 'green':
            bot.send_message(message.chat.id, (
                "EXPLODIU O GREEN DA NOSSA ANALISE!\n\n"
                "A analise cirurgica do nosso relatorio bateu exatamente com o andamento do jogo!\n"
                "Quem seguiu a gestao de banca e entrou na recomendacao do VAR do Lucro acabou de colocar dinheiro no bolso!\n"
                "O mercado tentou segurar, mas a nossa leitura tecnica foi implacavel.\n"
                "Parabens aos lucros coletados! Comemore sem perder o foco na proxima operacao."
            ))

        elif comando == 'red':
            bot.send_message(message.chat.id, (
                "Atenção operadores: Red detectado.\n\n"
                "O futebol tem variaveis imprevisiveis que nenhuma estatistica consegue blindar 100 por cento.\n"
                "Mas e aqui que se separam os amadores dos profissionais:\n"
                "Seguir estritamente a nossa stake de 1 a 3 por cento garante que esse tropeço nao afete sua saude financeira.\n"
                "Nao tente recuperar o valor perdido imediatamente com apostas desesperadas sem estudo.\n"
                "Mantenha o controle emocional. A longo prazo, a consistencia matematica sempre vence."
            ))

        elif comando == 'resenha':
            curiosidades = [
                "Voce sabia que em 1998, um raio atingiu o gramado durante um jogo no Congo e matou todos os 11 jogadores de um time, enquanto o outro time saiu completamente ileso? Bizarro demais!",
                "Na Inglaterra, o jogador Lee Todd levou o cartao vermelho mais rapido da historia: apenas 2 segundos de jogo! Ao ouvir o apito inicial do juiz perto do seu ouvido, ele exclamou: Caramba, isso foi muito alto! E foi expulso.",
                "Em 1945, um jogo entre Arsenal e Dynamo de Moscou ocorreu sob uma névoa tao densa que ninguem enxergava nada. O Dynamo fez substituicoes sem ninguem perceber e acabou jogando com 15 jogadores em campo por quase meia hora!"
            ]
            bot.send_message(message.chat.id, "CURIOSIDADE DO VAR DO LUCRO\n\n" + random.choice(curiosidades))

    # =====================================================================
    # MONITORAMENTO AUTOMÁTICO DE NOVOS MEMBROS (ENVIO NA SALA RESENHA)
    # =====================================================================
    @bot.message_handler(content_types=['new_chat_members'])
    def boas_vindas_automatico(message):
        """
        Detecta automaticamente a entrada de novos usuários no grupo 
        e envia a mensagem de acolhimento do VAR na sala de Resenha.
        """
        if not ID_RESENHA:
            return

        texto_boas_vindas = (
            "Atencao cabine do VAR! Temos um novo integrante na mesa de operacoes!\n\n"
            "Analisando o perfil do novato em nossa tela de transmissao...\n"
            "Checando dados... Verificando batimentos cardiacos... Analisando a carteira...\n\n"
            "DECISAO CONFIRMADA NO MONITOR:\n"
            "Cadastro aprovado com sucesso! Seja muito bem-vindo ao VAR do Lucro!\n"
            "Prepare sua planilha, ajuste sua stake e junte-se aos operadores profissionais de elite."
        )

        try:
            bot.send_message(
                chat_id=message.chat.id,
                text=texto_boas_vindas,
                message_thread_id=ID_RESENHA
            )
        except Exception as e:
            print(f"Erro ao processar as boas-vindas automatizadas: {e}")
