import pandas as pd
import hashlib
import io
import re
from db import execute_query

def calcola_hash(data: str, importo: float, causale: str) -> str:
    """Genera un hash SHA-256 univoco per prevenire duplicati."""
    chiave = f"{str(data).strip()}_{float(importo):.2f}_{str(causale).strip().lower()}"
    return hashlib.sha256(chiave.encode('utf-8')).hexdigest()

def clean_amount(val) -> float:
    """Normalizza qualsiasi formato monetario in float standard."""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    # Rimuove simboli valuta, caratteri corrotti e spazi
    val_str = str(val).replace('€', '').replace('', '').strip()
    val_str = re.sub(r'[^\d,\.\-]', '', val_str)
    
    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
    return float(val_str)

def parse_intesa(file_bytes) -> pd.DataFrame:
    """Parser dedicato a Intesa Sanpaolo: salta i metadati fino alla riga di header."""
    # Decodifica il file gestendo eventuali caratteri speciali (latin-1 / utf-8)
    content = file_bytes.getvalue().decode("latin-1")
    lines = content.splitlines()
    
    # Individua l'indice della riga che contiene le intestazioni reali
    header_idx = None
    for idx, line in enumerate(lines):
        if "Data" in line and "Operazione" in line and "Importo" in line:
            header_idx = idx
            break
            
    if header_idx is None:
        raise ValueError("Header non trovato nel file Intesa Sanpaolo.")
        
    # Carica in dataframe saltando i metadati
    csv_data = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_data), sep=";", decimal=",")
    
    # Rimuove eventuali colonne vuote create dai ';' finali
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')].dropna(how='all')
    
    # Pulizia nomi colonne
    cols = {col.strip(): col for col in df.columns}
    
    clean_df = pd.DataFrame()
    clean_df['Data'] = pd.to_datetime(df[cols['Data']], dayfirst=True).dt.strftime('%d-%m-%Y')
    clean_df['Importo'] = df[cols['Importo']].apply(clean_amount)
    
    # Unisce 'Operazione' e 'Dettagli' per creare una causale descrittiva ricca
    clean_df['Causale'] = (df[cols['Operazione']].fillna('') + " - " + df[cols.get('Dettagli', cols['Operazione'])].fillna('')).str.strip(" -")
    clean_df['Banca'] = 'Intesa Sanpaolo'
    
    return clean_df

def parse_hype(file_bytes_or_df) -> pd.DataFrame:
    """Parser dedicato a Hype: gestisce separatore ';', encoding e unione causale."""
    if hasattr(file_bytes_or_df, 'getvalue'):
        try:
            content = file_bytes_or_df.getvalue().decode('utf-8')
        except UnicodeDecodeError:
            content = file_bytes_or_df.getvalue().decode('latin-1')
        df = pd.read_csv(io.StringIO(content), sep=';')
    else:
        df = file_bytes_or_df

    # Normalizzazione nomi colonne (rimuove spazi e caratteri non standard)
    col_map = {re.sub(r'[^a-zA-Z]', '', c).lower(): c for c in df.columns}
    
    # Individuazione dinamica delle colonne
    col_data = next((col_map[c] for c in ['dataoperazione', 'data'] if c in col_map), df.columns[0])
    col_importo = next((col_map[c] for c in ['importo', 'importoeur', 'ammontare'] if c in col_map), None)
    
    # Se non trova 'importo', prende la colonna che contiene la parola
    if not col_importo:
        col_importo = [c for c in df.columns if 'importo' in c.lower()][0]

    col_nome = col_map.get('nome', None)
    col_desc = col_map.get('descrizione', None)
    col_tipo = col_map.get('tipologia', None)

    clean_df = pd.DataFrame()
    clean_df['Data'] = pd.to_datetime(df[col_data], dayfirst=True).dt.strftime('%d-%m-%Y')
    clean_df['Importo'] = df[col_importo].apply(clean_amount)
    
    # Combina Tipologia, Nome esercente e Descrizione per un matching RegEx accurato
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

