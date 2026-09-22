"""
Modulo: Memoria Vettoriale

Funzionalità:
- Pulizia delle stopword bancarie per non sporcare il contesto
- Cold Start: garanzia di classificazione anche se non ancora presente uno storico
- Aggiornamento della memoria con nuove transazioni con categorizzazione approvata
- Ricerca di esempi storici affini
"""

import re
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from src.database.db import run_query
from src.core.sanitizer import maschera_dati_sensibili
from src.core.categorizer import REGOLE_FISSE

CATEGORIE_VALIDE = set(REGOLE_FISSE.values())

# l'inserimento di queste parole avvicinerebbe troppo transazioni di categorie diverse
STOPWORDS_BANCARIE = (
    r"\b(pagamento|pos|c/o|sdd|sepa|mandato|addebito|disposizione|bonifico|"
    r"ordinario|fattura|dr|dott|presso|punto|vendita|station|self|service|"
    r"carta|carte|bancomat|circuito|mediante|effettuato|transazione|operazione|"
    r"ore|alle|il|del|a|favore|di|da|accredito|addebito)\b"
)

# Seed immutabili per il cold start del modello RAG
COLD_START_SEEDS = [
    # Entrate & Rimborsi
    {"testo": "stipendio mensile emolumenti compenso busta paga retribuzione", "categoria": "Entrate & Rimborsi"},
    {"testo": "rimborso spese note spesa trasferta paghetta bonifico entrata", "categoria": "Entrate & Rimborsi"},
    # Spesa
    {"testo": "supermercato ipermercato alimentari spesa carrefour conad coop esselunga lidl bennet pam", "categoria": "Spesa"},
    # Utenze & Casa
    {"testo": "bolletta luce gas energia elettrica fornitura acqua enel eni plenitude iren a2a", "categoria": "Utenze & Casa"},
    {"testo": "canone affitto spese condominiali condominio locazione", "categoria": "Utenze & Casa"},
    {"testo": "telefonia internet fibra ricarica telefonica tim vodafone windtre fastweb iliad", "categoria": "Utenze & Casa"},
    # Trasporti & Carburante
    {"testo": "rifornimento benzina diesel carburante distributore eni q8 ip tamoil", "categoria": "Trasporti & Carburante"},
    {"testo": "pedaggio autostrada telepass parcheggio strisce blu", "categoria": "Trasporti & Carburante"},
    {"testo": "biglietto treno italo trenitalia aereo ryanair easyjet taxi bus metro", "categoria": "Trasporti & Carburante"},
    # Ristorazione
    {"testo": "ristorante pizzeria trattoria osteria sushi cena pranzo", "categoria": "Ristorazione"},
    {"testo": "bar caffetteria aperitivo colazione pub birreria", "categoria": "Ristorazione"},
    {"testo": "food delivery deliveroo glovo just eat uber eats", "categoria": "Ristorazione"},
    # Abbonamenti & Servizi Digitali
    {"testo": "streaming abbonamento netflix spotify amazon prime disney plus dazn", "categoria": "Abbonamenti & Servizi Digitali"},
    {"testo": "cloud storage apple services icloud google storage dropbox software licenza", "categoria": "Abbonamenti & Servizi Digitali"},
    # Shopping
    {"testo": "abbigliamento vestiti scarpe moda shopping zara zalando h&m bershka pull&bear mango asos", "categoria": "Shopping"},
    {"testo": "articoli sportivi abbigliamento tecnico sport decathlon scarpe running attrezzatura sportiva", "categoria": "Shopping"},
    {"testo": "elettronica acquisti tecnologia amazon mediaworld unieuro", "categoria": "Shopping"},
    # Svago e Tempo Libero
    {"testo": "abbonamento palestra corsi fitness piscina centro sportivo arrampicata", "categoria": "Svago e Tempo Libero"},
    {"testo": "videogiochi steam playstation playstation network psn nintendo xbox videogames", "categoria": "Svago e Tempo Libero"},
    {"testo": "cinema multisala biglietto film spettacolo teatro concerto mostra museo eventi", "categoria": "Svago e Tempo Libero"},
    # Salute & Benessere
    {"testo": "farmacia parafarmacia farmaci medicinali scontrino parlante", "categoria": "Salute & Benessere"},
    {"testo": "visita medica dottore dentista fisioterapia osteopata analisi cliniche ticket", "categoria": "Salute & Benessere"},
    # Spese Personali & P2P
    {"testo": "scambio denaro privato bonifico amico restituzione prestito regalo quota cena colletta", "categoria": "Spese Personali & P2P"}
]

