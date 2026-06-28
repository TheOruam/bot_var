# main.py
import os
import time
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template_string, request
import telebot
from comandos import registrar_comandos
from analisador import verificar_e_enviar_pre_jogos, verificar_e_enviar_cronograma, obter_estatisticas_time, obter_elenco_time

app = Flask(__name__)

# Template HTML e CSS moderno atualizado com suporte a Alerta de Partida de Hoje
HTML_TEMPLATE_PAINEL = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estatísticas do Time</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f6f8;
            color: #333;
            margin: 0;
            padding: 10px;
        }
        .container {
            background-color: #fff;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            max-width: 500px;
            margin: 0 auto;
        }
        .header {
            display: flex;
            align-items: center;
            border-bottom: 2px solid #00c2cb;
            padding-bottom: 12px;
            margin-bottom: 12px;
        }
        .header img {
            width: 50px;
            height: 50px;
            margin-right: 12px;
        }
        .header-title h2 {
            margin: 0;
            font-size: 1.2rem;
            color: #1a1a1a;
        }
        .header-title p {
            margin: 2px 0 0 0;
            font-size: 0.85rem;
            color: #777;
        }
        .match-today-card {
            background: linear-gradient(135deg, #00c2cb, #008f96);
            color: #fff;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 15px;
            text-align: center;
            box-shadow: 0 4px 8px rgba(0, 194, 203, 0.15);
        }
        .match-today-card .title {
            font-size: 0.7rem;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }
        .match-today-card .versus {
            font-size: 0.95rem;
            font-weight: bold;
        }
        .match-today-card .info {
            font-size: 0.75rem;
            margin-top: 4px;
            opacity: 0.9;
        }
        .tabs {
            display: flex;
            background-color: #eaecef;
            border-radius: 8px;
            margin-bottom: 15px;
            overflow: hidden;
        }
        .tab {
            flex: 1;
            text-align: center;
            padding: 10px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            background-color: #eaecef;
            border: none;
            color: #666;
            outline: none;
        }
        .tab.active {
            background-color: #00c2cb;
            color: #fff;
        }
        .content {
            display: none;
        }
        .content.active {
            display: block;
        }
        .grid-circles {
            display: flex;
            justify-content: space-around;
            margin-bottom: 20px;
        }
        .circle-stat {
            text-align: center;
        }
        .circle {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 4px solid #00c2cb;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.95rem;
            margin-bottom: 5px;
        }
        .bar-container {
            margin-bottom: 12px;
        }
        .bar-label {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .bar-bg {
            background-color: #eaecef;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            display: flex;
        }
        .bar-fill-home {
            background-color: #00c2cb;
            height: 100%;
        }
        .bar-fill-away {
            background-color: #ffb703;
            height: 100%;
        }
        .player-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #eee;
            padding: 8px 0;
            font-size: 0.9rem;
        }
        .player-position {
            font-size: 0.75rem;
            background-color: #00c2cb;
            color: #fff;
            padding: 2px 6px;
            border-radius: 4px;
        }
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <img src="{{ time_logo }}" alt="Logo">
        <div class="header-title">
            <h2>{{ time_nome }}</h2>
            <p>{{ pais }} | Estatísticas da Liga</p>
        </div>
    </div>

    <!-- ALERTA DINÂMICO DE JOGO DE HOJE -->
    {% if jogo_hoje %}
    <div class="match-today-card">
        <div class="title">🔥 Tem Jogo de Hoje!</div>
        <div class="versus">⚽ {{ jogo_hoje_casa }} v {{ jogo_hoje_fora }}</div>
        <div class="info">🕒 Horário: {{ jogo_hoje_hora }} (BRT) | 🏟️ {{ jogo_hoje_estadio }}</div>
    </div>
    {% endif %}

    <div class="tabs">
        <button class="tab active" onclick="switchTab('stats')">STATISTICS</button>
        <button class="tab" onclick="switchTab('squads')">SQUADS</button>
    </div>

    <!-- ABA ESTATÍSTICAS -->
    <div id="stats" class="content active">
        <div class="grid-circles">
            <div class="circle-stat">
                <div class="circle">{{ vitorias_percent }}%</div>
                <div style="font-size:0.75rem; color:#777;">Wins</div>
            </div>
            <div class="circle-stat">
                <div class="circle">{{ clean_sheets }}</div>
                <div style="font-size:0.75rem; color:#777;">Clean Sheets</div>
            </div>
            <div class="circle-stat">
                <div class="circle">{{ gols_feitos }}</div>
                <div style="font-size:0.75rem; color:#777;">Gols Feitos</div>
            </div>
        </div>

        <div class="bar-container">
            <div class="bar-label">
                <span>Casa ({{ vit_casa }})</span>
                <span>Vitorias Totais: {{ total_vitorias }}</span>
                <span>Fora ({{ vit_fora }})</span>
            </div>
            <div class="bar-bg">
                <div class="bar-fill-home" style="width: {{ home_percent }}%"></div>
                <div class="bar-fill-away" style="width: {{ away_percent }}%"></div>
            </div>
        </div>

        <div class="bar-container">
            <div class="bar-label">
                <span>Casa ({{ gols_casa }})</span>
                <span>Gols Feitos: {{ total_gols }}</span>
                <span>Fora ({{ gols_fora }})</span>
            </div>
            <div class="bar-bg">
                <div class="bar-fill-home" style="width: {{ home_gols_percent }}%"></div>
                <div class="bar-fill-away" style="width: {{ away_gols_percent }}%"></div>
            </div>
        </div>
    </div>

    <!-- ABA ELENCO -->
    <div id="squads" class="content">
        {% for p in elenco %}
        <div class="player-row">
            <span>{{ p.name }}</span>
            <span class="player-position">{{ p.position }}</span>
        </div>
        {% endfor %}
    </div>
</div>

<script>
    function switchTab(tabId) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
        event.currentTarget.classList.add('active');
        document.getElementById(tabId).classList.add('active');
    }
