import re

# Dizionario di regole fisse (Regex Pattern -> Categoria)
REGOLE_FISSE = {
    # 0. Ricariche e Trasferimenti Interni (priorità alta)
    r"satispay|ricarica |giroconto |dalla banca |verso la banca | risparmi | investimento|\[giroconto\]": "Giroconto",

    # 1. Spese standard
    r"conad|esselunga|carrefour|coop|lidl|pam|penny|bennet|gigante ": "Spesa",
    r"q8|eni|ip |tamoil|autostrade|telepass|tap & go torino|sostapp": "Trasporti & Carburante",
    r"amazon|aliexpress|temu|zalando": "Shopping Online",
    r"ristorante|trattoria|pizzeria|nyx |mcdonald|burger king|starbucks |pummar|bar|bristrot|caff|panino|bakery|trapizzino|..."
    "skassa|evolution|to11|gelat|chiosco|rifugio|panche": "Ristorazione",
    r"netflix|spotify|disney|prime video|dazn": "Abbonamenti & Streaming",
    r"farmacia|ospedale|visita medica|dentista|riba|non solo ricci": "Salute & Benessere",
    r"stipendio|emolumenti|accredito bonifico da |compenso | premio": "Entrate & Stipendio",
    r"affitto|condominio|luce|gas|enel|iren|a2a|vodafone|tim |iliad": "Utenze & Casa",
    r"rimborso|paghetta|mese": "Rimborsi & Paghette",
    r"a una persona|regalo inviato": "Spese Personali & P2P"
}

def categorizza_con_regole(causale: str) -> str:
    """Classifica la causale tramite matching con espressioni regolari."""
    if not causale:
        return "Non Categorizzato"
    
    testo = str(causale).lower()
    for pattern, cat in REGOLE_FISSE.items():
        if re.search(pattern, testo):
            return cat
            
    return "Non Categorizzato"