"""
Modulo: Dizionario di espressioni regolari
"""

import re

REGOLE_FISSE = {
    # su satispay la causale di ricarica è "ricarica budget" mentre sulla banca di prelievo è "satispay"
    r"satispay|ricarica budget|ricarica(?!\s+telefonica)|giroconto|dalla banca|verso la banca|risparmi|investimento|\[giroconto\]": "Giroconto",

    r"stipendio|emolumenti|accredito bonifico da|compenso|premio|paghetta|rimborso|\bmese\b": "Entrate & Rimborsi",
    r"conad|esselunga|carrefour|coop|lidl|pam|penny|bennet|gigante|eurospin|md\b|crai|despar|in's|aldi": "Spesa",
    r"affitto|condominio|luce|gas|enel|iren|a2a|sorgenia|edison|hera|vodafone|tim\b|telecom|iliad|windtre|fastweb": "Utenze & Casa",
    r"q8|eni\b|ip\b|tamoil|agip|autostrade|telepass|uber|free now|trenitalia|italo|ryanair|easyjet|tap & go|sostapp|parcometro|gtt": "Trasporti & Carburante",
    r"ristorante|trattoria|pizzeria|osteria|mcdonald|burger king|kfc|starbucks|bar\b|bistrot|caff|panino|bakery|trapizzino|"
    r"gelat|chiosco|rifugio|panche|deliveroo|glovo|just eat|nyx|pummar|skassa|evolution|to11": "Ristorazione",
    r"netflix|spotify|disney|prime video|dazn|youtube premium|apple services|apple\.com/bill|icloud|google storage|google one|dropbox|chatgpt|openai": "Abbonamenti & Servizi Digitali",
    r"amazon|aliexpress|temu|zalando|shein|zara|h&m|pull\s*&\s*bear|bershka|stradivarius|ovs|primark|unieuro|mediaworld": "Shopping",
    r"decathlon|calcetto|palestra|cinema|teatro|libr|feltrinelli|mondadori|steam|playstation|psn|nintendo|xbox": "Svago e Tempo Libero",
    r"farmacia|ospedale|visita medica|dentista|osteopat|fisioter|ticket sanitari|riba|non solo ricci|parrucch": "Salute & Benessere",
    r"a favore di|disposizione a favore di|a una persona|quota|regalo|prelievo|bancomat|prestito|restituzione": "Spese Personali & P2P"
}


_REGOLE_COMPILATE = [
    (re.compile(pattern, re.IGNORECASE), categoria)
    for pattern, categoria in REGOLE_FISSE.items()
]

def categorizza_con_regole(causale: str) -> str:
    """Verifica la causale contro le regole deterministiche precompilate."""
    if not causale:
        return "Non Categorizzato"
    
    testo = str(causale).lower()
    for regex, categoria in _REGOLE_COMPILATE:
        if regex.search(testo):
            return categoria
            
    return "Non Categorizzato"