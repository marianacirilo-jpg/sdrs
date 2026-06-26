#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrige acentos de mensagens WhatsApp geradas em ASCII.
Substituicao palavra-a-palavra com limites (\b) para seguranca.
Uso: python3 fix_accents.py <arquivo_msg.txt>  (sobrescreve)
"""
import re, sys, os

# Dicionario palavra -> forma acentuada (PT-BR)
REPL = {
    # pronomes/frequentes
    "voce": "você", "nao": "não", "estao": "estão", "tambem": "também",
    "ja": "já", "so": "só", "ate": "até", "apos": "após", "apos": "após",
    "aquela": "aquela", "desse": "desse",
    # template fixo
    "diagnostico": "diagnóstico", "digitalizacao": "digitalização",
    "pratica": "prática", "operacao": "operação", "gestao": "gestão",
    # sufixos -cao -> -ção
    "organizacao": "organização", "integracao": "integração",
    "automacao": "automação", "renovacao": "renovação",
    "contratacao": "contratação", "expansao": "expansão",
    "distribuicao": "distribuição", "comercializacao": "comercialização",
    "comunicacao": "comunicação", "informacao": "informação",
    "atencao": "atenção", "opcao": "opção", "funcao": "função",
    "solucao": "solução", "decisao": "decisão", "visao": "visão",
    "relacao": "relação", "recompra": "recompra", "conexao": "conexão",
    "recepcao": "recepção", "producao": "produção", "reducao": "redução",
    "selecao": "seleção", "configuracao": "configuração",
    "cotacao": "cotação", "orcamento": "orçamento",
    "profissionalizacao": "profissionalização", "reposicao": "reposição",
    "comissao": "comissão", "visao": "visão", "temporada": "temporada",
    "colecao": "coleção", "secao": "seção", "avaliacao": "avaliação",
    "atualizacao": "atualização", "confirmacao": "confirmação",
    "negociacao": "negociação",
    "balcao": "balcão", "formulacao": "formulação",
    "recuperacao": "recuperação", "conservacao": "conservação",
    "limpeza": "limpeza", "manutencao": "manutenção",
    "instalacao": "instalação", "instalacoes": "instalações",
    "salao": "salão", "saloes": "salões", "cao": "cão",
    "industrias": "indústrias", "voces": "vocês",
    "acessorios": "acessórios", "acessorio": "acessório",
    "consumiveis": "consumíveis", "consumivel": "consumível",
    "cosmeticos": "cosméticos", "cosmetico": "cosmético",
    "moveis": "móveis", "movel": "móvel",
    "telemoveis": "telemóveis",
    "tecnico": "técnico", "tecnicos": "técnicos",
    "tecnica": "técnica", "tecnicas": "técnicas",
    "comercial": "comercial", "comerciais": "comerciais",
    "escritorios": "escritórios", "escritorio": "escritório",
    "regiao": "região", "regioes": "regiões",
    "hoteis": "hotéis", "hotel": "hotel",
    "sinalizacao": "sinalização", "comunicacao": "comunicação",
    "fabrica": "fábrica", "fabricas": "fábricas",
    "plasticos": "plásticos", "plastico": "plástico",
    "fisica": "física", "fisico": "físico",
    "restricao": "restrição", "restricoes": "restrições",
    "aprovacao": "aprovação", "pedido": "pedido",
    "expansao": "expansão", "avaliacao": "avaliação",
    "suporte": "suporte", "configuracoes": "configurações",
    # -ario, -orio
    "funcionario": "funcionário", "inventario": "inventário",
    "horario": "horário", "necessario": "necessário", "obrigatorio": "obrigatório",
    # nomes
    "joao": "João", "antonio": "Antônio", "jose": "José", "andre": "André",
    # adjetivos comuns
    "proprio": "próprio", "rapida": "rápida", "rapido": "rápido",
    "facil": "fácil", "faceis": "fáceis", "agil": "ágil",
    "unico": "único", "unica": "única", "media": "média", "medio": "médio",
    "ultimos": "últimos", "ultima": "última", "primeira": "primeira",
    "terceiro": "terceiro",
    # catálogo, automático, etc
    "catalogo": "catálogo", "catalogos": "catálogos",
    "automatico": "automático", "automatica": "automática",
    "estrategico": "estratégico", "estrategica": "estratégica",
    "analise": "análise", "analises": "análises",
    "estrangeiro": "estrangeiro",
    # saude, pegada
    "saude": "saúde",
    # farmácia, academia
    "farmacias": "farmácias", "farmacia": "farmácia",
    "academias": "academias",
    # area, era -> cuidado (era verbo!). nao tocar "era"
    "area": "área", "areas": "áreas",
    # assim, mas
    # "muda" etc - nao
    # historico
    "historico": "histórico", "historica": "histórica",
    # categoria
    "categoria": "categoria",
    "industria": "indústria", "comercio": "comércio",
    "irrigacao": "irrigação", "agricola": "agrícola",
    "agricolas": "agrícolas", "irrigacao": "irrigação",
    "producao": "produção", "fabricacao": "fabricação",
    "industrial": "industrial", "industriais": "industriais",
    "comerciais": "comerciais",
    # dia, noite - cuidado com "dia" (muito comum em outros contextos, mas aqui ok)
    # o template usa "segunda-feira"
    # itens -> ok
    "item": "item", "itens": "itens",
    # "e a Mariana" -> "é a Mariana" (frase, fazer antes)
    # depois: "e" sozinho -> "é" só no contexto "Aqui e a"
}

def fix(text):
    # frase fixa primeiro
    text = text.replace("Aqui e a Mariana", "Aqui é a Mariana")
    text = text.replace("da pra", "dá pra")
    # palavra-a-palavra (case-insensitive, mantem case simples)
    for k, v in REPL.items():
        # \b com re.IGNORECASE; substitui preservando se era titulo
        text = re.sub(r"\b" + re.escape(k) + r"\b", v, text, flags=re.IGNORECASE)
    return text

if __name__ == "__main__":
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        orig = f.read()
    novo = fix(orig)
    with open(path, "w", encoding="utf-8") as f:
        f.write(novo)
    changed = orig != novo
    print(("OK (alterado) " if changed else "OK (sem mudanca) ") + path)
