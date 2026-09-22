"""
Modulo: Sanitizzazione e protezione privacy

Funzionalità:
- Masking dei dati sensibili prima dell'elaborazione

"""

import re

PATTERN_IBAN = re.compile(r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b', re.IGNORECASE)

PATTERN_CARTA_ESTESA = re.compile(r'\b(?:\d{4}[ -]?){3}\d{4}\b')
PATTERN_CARTA_MASCHERATA_1 = re.compile(r'\b(?:\*{4}[ -]?){2,3}\d{4}\b')
PATTERN_CARTA_MASCHERATA_2 = re.compile(r'\*{3,}\s*\d{4}')

PATTERN_CF = re.compile(
    r'\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPR-T][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b',
    re.IGNORECASE
)

PATTERN_NOMINATIVI = re.compile(
    r'\b(a favore di|disposizione a favore di|ordinante|beneficiario|accredito bonifico da|bonifico da|a una persona)\s+'
    r'([A-Za-zÀ-ÿ\s\.\,\'\-]{2,40}?)'
    r'(?=\s+(?:iban|bic|nota|causale|id|data|cro|trn|\d{2}\/\d{2}\/|\-|\/|$)|$)',
    re.IGNORECASE
)

def maschera_dati_sensibili(testo: str) -> str:
    """
    Rimuove identificativi personali e riferimenti bancari (IBAN, carte, CF, nominativi)
    lasciando inalterato il contesto semantico necessario alla classificazione.
    """
    if not testo or not isinstance(testo, str):
        return ""

    s = PATTERN_IBAN.sub('[IBAN]', testo)
    s = PATTERN_CARTA_ESTESA.sub('[CARTA]', s)
    s = PATTERN_CARTA_MASCHERATA_1.sub('[CARTA]', s)
    s = PATTERN_CARTA_MASCHERATA_2.sub('[CARTA]', s)
    s = PATTERN_CF.sub('[CF]', s)
    s = PATTERN_NOMINATIVI.sub(r'\1 [NOME]', s)

    return s.strip()