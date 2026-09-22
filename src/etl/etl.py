"""
Modulo: Lettura dei dati

Funzionalità:
- Deduplicazione tramite hash
- Parser specifici per le varie banche
- Caricamento nel DB con 'Non Categorizzato'

"""

import hashlib
import io
import re
import pandas as pd
from src.database.db import run_query, execute_query

def calcola_hash(data: str, importo: float, causale: str) -> str:
    """Genera un hash SHA-256 univoco per garantire l'idempotenza dei caricamenti."""
    chiave = f"{str(data).strip()}_{float(importo):.2f}_{str(causale).strip().lower()}"
    return hashlib.sha256(chiave.encode('utf-8')).hexdigest()

def clean_amount(val) -> float:
    """Normalizza stringhe monetarie eterogenee nel tipo float."""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    val_str = str(val).replace('€', '').strip()
    val_str = re.sub(r'[^\d,\.\-]', '', val_str)

    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
    return float(val_str)

def parse_intesa(file_bytes_or_df) -> pd.DataFrame:
    """Parser per estratti conto Intesa Sanpaolo."""
    if hasattr(file_bytes_or_df, 'getvalue'):
        try:
            content = file_bytes_or_df.getvalue().decode("latin-1")
        except UnicodeDecodeError:
            content = file_bytes_or_df.getvalue().decode("utf-8")
        lines = content.splitlines()
        header_idx = next(
            (idx for idx, line in enumerate(lines) if "Data" in line and "Operazione" in line and "Importo" in line),
            None
        )
        if header_idx is None:
            raise ValueError("Header non trovato nel file Intesa Sanpaolo.")

        csv_data = "\n".join(lines[header_idx:])
        df = pd.read_csv(io.StringIO(csv_data), sep=";", decimal=",")
    else:
        df = file_bytes_or_df

    df = df.loc[:, ~df.columns.str.contains('^Unnamed')].dropna(how='all')
    cols = {col.strip(): col for col in df.columns}

    clean_df = pd.DataFrame()
    clean_df['Data'] = pd.to_datetime(df[cols['Data']], dayfirst=True).dt.strftime('%Y-%m-%d')
    clean_df['Importo'] = df[cols['Importo']].apply(clean_amount)
    clean_df['Causale'] = (
        df[cols['Operazione']].fillna('') + " - " + df[cols.get('Dettagli', cols['Operazione'])].fillna('')
    ).str.strip(" -")
    clean_df['Banca'] = 'Intesa Sanpaolo'
    return clean_df

def parse_hype(file_bytes_or_df) -> pd.DataFrame:
    """Parser per estratti conto Hype."""
    if hasattr(file_bytes_or_df, 'getvalue'):
        try:
            content = file_bytes_or_df.getvalue().decode('utf-8')
        except UnicodeDecodeError:
            content = file_bytes_or_df.getvalue().decode('latin-1')
        df = pd.read_csv(io.StringIO(content), sep=';')
    else:
        df = file_bytes_or_df

    col_map = {re.sub(r'[^a-zA-Z]', '', c).lower(): c for c in df.columns}
    col_data = next((col_map[c] for c in ['dataoperazione', 'data'] if c in col_map), df.columns[0])
    col_importo = next((col_map[c] for c in ['importo', 'importoeur', 'ammontare'] if c in col_map), None)
    if not col_importo:
        col_importo = [c for c in df.columns if 'importo' in c.lower()][0]

    col_nome = col_map.get('nome', None)
    col_desc = col_map.get('descrizione', None)
    col_tipo = col_map.get('tipologia', None)

    clean_df = pd.DataFrame()
    clean_df['Data'] = pd.to_datetime(df[col_data], dayfirst=True).dt.strftime('%Y-%m-%d')
    clean_df['Importo'] = df[col_importo].apply(clean_amount)

    causali = []
    for _, r in df.iterrows():
        parti = []
        if col_tipo and pd.notna(r[col_tipo]):
            parti.append(str(r[col_tipo]))
        if col_nome and pd.notna(r[col_nome]):
            parti.append(str(r[col_nome]))
        if col_desc and pd.notna(r[col_desc]):
            parti.append(str(r[col_desc]))
        causali.append(" - ".join(parti))

    clean_df['Causale'] = causali
    clean_df['Banca'] = 'Hype'
    return clean_df

