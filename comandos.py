elif comando == 'painel':
            nome_time = message.text.replace('/painel', '').strip()
            if not nome_time:
                bot.reply_to(message, "⚠️ Use o comando digitando o nome do time. Exemplo: /painel Flamengo")
                return
                
            bot.reply_to(message, f"🔍 Pesquisando dados e montando o painel de analise para '{nome_time}'...")
            
            from analisador import buscar_ids_ligas, traduzir_busca_para_ingles
            nome_time_en = traduzir_busca_para_ingles(nome_time)
            
            # 1. Pesquisa o time na API de Futebol para descobrir o ID correto
            headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': os.getenv("API_FOOTBALL_KEY")}
            try:
                res_busca = requests.get(f"https://v3.football.api-sports.io/teams?search={nome_time_en}", headers=headers, timeout=12)
                times_encontrados = res_busca.json().get("response", [])
                
                if not times_encontrados:
                    bot.send_message(message.chat.id, f"❌ Nao encontrei nenhum time com o nome '{nome_time}'.")
                    return
                    
                time_id = times_encontrados[0]["team"]["id"]
                time_nome = times_encontrados[0]["team"]["name"]
                
                # 2. Gera a URL do Mini App do Telegram baseada no seu Render
                # Você pode mudar o 'league_id=71' e 'season=2024' se quiser outras ligas/anos por padrão
                url_web_app = f"{os.getenv('WEBHOOK_URL')}/painel_time?team_id={time_id}&league_id=71&season=2024"
                
                # 3. Cria o botão de abertura de janela (Web App) do Telegram
                teclado = telebot.types.InlineKeyboardMarkup()
                botao_painel = telebot.types.InlineKeyboardButton(
                    text=f"📊 Ver Estatisticas do {time_nome}",
                    web_app=telebot.types.WebAppInfo(url=url_web_app)
                )
                teclado.add(botao_painel)
                
                bot.send_message(
                    chat_id=message.chat.id,
                    text=f"💎 Painel estatistico pronto para o {time_nome}!",
                    reply_markup=teclado,
                    message_thread_id=message.message_thread_id
                )
            except Exception as e:
                bot.reply_to(message, f"Erro ao construir painel: {e}")