def normalizza_per_embedding(testo: str) -> str:
    """Rimuove rumore numerico, date e pattern ricorrenti prima dell'elaborazione vettoriale."""
    t = str(testo).lower()
    t = re.sub(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?", " ", t)
    t = re.sub(r"\b\d{1,2}[:.]\d{2}\b", " ", t)
    t = re.sub(r"\b\d+\b", " ", t)
    t = re.sub(r"\[(iban|carta|cf|nome)\]", " ", t)
    t = re.sub(STOPWORDS_BANCARIE, " ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())

class VectorStore:
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.encoder = SentenceTransformer(model_name)
        self.testi_originali: list[str] = []
        self.testi_puliti: list[str] = []
        self.categorie: list[str] = []
        self.ids_caricati: set[int] = set()
        self.embeddings: np.ndarray | None = None
        
        self._inizializza_seed()
        self.ricarica_indice()

    def _inizializza_seed(self):
        """Genera e memorizza in cache gli embeddings dei seed iniziali."""
        seed_orig = []
        seed_clean = []
        seed_cat = []

        for s in COLD_START_SEEDS:
            p = normalizza_per_embedding(s["testo"])
            if p:
                seed_orig.append(s["testo"])
                seed_clean.append(p)
                seed_cat.append(s["categoria"])

        self._seed_originali = seed_orig
        self._seed_puliti = seed_clean
        self._seed_categorie = seed_cat
        
        if seed_clean:
            self._seed_embeddings = self.encoder.encode(seed_clean, normalize_embeddings=True)
        else:
            self._seed_embeddings = np.empty((0, 384), dtype=np.float32)

    def ricarica_indice(self, full_reload: bool = False):
        """
        Aggiorna l'indice in modo incrementale elaborando solo le transazioni
        recentemente approvate o aggiunte nel database.
        """
        if full_reload or self.embeddings is None:
            self.testi_originali = list(self._seed_originali)
            self.testi_puliti = list(self._seed_puliti)
            self.categorie = list(self._seed_categorie)
            self.ids_caricati = set()
            self.embeddings = np.copy(self._seed_embeddings)

        df_storico = run_query(
            "SELECT T.Id, T.Causale, T.Categoria "
            "FROM TRANSAZIONE T "
            "WHERE T.Categoria <> 'Non Categorizzato'"
        )

        if df_storico.empty:
            return

        df_delta = df_storico[~df_storico["Id"].isin(self.ids_caricati)]
        if df_delta.empty:
            return

        nuovi_originali = []
        nuovi_puliti = []
        nuovi_cat = []
        nuovi_ids = []

        for _, row in df_delta.iterrows():
            categoria = str(row["Categoria"]).strip()
            if categoria not in CATEGORIE_VALIDE:
                continue

            causale_sanitizzata = maschera_dati_sensibili(str(row["Causale"]))
            causale_pulita = normalizza_per_embedding(causale_sanitizzata)

            if causale_pulita.strip():
                nuovi_originali.append(causale_sanitizzata)
                nuovi_puliti.append(causale_pulita)
                nuovi_cat.append(categoria)
                nuovi_ids.append(int(row["Id"]))

        if not nuovi_puliti:
            self.ids_caricati.update(df_delta["Id"].tolist())
            return

        nuovi_embeddings = self.encoder.encode(nuovi_puliti, normalize_embeddings=True)

        if self.embeddings.shape[0] == 0:
            self.embeddings = nuovi_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, nuovi_embeddings])

        self.testi_originali.extend(nuovi_originali)
        self.testi_puliti.extend(nuovi_puliti)
        self.categorie.extend(nuovi_cat)
        self.ids_caricati.update(nuovi_ids)

    def cerca_esempi_simili(self, causale: str, k: int = 3) -> list[dict]:
        """Calcola la similarità cosenica ed estrae i k esempi semanticamente più vicini."""
        if self.embeddings is None or len(self.embeddings) == 0:
            return []

        causale_sanitizzata = maschera_dati_sensibili(causale)
        causale_pulita = normalizza_per_embedding(causale_sanitizzata)
        
        vettore_query = self.encoder.encode([causale_pulita], normalize_embeddings=True)
        similarita = cosine_similarity(vettore_query, self.embeddings)[0]

        k_effettivo = min(k, len(similarita))
        indici_top = np.argsort(similarita)[::-1][:k_effettivo]

        return [
            {
                "causale": self.testi_originali[idx],
                "categoria": self.categorie[idx],
                "similarita": float(similarita[idx])
            }
            for idx in indici_top
        ]