</script>

</body>
</html>
"""

@app.route('/')
def home():
    return "Bot Online e Operando com Sucesso!", 200

@app.route('/painel_time')
def painel_time():
    """Rota que alimenta e desenha as estatísticas visuais do time, com detector de jogo hoje."""
    team_id = request.args.get('team_id', type=int)
    league_id = request.args.get('league_id', default=71, type=int)
    season = request.args.get('season', default=2024, type=int)
    
    if not team_id:
        return "Erro: Parâmetro team_id em falta.", 400
        
    stats = obter_estatisticas_time(team_id, league_id, season)
    elenco = obter_elenco_time(team_id)
    
    # Processamento de jogo hoje (Global para qualquer time)
    from analisador import obter_jogos_do_dia
    jogos_hoje = obter_jogos_do_dia()
    jogo_hoje_dados = None
    
    for jogo in jogos_hoje:
        id_casa = jogo["teams"]["home"]["id"]
        id_fora = jogo["teams"]["away"]["id"]
        
        if id_casa == team_id or id_fora == team_id:
            # Converte a hora UTC do jogo de hoje para o Horário de Brasília
            data_utc_str = jogo["fixture"]["date"]
            data_utc = datetime.fromisoformat(data_utc_str.replace("Z", "+00:00"))
            data_brt = data_utc - timedelta(hours=3)
            hora_formatada = data_brt.strftime('%H:%M')
            
            jogo_hoje_dados = {
                "casa": jogo["teams"]["home"]["name"],
                "fora": jogo["teams"]["away"]["name"],
                "hora": hora_formatada,
                "estadio": jogo["fixture"]["venue"]["name"] if jogo["fixture"]["venue"]["name"] else "Sem estádio definido"
            }
            break

    # Lógica Resiliente de Campanha: Se o time for de outra liga e der None nas stats,
    # o painel não "crasha", ele apenas preenche como N/A e exibe o elenco (SQUADS) perfeitamente!
    if not stats:
        return render_template_string(
            HTML_TEMPLATE_PAINEL,
            time_nome="Estatísticas Indisponíveis",
            time_logo="https://cdn-icons-png.flaticon.com/512/53/53283.png",
            pais="Internacional",
            fundacao="N/A",
            vitorias_percent="0",
            clean_sheets="N/A",
            gols_feitos="N/A",
            total_vitorias="N/A",
            vit_casa="0", vit_fora="0",
            home_percent="50", away_percent="50",
            total_gols="0", gols_casa="0", gols_fora="0",
            home_gols_percent="50", away_gols_percent="50",
            elenco=elenco[:15] if elenco else [],
            jogo_hoje=jogo_hoje_dados is not None,
            jogo_hoje_casa=jogo_hoje_dados["casa"] if jogo_hoje_dados else "",
            jogo_hoje_fora=jogo_hoje_dados["fora"] if jogo_hoje_dados else "",
            jogo_hoje_hora=jogo_hoje_dados["hora"] if jogo_hoje_dados else "",
            jogo_hoje_estadio=jogo_hoje_dados["estadio"] if jogo_hoje_dados else ""
        )
        
    nome = stats["team"]["name"]
    logo = stats["team"]["logo"]
    played = stats["fixtures"]["played"]["total"] or 1
    wins_total = stats["fixtures"]["wins"]["total"] or 0
    clean_sheets = stats["clean_sheet"]["total"] or 0
    gols_total = stats["goals"]["for"]["total"]["total"] or 0
    
    vit_casa = stats["fixtures"]["wins"]["home"] or 0
    vit_fora = stats["fixtures"]["wins"]["away"] or 0
    
    vitorias_percent = round((wins_total / played) * 100, 1)
    home_percent = round((vit_casa / (wins_total or 1)) * 100, 1)
    away_percent = 100 - home_percent
    
    gols_casa = stats["goals"]["for"]["total"]["home"] or 0
    gols_fora = stats["goals"]["for"]["total"]["away"] or 0
    home_gols_percent = round((gols_casa / (gols_total or 1)) * 100, 1)
    away_gols_percent = 100 - home_gols_percent

    return render_template_string(
        HTML_TEMPLATE_PAINEL,
        time_nome=nome,
        time_logo=logo,
        pais=stats["league"]["country"],
        fundacao="2003",
        vitorias_percent=vitorias_percent,
        clean_sheets=clean_sheets,
        gols_feitos=gols_total,
        total_vitorias=wins_total,
        vit_casa=vit_casa,
        vit_fora=vit_fora,
        home_percent=home_percent,
        away_percent=away_percent,
        total_gols=gols_total,
        gols_casa=gols_casa,
        gols_fora=gols_fora,
        home_gols_percent=home_gols_percent,
        away_gols_percent=away_gols_percent,
        elenco=elenco[:15],
        # Variáveis dinâmicas para o card de jogo de hoje
        jogo_hoje=jogo_hoje_dados is not None,
        jogo_hoje_casa=jogo_hoje_dados["casa"] if jogo_hoje_dados else "",
        jogo_hoje_fora=jogo_hoje_dados["fora"] if jogo_hoje_dados else "",
        jogo_hoje_hora=jogo_hoje_dados["hora"] if jogo_hoje_dados else "",
        jogo_hoje_estadio=jogo_hoje_dados["estadio"] if jogo_hoje_dados else ""
    )

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("A variável de ambiente 'TELEGRAM_TOKEN' não está configurada.")

bot = telebot.TeleBot(TOKEN)
registrar_comandos(bot)

# ==========================================
# AGENDADOR AUTOMÁTICO (PRÉ-JOGO E CRONOGRAMAS)
# ==========================================

def tarefa_agendada_loop():
    # Aguarda 30 segundos ao iniciar para estabilizar as conexões de rede
    time.sleep(30)
    while True:
        try:
            verificar_e_enviar_cronograma(bot)
            verificar_e_enviar_pre_jogos(bot)
        except Exception as e:
            print(f"Erro no loop do agendador automático: {e}")
        time.sleep(600)  # Aguarda 10 minutos para a próxima varredura

def rodar_servidor_web():
    porta = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)

if __name__ == "__main__":
    # 1. Inicia o agendador de segundo plano (Thread)
    thread_agendador = threading.Thread(target=tarefa_agendada_loop, daemon=True)
    thread_agendador.start()
    print("Agendador automático iniciado com sucesso.")

    # 2. Inicia o Polling do Telegram em segundo plano (Thread)
    # Isso evita que o polling pesado bloqueie o fluxo principal do Flask
    thread_bot = threading.Thread(target=lambda: bot.infinity_polling(), daemon=True)
    thread_bot.start()
    print("Escuta do Bot do Telegram iniciada em segundo plano.")

    # 3. RODA O SERVIDOR WEB FLASK NO FLUXO PRINCIPAL (Main Thread)
    # Garante a conexão instantânea à porta do Render no início da execução
    print("Iniciando Servidor Web Flask...")
    rodar_servidor_web()