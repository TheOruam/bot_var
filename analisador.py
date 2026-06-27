def obter_estatisticas_time(team_id: int, league_id: int, season: int) -> Optional[Dict[str, Any]]:
    """Busca as estatísticas gerais de um time em uma liga e temporada específica."""
    if not API_FOOTBALL_KEY:
        return None
    headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': API_FOOTBALL_KEY}
    try:
        resposta = requests.get(
            f"{API_FOOTBALL_URL}/teams/statistics?team={team_id}&league={league_id}&season={season}",
            headers=headers,
            timeout=12
        )
        return resposta.json().get("response")
    except Exception as e:
        print(f"Erro ao buscar estatísticas do time {team_id}: {e}")
        return None

def obter_elenco_time(team_id: int) -> List[Dict[str, Any]]:
    """Busca a lista de jogadores (Squad) atual do time."""
    if not API_FOOTBALL_KEY:
        return []
    headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': API_FOOTBALL_KEY}
    try:
        resposta = requests.get(f"{API_FOOTBALL_URL}/players/squads?team={team_id}", headers=headers, timeout=12)
        dados = resposta.json().get("response", [])
        if dados:
            return dados[0].get("players", [])
        return []
    except Exception as e:
        print(f"Erro ao buscar elenco do time {team_id}: {e}")
        return []

def buscar_time_por_nome(nome_time: str) -> Optional[Dict[str, Any]]:
    """Busca o ID e dados de um time pelo nome (utilizado antes de renderizar o painel)."""
    if not API_FOOTBALL_KEY:
        return None
    headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': API_FOOTBALL_KEY}
    try:
        resposta = requests.get(f"{API_FOOTBALL_URL}/teams?search={nome_time}", headers=headers, timeout=12)
        dados = resposta.json().get("response", [])
        if dados:
            return dados[0]  # Retorna o primeiro time correspondente
        return None
    except Exception as e:
        print(f"Erro ao buscar time por nome: {e}")
        return None
