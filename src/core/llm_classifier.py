"""
Modulo: Classificatore ibrido LLM & RAG

Funzionalità:
- Soglie di similarità vettoriale:
    1. Forte Affinità: alta similarità vettoriale con esempi storici, bypass dell'LLM e assegnazione automatica della categoria
    2. Parziale Affinità: media similarità con esempi storici, interrogazione dell'LLM con aggiunta di top 3 esempi storici
    3. Scarsa Affinità: bassa similarità con esempi storici, interrogazione dell'LLM senza esmepi storici
- Output con valore di confidenza e motivazione
"""

import json
import ollama
from src.core.sanitizer import maschera_dati_sensibili
from src.core.categorizer import REGOLE_FISSE
from src.core.vector_store import VectorStore

CATEGORIE_VALIDE = sorted(list(set(REGOLE_FISSE.values())))

# mantedimento di 'VectorStore' residente in memoria per non ricaricarlo ogni volta
_VECTOR_STORE = None
def get_vector_store() -> VectorStore:
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        _VECTOR_STORE = VectorStore()
    return _VECTOR_STORE

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "categoria": {
            "type": "string",
            "enum": CATEGORIE_VALIDE + ["Non Categorizzato"]
        },
        "confidenza": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "motivo": {
            "type": "string"
        }
    },
    "required": ["categoria", "confidenza", "motivo"]
}

BASE_SYSTEM_PROMPT = f"""Sei un assistente contabile personale esperto.
Classifica la transazione scegliendo ESCLUSIVAMENTE una delle seguenti categorie:
{json.dumps(CATEGORIE_VALIDE, ensure_ascii=False)}

REGOLE DI DOMINIO FONDAMENTALI:
- "Utenze & Casa": bollette luce, gas, acqua, rifiuti, affitto, spese condominiali, telefonia fissa e mobile (TIM, Vodafone, WindTre, Fastweb).
- "Abbonamenti & Servizi Digitali": abbonamenti streaming (Netflix, Spotify), licenze software, cloud storage (iCloud, Google One, Dropbox).
- "Shopping": acquisto di beni fisici, abbigliamento, calzature, elettronica, articoli sportivi e attrezzatura (es. Decathlon, Nike, Zara, Amazon).
- "Svago e Tempo Libero": esperienze, eventi ed intrattenimento: ingressi e abbonamenti palestra/piscina, cinema, teatri, concerti, videogiochi digitali (Steam, PlayStation), libri.
- "Spese Personali & P2P": scambi tra privati, quote cene, restituzione prestiti ad amici o parenti, prelievi contante bancomat.
- "Ristorazione": bar, caffetterie, pizzerie, ristoranti, pub, fast food e servizi di food delivery (Deliveroo, Glovo).
- "Spesa": supermercati, ipermercati e negozi di generi alimentari.
- "Trasporti & Carburante": benzina, diesel, ricarica elettrica, caselli autostradali, telepass, parcheggi, treni, aerei, taxi e mezzi pubblici.
- "Salute & Benessere": farmacie, visite specialistiche, dentisti, fisioterapia, osteopatia, analisi cliniche.
- "Entrate & Rimborsi": stipendio, emolumenti, paghette, rimborsi note spese ricevuti.
- "Giroconto": trasferimenti di denaro tra propri conti correnti o verso conti deposito/investimento.

ISTRUZIONI FORMATO RISPOSTA:
- Nel campo "confidenza", inserisci un valore decimale tra 0.0 e 1.0 (es. 0.95 se il merchant o l'analogia con gli esempi storici è evidente, 0.50 se la causale è generica o dubbia).
- Nel campo "motivo", indica in massimo 6-8 parole la ragione sintetica dell'assegnazione.
"""

def classifica_con_rag(causale: str, importo: float, banca: str, model: str = "llama3.2:3b") -> dict:
    
    vs = get_vector_store()
    causale_sanitizzata = maschera_dati_sensibili(causale)
    
    vicini = vs.cerca_esempi_simili(causale_sanitizzata, k=3)
    top_sim = vicini[0]["similarita"] if vicini else 0.0
    
    SOGLIA_FORTE_AFFINITA = 0.85
    SOGLIA_PARZIALE_AFFINITA = 0.40

    #AFFINITA FORTE
    if top_sim >= SOGLIA_FORTE_AFFINITA:
        miglior_match = vicini[0]
        return {
            "categoria": miglior_match["categoria"],
            "confidenza": 0.98,
            "motivo": f"Forte affinità vettoriale diretta ({top_sim:.2f}) con: '{miglior_match['causale'][:30]}'",
            "metodo": "RAG Diretto (Forte Affinità)",
            "causale_sanitizzata": causale_sanitizzata
        }

    system_prompt = BASE_SYSTEM_PROMPT
    metodo = "LLM Zero-Shot (Bassa Affinità)"

    #AFFINITA PARZIALE
    if top_sim >= SOGLIA_PARZIALE_AFFINITA:
        metodo = "LLM Dynamic Few-Shot (Parziale Affinità)"
        esempi_blocco = "\nESEMPI STORICI REALI RECUPERATI DAL DATABASE:\n"
        for v in vicini:
            esempi_blocco += f"- Causale: \"{v['causale']}\" -> Categoria: \"{v['categoria']}\"\n"
        system_prompt += esempi_blocco

    segno = "ENTRATA / ACCREDITO" if importo > 0 else "USCITA / ADDEBITO"
    user_prompt = (
        f"Classifica questa transazione:\n"
        f"- Tipologia: {segno}\n"
        f"- Importo: {importo:.2f} €\n"
        f"- Banca: {banca}\n"
        f"- Causale: {causale_sanitizzata}\n"
    )

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            format=JSON_SCHEMA,
            options={"temperature": 0.0}
        )
        
        dati = json.loads(response["message"]["content"])
        cat = dati.get("categoria", "Non Categorizzato")
        if cat not in CATEGORIE_VALIDE:
            cat = "Non Categorizzato"

        return {
            "categoria": cat,
            "confidenza": float(dati.get("confidenza", 0.0)),
            "motivo": str(dati.get("motivo", "")),
            "metodo": metodo,
            "causale_sanitizzata": causale_sanitizzata
        }
    except Exception as e:
    #gestione non risposta di Ollama
        return {
            "categoria": "Non Categorizzato",
            "confidenza": 0.0,
            "motivo": f"Errore inferenza: {str(e)}",
            "metodo": "Errore",
            "causale_sanitizzata": causale_sanitizzata
        }