def parse_satispay(file_bytes_or_df) -> pd.DataFrame:
    """Parser per estratti conto Satispay."""
    if hasattr(file_bytes_or_df, 'getvalue'):
        try:
            content = file_bytes_or_df.getvalue().decode('latin-1')
        except UnicodeDecodeError:
            content = file_bytes_or_df.getvalue().decode('utf-8')
        df = pd.read_csv(io.StringIO(content), sep=';')
    else:
        df = file_bytes_or_df

    cols = {col.strip().lower(): col for col in df.columns}
    col_data = cols.get('data', df.columns[0])
    col_importo = cols.get('importo', df.columns[3])
    col_nome = cols.get('nome')
    col_desc = cols.get('descrizione')
    col_tipo = cols.get('tipo')
    col_stato = cols.get('stato')

    if col_stato:
        df = df[df[col_stato].astype(str).str.contains('Approvato', case=False, na=False)]

    clean_df = pd.DataFrame()
    clean_df['Data'] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
    clean_df['Importo'] = df[col_importo].apply(clean_amount)

    nome_str = df[col_nome].fillna('').astype(str) if col_nome else ''
    desc_str = df[col_desc].fillna('').astype(str) if col_desc else ''
    tipo_str = df[col_tipo].fillna('').astype(str) if col_tipo else ''

    causale_completa = nome_str + " - " + desc_str + " - " + tipo_str
    causale_completa = causale_completa.apply(lambda x: re.sub(r'[^\x00-\x7F\xa0-\xff]', '', str(x)))
    causale_completa = causale_completa.str.replace(r'(\s*-\s*)+', ' - ', regex=True).str.strip(' -')

    clean_df['Causale'] = causale_completa
    clean_df['Banca'] = 'Satispay'

    giroconti_keywords = ['Dalla Banca', 'Verso la Banca', 'Risparmi', 'Investimento']
    mask_giroconto = clean_df['Causale'].str.contains('|'.join(giroconti_keywords), case=False, na=False)
    clean_df.loc[mask_giroconto, 'Causale'] = '[GIROCONTO] ' + clean_df.loc[mask_giroconto, 'Causale']

    return clean_df

def parse_estratto_conto(file_obj, banca: str, separatore: str = ",") -> pd.DataFrame:
    """Smista il parsing verso l'estrattore corretto in base all'istituto."""
    file_obj.seek(0)
    if banca == "Intesa Sanpaolo":
        return parse_intesa(file_obj)
    elif banca == "Hype":
        return parse_hype(file_obj)
    elif banca == "Satispay":
        return parse_satispay(file_obj)
    else:
        # Fallback per CSV generici
        df = pd.read_csv(file_obj, sep=separatore)
        df['Banca'] = banca
        return df

def salva_transazioni(df: pd.DataFrame) -> tuple[int, int]:
    """
    Esegue la deduplicazione e salva in batch le transazioni nel database.
    Restituisce: (righe_inserite, righe_scartate_o_duplicate).
    """
    if df.empty:
        return 0, 0

    df_work = df.copy()

    if 'Hash_Duplicato' not in df_work.columns:
        df_work['Hash_Duplicato'] = df_work.apply(
            lambda r: calcola_hash(r['Data'], r['Importo'], r['Causale']), axis=1
        )

    totale_righe = len(df_work)

    # 1. Scarto duplicati interni allo stesso file CSV
    df_dedup = df_work.drop_duplicates(subset=['Hash_Duplicato'])

    # 2. Controllo duplicati rispetto allo storico sul DB (query con alias T esplicito)
    hash_esistenti_df = run_query("SELECT T.Hash_Duplicato FROM TRANSAZIONE T WHERE T.Hash_Duplicato IS NOT NULL")
    hash_esistenti = set(hash_esistenti_df['Hash_Duplicato'].dropna().tolist()) if not hash_esistenti_df.empty else set()

    # 3. Isolamento record nuovi
    df_nuovi = df_dedup[~df_dedup['Hash_Duplicato'].isin(hash_esistenti)]
    duplicati = totale_righe - len(df_nuovi)

    if df_nuovi.empty:
        return 0, duplicati

    # 4. Inserimento batch in singola transazione atomica
    records = [
        {
            "data": str(r['Data']),
            "importo": float(r['Importo']),
            "causale": str(r['Causale']),
            "banca": str(r['Banca']),
            "categoria": "Non Categorizzato",
            "hash_duplicato": str(r['Hash_Duplicato'])
        }
        for _, r in df_nuovi.iterrows()
    ]

    query = """
        INSERT INTO TRANSAZIONE (Data, Importo, Causale, Banca, Categoria, Hash_Duplicato)
        VALUES (:data, :importo, :causale, :banca, :categoria, :hash_duplicato)
    """
    execute_query(query, records)

    return len(df_nuovi), duplicati

def transform_and_load(df_raw, banca: str) -> tuple[int, int]:
    """Wrapper di compatibilità verso la pipeline normalizzazione + salvataggio."""
    df_norm = parse_estratto_conto(df_raw, banca)
    return salva_transazioni(df_norm)