def parse_satispay(df: pd.DataFrame) -> pd.DataFrame:
    """Parser ottimizzato per estratto conto Satispay."""
    
    # Normalizzazione intestazioni per accesso sicuro
    cols = {col.strip().lower(): col for col in df.columns}
    
    col_data = cols.get('data', df.columns[0])
    col_importo = cols.get('importo', df.columns[3])
    col_nome = cols.get('nome')
    col_desc = cols.get('descrizione')
    col_tipo = cols.get('tipo')
    col_stato = cols.get('stato')
    
    #Filtro Transazioni: si cancellano le transazioni di tipo 'Annullato'
    if col_stato:
        df = df[df[col_stato].astype(str).str.contains('Approvato', case=False, na=False)]
    
    clean_df = pd.DataFrame()
    
    #Formattazione data
    clean_df['Data'] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce').dt.strftime('%d-%m-%Y')
    
    #Pulizia importo richiamando la funzione esistente nell'ETL
    clean_df['Importo'] = df[col_importo].apply(clean_amount)
    
    #Creazione Causale Arricchita
    nome_str = df[col_nome].fillna('').astype(str) if col_nome else ''
    desc_str = df[col_desc].fillna('').astype(str) if col_desc else ''
    tipo_str = df[col_tipo].fillna('').astype(str) if col_tipo else ''
    #Concatenazione dei campi
    causale_completa = nome_str + " - " + desc_str + " - " + tipo_str
    
    # Rimozione dei caratteri non ASCII generati da problemi di codifica del CSV
    causale_completa = causale_completa.apply(lambda x: re.sub(r'[^\x00-\x7F\xa0-\xff]', '', str(x)))
    
    # Pulizia profonda dei trattini ridondanti: se manca la descrizione, evita risultati come "Nome - - Tipo"
    causale_completa = causale_completa.str.replace(r'(\s*-\s*)+', ' - ', regex=True).str.strip(' -')

    clean_df['Causale'] = causale_completa
    clean_df['Banca'] = 'Satispay'
    
    #Pre-categorizzazione Giroconti con aggiunta marcatore per agevolare categorizer.py
    giroconti_keywords = ['Dalla Banca', 'Verso la Banca', 'Risparmi', 'Investimento']
    mask_giroconto = clean_df['Causale'].str.contains('|'.join(giroconti_keywords), case=False, na=False)
    clean_df.loc[mask_giroconto, 'Causale'] = '[GIROCONTO] ' + clean_df.loc[mask_giroconto, 'Causale']
    
    return clean_df

def transform_and_load(df_raw: pd.DataFrame, banca: str) -> tuple[int, int]:
    """Trasforma i dati grezzi e applica l'Upsert/Insert Ignore su MySQL."""
    if banca == "Intesa Sanpaolo":
        df_norm = parse_intesa(df_raw)
    elif banca == "Hype":
        df_norm = parse_hype(df_raw)
    elif banca == "Satispay":
        df_norm = parse_satispay(df_raw)
    else:
        raise ValueError("Banca non supportata")
    
    # Generazione Hash Univoco per ogni riga
    df_norm['Hash_Duplicato'] = df_norm.apply(
        lambda r: calcola_hash(r['Data'], r['Importo'], r['Causale']), axis=1
    )
    
    inseriti = 0
    duplicati = 0
    
    query = """
    INSERT INTO TRANSAZIONE (Data, Importo, Causale, Banca, Categoria, Hash_Duplicato)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE Id = Id;
    """
    
    for _, row in df_norm.iterrows():
        try:
            execute_query(query, (
                row['Data'],
                row['Importo'],
                row['Causale'],
                row['Banca'],
                'Non Categorizzato',
                row['Hash_Duplicato']
            ))
            inseriti += 1
        except Exception:
            duplicati += 1
            
    return inseriti, duplicati